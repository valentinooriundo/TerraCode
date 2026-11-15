import asyncio
import hashlib
import json
import re
import secrets
import time
from typing import Callable

import flet as ft
from flet.controls.services.url_launcher import LaunchMode

import theme

from services import auth_service
from services.auth_service import CANAL_MOVIL, CANAL_WEB, AuthError, Session

# Mismo formato que valida el backend (Usuario.normalizarLogin)
LOGIN_RE = re.compile(r"^[a-z0-9._-]{3,60}$")

# Web: inicio con Google en curso (id + verificador), guardado en el navegador mientras la pestaña va a Google
CLAVE_GOOGLE = "terracode.google_pendiente"
VIGENCIA_GOOGLE = 600  # segundos, igual que el inicio en el backend


def _canal(page: ft.Page) -> str:
    """Android e iOS entran por el canal MOVIL; escritorio y navegador por WEB."""
    movil = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS) and not page.web
    return CANAL_MOVIL if movil else CANAL_WEB


def build_login_view(page: ft.Page, on_success: Callable[[Session], None]) -> ft.Control:
    email = ft.TextField(
        label="Usuario",
        prefix_icon=ft.Icons.PERSON_OUTLINE,
        autofocus=True,
        width=320,
    )
    password = ft.TextField(
        label="Contraseña",
        prefix_icon=ft.Icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        width=320,
    )
    error = ft.Text("", color=theme.DANGER, visible=False)
    loading = ft.ProgressRing(width=20, height=20, stroke_width=2, visible=False)

    def set_busy(busy: bool):
        email.disabled = busy
        password.disabled = busy
        submit.disabled = busy
        loading.visible = busy

    async def do_login(e):
        error.visible = False
        email.error_text = None
        password.error_text = None

        email_value = (email.value or "").strip().lower()
        password_value = password.value or ""

        if not LOGIN_RE.match(email_value):
            email.error_text = "De 3 a 60 caracteres: letras, números, punto, guion o guion bajo"
        if not password_value:
            password.error_text = "Ingresa tu contraseña"
        if email.error_text or password.error_text:
            page.update()
            return

        set_busy(True)
        page.update()
        try:
            session = await asyncio.to_thread(auth_service.login, email_value, password_value, _canal(page))
        except AuthError as ex:
            error.value = str(ex)
            error.visible = True
            set_busy(False)
            page.update()
            return

        on_success(session)

    async def focus_password(e):
        await password.focus()

    email.on_submit = focus_password
    password.on_submit = do_login

    submit = ft.Button(
        content="Iniciar sesión",
        on_click=do_login,
        width=320,
        bgcolor=theme.PRIMARY,
        color=theme.TEXT_ON_PRIMARY,
    )

    # ---------- Login con Google ----------
    # La app guarda un verificador secreto y solo envía su SHA-256.
    # - Móvil/escritorio: abre Google en el navegador externo (Google no permite iniciar sesión dentro de la app) y
    #   pregunta al backend cada 2 s hasta que el usuario vuelva.
    # - Web: guarda id + verificador en el navegador y abre Google en la misma pestaña; el backend redirige de vuelta
    #   a /app/ y al cargar se canjea lo guardado (retomar_google).
    prefs = ft.SharedPreferences() if page.web else None

    google_estado: dict = {"activo": False}
    google_espera = ft.Row(
        visible=False,
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=10,
        controls=[
            ft.ProgressRing(width=16, height=16, stroke_width=2),
            texto_espera := ft.Text("Esperando a Google… completa el inicio en el navegador", size=12,
                                    color=theme.TEXT_MUTED),
        ],
    )

    def fin_google(mensaje: str | None = None):
        google_estado["activo"] = False
        google_espera.visible = False
        boton_cancelar.visible = False
        boton_google.disabled = False
        set_busy(False)
        if mensaje:
            error.value = mensaje
            error.visible = True
        page.update()

    async def login_google(e):
        if google_estado["activo"]:
            return
        error.visible = False
        verificador = secrets.token_urlsafe(48)
        desafio = hashlib.sha256(verificador.encode("utf-8")).hexdigest()
        google_estado["activo"] = True
        boton_google.disabled = True
        set_busy(True)
        page.update()
        try:
            inicio = await asyncio.to_thread(auth_service.google_inicio, desafio, _canal(page))
            if page.web:
                await prefs.set(CLAVE_GOOGLE, json.dumps(
                    {"id": inicio["id"], "verificador": verificador, "ts": time.time()}))
                await ft.UrlLauncher().launch_url(inicio["url"], web_only_window_name="_self")
                return  # la pestaña se va a Google
            await ft.UrlLauncher().launch_url(inicio["url"], mode=LaunchMode.EXTERNAL_APPLICATION)
        except AuthError as ex:
            fin_google(str(ex))
            return
        except Exception:
            fin_google("No se pudo abrir el navegador para iniciar sesión con Google")
            return

        google_espera.visible = True
        boton_cancelar.visible = True
        page.update()
        # Hasta 10 minutos (vigencia del inicio en el backend)
        for _ in range(300):
            await asyncio.sleep(2)
            if not google_estado["activo"]:
                return  # canceló
            try:
                session = await asyncio.to_thread(auth_service.google_sesion, inicio["id"], verificador)
            except AuthError as ex:
                fin_google(str(ex))
                return
            if session is not None:
                google_estado["activo"] = False
                on_success(session)
                return
        fin_google("Se agotó el tiempo para iniciar sesión con Google. Vuelve a intentarlo")

    async def retomar_google():
        """Web: al volver de Google (o al abrir /app/), canjea el inicio que quedó guardado en el navegador."""
        try:
            guardado = await prefs.get(CLAVE_GOOGLE)
            if not guardado:
                return
            await prefs.remove(CLAVE_GOOGLE)  # un solo intento: si falla, se vuelve a pulsar el botón
            datos = json.loads(guardado)
            inicio_id, verificador = datos["id"], datos["verificador"]
            vigente = time.time() - float(datos.get("ts", 0)) < VIGENCIA_GOOGLE
        except Exception:
            return
        if not vigente:
            return
        google_estado["activo"] = True
        boton_google.disabled = True
        texto_espera.value = "Completando el inicio con Google…"
        google_espera.visible = True
        set_busy(True)
        page.update()
        for _ in range(5):
            try:
                session = await asyncio.to_thread(auth_service.google_sesion, inicio_id, verificador)
            except AuthError as ex:
                fin_google(str(ex))
                return
            if session is not None:
                google_estado["activo"] = False
                on_success(session)
                return
            await asyncio.sleep(2)
        fin_google("No se completó el inicio con Google. Vuelve a intentarlo")

    if page.web:
        page.run_task(retomar_google)

    boton_google = ft.OutlinedButton(
        content="Continuar con Google",
        icon=ft.Icons.ACCOUNT_CIRCLE_OUTLINED,
        width=320,
        on_click=login_google,
    )
    boton_cancelar = ft.TextButton(content="Cancelar", visible=False, on_click=lambda e: fin_google())

    return ft.Container(
        alignment=ft.Alignment.CENTER,
        expand=True,
        content=ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16,
            controls=[
                ft.Image(src="icon.svg", width=72, height=72),
                ft.Text(
                    "TerraCode",
                    size=32,
                    weight=ft.FontWeight.BOLD,
                    color=theme.PRIMARY,
                ),
                ft.Text("Inicia sesión para continuar", size=16, color=theme.TEXT_MUTED),
                email,
                password,
                error,
                submit,
                loading,
                ft.Row(
                    width=320,
                    controls=[
                        ft.Divider(expand=True, color=theme.BORDER_SUBTLE),
                        ft.Text("o", size=12, color=theme.TEXT_MUTED),
                        ft.Divider(expand=True, color=theme.BORDER_SUBTLE),
                    ],
                ),
                boton_google,
                google_espera,
                boton_cancelar,
            ],
        ),
    )
