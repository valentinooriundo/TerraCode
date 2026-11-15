import asyncio
import re
from typing import Callable

import flet as ft

import theme

from services import auth_service
from services.auth_service import CANAL_MOVIL, CANAL_WEB, AuthError, Session

# Mismo formato que valida el backend (Usuario.normalizarLogin)
LOGIN_RE = re.compile(r"^[a-z0-9._-]{3,60}$")


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
            ],
        ),
    )
