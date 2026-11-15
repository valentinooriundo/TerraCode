from datetime import datetime
from typing import Callable

import flet as ft

import theme

from services.auth_service import Session

PRIMARY = theme.PRIMARY


def _greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Buenos días"
    if hour < 19:
        return "Buenas tardes"
    return "Buenas noches"


def _initials(name: str) -> str:
    parts = [p for p in name.replace("@", " ").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def build_home_view(
    page: ft.Page,
    session: Session,
    on_logout: Callable[[], None],
    on_nuevo_registro: Callable[[], None],
    on_ver_registros: Callable[[], None],
) -> ft.Control:
    name = session.display_name

    def notify(msg: str):
        page.show_dialog(ft.SnackBar(content=ft.Text(msg)))

    def action_card(icon, title: str, subtitle: str, on_click) -> ft.Control:
        return ft.Container(
            col={"xs": 6, "md": 3},
            padding=16,
            border_radius=16,
            bgcolor=theme.BG_SURFACE,
            border=ft.Border.all(1, theme.BORDER_SUBTLE),
            ink=True,
            on_click=on_click,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Container(
                        content=ft.Icon(icon, color=theme.PRIMARY_HOVER, size=26),
                        bgcolor=theme.PRIMARY_LIGHT,
                        border_radius=12,
                        padding=10,
                    ),
                    ft.Text(title, size=15, weight=ft.FontWeight.W_600, color=theme.TEXT_MAIN),
                    ft.Text(subtitle, size=12, color=theme.TEXT_MUTED),
                ],
            ),
        )

    def coming_soon(feature: str):
        return lambda e: notify(f"{feature}: próximamente")

    header = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Row(
                spacing=12,
                controls=[
                    ft.CircleAvatar(
                        content=ft.Text(_initials(name), color=theme.TEXT_ON_PRIMARY, weight=ft.FontWeight.BOLD),
                        bgcolor=PRIMARY,
                        radius=22,
                    ),
                    ft.Column(
                        spacing=0,
                        controls=[
                            ft.Text(_greeting(), size=13, color=theme.TEXT_MUTED),
                            ft.Text(name, size=18, weight=ft.FontWeight.BOLD, color=theme.TEXT_MAIN),
                        ],
                    ),
                ],
            ),
            ft.IconButton(
                icon=ft.Icons.LOGOUT,
                icon_color=PRIMARY,
                tooltip="Cerrar sesión",
                on_click=lambda e: on_logout(),
            ),
        ],
    )

    hero = ft.Container(
        padding=24,
        border_radius=20,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[theme.PRIMARY, theme.PRIMARY_HOVER],
        ),
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.ECO, color=theme.TEXT_ON_PRIMARY, size=22),
                        ft.Text("TerraCode", color=theme.TEXT_ON_PRIMARY, size=16, weight=ft.FontWeight.W_600),
                    ],
                ),
                ft.Text(
                    "Bienvenido a tu campo inteligente",
                    color=theme.TEXT_ON_PRIMARY,
                    size=22,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    "Analiza tus cultivos y toma mejores decisiones con datos.",
                    color=ft.Colors.with_opacity(0.9, theme.TEXT_ON_PRIMARY),
                    size=14,
                ),
                ft.Button(
                    content="Iniciar análisis",
                    icon=ft.Icons.PLAY_ARROW_ROUNDED,
                    bgcolor=theme.ACCENT,
                    color=theme.TEXT_ON_PRIMARY,
                    on_click=lambda e: on_nuevo_registro(),
                ),
            ],
        ),
    )

    actions = ft.ResponsiveRow(
        spacing=12,
        run_spacing=12,
        controls=[
            action_card(ft.Icons.ADD_LOCATION_ALT_OUTLINED, "Nuevo registro", "Ubica tu parcela y su cultivo",
                        lambda e: on_nuevo_registro()),
            action_card(ft.Icons.GRASS, "Mis registros", "Lleva el control de tus parcelas",
                        lambda e: on_ver_registros()),
            action_card(ft.Icons.HISTORY, "Historial", "Revisa análisis anteriores", coming_soon("Historial")),
            action_card(ft.Icons.WB_SUNNY_OUTLINED, "Clima", "Pronóstico para tu zona", coming_soon("Clima")),
        ],
    )

    tip = ft.Container(
        padding=16,
        border_radius=16,
        bgcolor=theme.BG_SURFACE,
        border=ft.Border.all(1, theme.BORDER_SUBTLE),
        content=ft.Row(
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, color=theme.ACCENT),
                ft.Column(
                    spacing=4,
                    expand=True,
                    controls=[
                        ft.Text("Consejo del día", weight=ft.FontWeight.W_600, color=theme.TEXT_MAIN),
                        ft.Text(
                            "Registra tus parcelas para obtener análisis más precisos "
                            "y comparar resultados entre temporadas.",
                            size=13,
                            color=theme.TEXT_MUTED,
                        ),
                    ],
                ),
            ],
        ),
    )

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=20,
        controls=[
            header,
            hero,
            ft.Text("Accesos rápidos", size=17, weight=ft.FontWeight.BOLD, color=theme.TEXT_MAIN),
            actions,
            tip,
        ],
    )
