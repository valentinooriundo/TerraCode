"""Clima: condiciones actuales y pronóstico de 7 días para la ubicación del celular (Open-Meteo)."""

import asyncio
from typing import Callable

import flet as ft
import flet_geolocator as gps

import theme
from services import clima_service, ubicacion
from services.clima_service import ClimaError
from services.ubicacion import UbicacionError


def _icono(codigo) -> ft.IconData:
    return getattr(ft.Icons, clima_service.tiempo(codigo)[1])


def _num(valor, decimales: int = 0) -> str:
    return "–" if valor is None else f"{valor:.{decimales}f}"


def build_clima_view(page: ft.Page, geo: gps.Geolocator, on_back: Callable[[], None]) -> ft.Control:
    estado_txt = ft.Text("Usaremos la ubicación de tu celular para el pronóstico.", size=13, color=theme.TEXT_MUTED)
    progreso = ft.ProgressRing(width=22, height=22, stroke_width=2, visible=False)
    actual = ft.Container(visible=False)
    dias = ft.Column(spacing=8, visible=False)
    fuente = ft.Text("Datos: Open-Meteo.com", size=11, color=theme.TEXT_MUTED, visible=False)
    boton = ft.Button(content="Obtener pronóstico", icon=ft.Icons.MY_LOCATION, bgcolor=theme.ACCENT,
                      color=theme.TEXT_ON_PRIMARY)

    def dato(icono, etiqueta: str, valor: str) -> ft.Control:
        return ft.Column(spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
            ft.Icon(icono, size=18, color=ft.Colors.with_opacity(0.85, theme.TEXT_ON_PRIMARY)),
            ft.Text(valor, size=14, weight=ft.FontWeight.W_600, color=theme.TEXT_ON_PRIMARY),
            ft.Text(etiqueta, size=11, color=ft.Colors.with_opacity(0.8, theme.TEXT_ON_PRIMARY)),
        ])

    def tarjeta_actual(a: dict, lugar: str) -> ft.Control:
        descripcion = clima_service.tiempo(a["codigo"])[0]
        return ft.Container(
            padding=20,
            border_radius=20,
            gradient=ft.LinearGradient(begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT,
                                       colors=[theme.PRIMARY, theme.PRIMARY_HOVER]),
            content=ft.Column(spacing=14, controls=[
                ft.Row(spacing=6, controls=[
                    ft.Icon(ft.Icons.PLACE_OUTLINED, size=16, color=theme.TEXT_ON_PRIMARY),
                    ft.Text(lugar, size=13, color=theme.TEXT_ON_PRIMARY, expand=True),
                ]),
                ft.Row(spacing=16, controls=[
                    ft.Icon(_icono(a["codigo"]), size=56, color=theme.TEXT_ON_PRIMARY),
                    ft.Column(spacing=0, controls=[
                        ft.Text(f"{_num(a['temperatura'])}°C", size=40, weight=ft.FontWeight.BOLD,
                                color=theme.TEXT_ON_PRIMARY),
                        ft.Text(f"{descripcion} · Sensación {_num(a['sensacion'])}°C", size=13,
                                color=ft.Colors.with_opacity(0.9, theme.TEXT_ON_PRIMARY)),
                    ]),
                ]),
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_AROUND, controls=[
                    dato(ft.Icons.WATER_DROP_OUTLINED, "Humedad", f"{_num(a['humedad'])}%"),
                    dato(ft.Icons.UMBRELLA_OUTLINED, "Lluvia", f"{_num(a['lluvia_mm'], 1)} mm"),
                    dato(ft.Icons.AIR, "Viento", f"{_num(a['viento'])} km/h"),
                ]),
            ]),
        )

    def fila_dia(d: dict, t_min: float, t_max: float) -> ft.Control:
        # Barra de rango de temperatura del día dentro del rango de la semana (una sola serie, un solo tono)
        rango = max(t_max - t_min, 1)
        ancho = 90
        izquierda = (d["min"] - t_min) / rango * ancho if d["min"] is not None else 0
        largo = max(((d["max"] or 0) - (d["min"] or 0)) / rango * ancho, 4)
        descripcion = clima_service.tiempo(d["codigo"])[0]
        prob = d["prob_lluvia"]
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=14,
            bgcolor=theme.BG_SURFACE,
            border=ft.Border.all(1, theme.BORDER_SUBTLE),
            tooltip=f"{descripcion} · lluvia {_num(d['lluvia_mm'], 1)} mm · viento máx. {_num(d['viento_max'])} km/h",
            content=ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Text(d["dia"], width=40, size=14, weight=ft.FontWeight.W_600, color=theme.TEXT_MAIN),
                ft.Icon(_icono(d["codigo"]), size=22, color=theme.PRIMARY_HOVER),
                ft.Column(spacing=0, expand=True, controls=[
                    ft.Text(descripcion, size=13, color=theme.TEXT_MAIN, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"Lluvia {_num(prob)}% · {_num(d['viento_max'])} km/h", size=11,
                            color=theme.TEXT_MUTED),
                ]),
                ft.Text(f"{_num(d['min'])}°", size=13, color=theme.TEXT_MUTED, width=30,
                        text_align=ft.TextAlign.RIGHT),
                ft.Container(width=ancho, height=6, border_radius=3, bgcolor=theme.PRIMARY_LIGHT,
                             content=ft.Row(spacing=0, controls=[
                                 ft.Container(width=izquierda),
                                 ft.Container(width=largo, height=6, border_radius=3, bgcolor=theme.PRIMARY_HOVER),
                             ])),
                ft.Text(f"{_num(d['max'])}°", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_MAIN,
                        width=30),
            ]),
        )

    async def consultar(e=None):
        boton.disabled = True
        progreso.visible = True
        estado_txt.value = "Obteniendo tu ubicación…"
        estado_txt.color = theme.TEXT_MUTED
        page.update()
        try:
            pos = await ubicacion.obtener(page, geo)
            estado_txt.value = "Consultando el pronóstico…"
            page.update()
            datos = await asyncio.to_thread(clima_service.pronostico, pos.latitud, pos.longitud)
        except (UbicacionError, ClimaError) as ex:
            estado_txt.value = str(ex)
            estado_txt.color = theme.DANGER
            return
        finally:
            boton.disabled = False
            progreso.visible = False
            page.update()

        lugar = f"{pos.latitud:.4f}, {pos.longitud:.4f}"
        actual.content = tarjeta_actual(datos["actual"], lugar)
        actual.visible = True
        validos = [d for d in datos["dias"] if d["min"] is not None and d["max"] is not None]
        t_min = min((d["min"] for d in validos), default=0)
        t_max = max((d["max"] for d in validos), default=1)
        dias.controls = [ft.Text("Próximos 7 días", size=17, weight=ft.FontWeight.BOLD, color=theme.TEXT_MAIN),
                         *(fila_dia(d, t_min, t_max) for d in datos["dias"])]
        dias.visible = True
        fuente.visible = True
        estado_txt.value = "Pronóstico actualizado" + (" (ubicación simulada)" if pos.simulada else "")
        estado_txt.color = theme.TEXT_MUTED
        boton.content = "Actualizar"
        boton.icon = ft.Icons.REFRESH
        page.update()

    boton.on_click = consultar

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=16,
        controls=[
            ft.Row(controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=theme.PRIMARY, tooltip="Volver",
                              on_click=lambda e: on_back()),
                ft.Text("Clima", size=20, weight=ft.FontWeight.BOLD, color=theme.TEXT_MAIN),
            ]),
            ft.Row(spacing=12, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                   controls=[boton, progreso]),
            estado_txt,
            actual,
            dias,
            fuente,
        ],
    )
