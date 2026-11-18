import asyncio

import flet as ft
import flet_geolocator as gps

from services import auth_service
from services.api_client import ApiClient
from services.auth_service import Session
import theme
from views.clima_view import build_clima_view
from views.historial_view import build_historial_view
from views.home_view import build_home_view
from views.login_view import build_login_view
from views.registro_view import build_registro_view
from views.registros_view import build_registros_view


def main(page: ft.Page):
    page.title = "TerraCode"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    page.bgcolor = theme.BG_MAIN
    page.theme = theme.app_theme()

    # GPS del celular. Un solo servicio para toda la app.
    geo = gps.Geolocator()
    page.services.append(geo)

    # Sesión activa (token del backend). None = no autenticado.
    # El ApiClient renueva el access token solo y deja aquí la sesión vigente.
    state: dict = {"session": None, "api": None}

    def show(control: ft.Control):
        page.controls.clear()
        page.add(control)

    def show_login():
        state["session"] = None
        state["api"] = None
        show(build_login_view(page, on_success=on_login))

    async def cerrar_sesion():
        session = state["session"]
        if session is not None:
            # Cierra la sesión en el backend: su access token deja de servir al instante
            await asyncio.to_thread(auth_service.logout, session)
        show_login()

    def logout():
        # Se puede llamar desde un handler síncrono (lambda e: on_logout()): la llamada HTTP corre en segundo plano
        page.run_task(cerrar_sesion)

    def sesion_renovada(session: Session):
        state["session"] = session

    def show_home():
        show(build_home_view(page, state["session"], on_logout=logout,
                             on_nuevo_registro=show_registro, on_ver_registros=show_registros,
                             on_historial=show_historial, on_clima=show_clima))

    def show_registro():
        show(build_registro_view(page, state["api"], geo, on_back=show_home, on_saved=show_registros,
                                 on_session_expired=show_login))

    def show_registros():
        show(build_registros_view(page, state["api"], on_back=show_home, on_nuevo=show_registro,
                                  on_session_expired=show_login))

    def show_historial():
        show(build_historial_view(page, state["api"], on_back=show_home, on_nuevo=show_registro,
                                  on_session_expired=show_login))

    def show_clima():
        show(build_clima_view(page, geo, on_back=show_home))

    def on_login(session: Session):
        state["session"] = session
        state["api"] = ApiClient(session, on_session_change=sesion_renovada)
        show_home()

    show_login()


ft.run(main)
