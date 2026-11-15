"""Historial: resumen de mis registros de campo (por cultivo, zona, mes y riego) y línea de tiempo."""

import asyncio
from collections import Counter
from datetime import datetime
from typing import Callable

import flet as ft

import theme
from services import campo_service
from services.api_client import ApiClient, ApiError, SesionExpirada
from services.campo_service import TIPOS_RIEGO

TAMANO_PAGINA = 100
MAX_PAGINAS = 10  # resumen de hasta 1000 registros
MAX_BARRAS = 6
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"]


def _fecha(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def _agrupar(conteo: Counter) -> list[tuple[str, int]]:
    """Los más frecuentes; el resto se suma en 'Otros' para no pasar de MAX_BARRAS."""
    top = conteo.most_common()
    if len(top) <= MAX_BARRAS:
        return top
    return top[:MAX_BARRAS - 1] + [("Otros", sum(n for _, n in top[MAX_BARRAS - 1:]))]


def _ultimos_meses(fechas: list[datetime], cantidad: int = 6) -> list[tuple[str, int]]:
    hoy = datetime.now()
    claves = []
    anio, mes = hoy.year, hoy.month
    for _ in range(cantidad):
        claves.append((anio, mes))
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    conteo = Counter((f.year, f.month) for f in fechas)
    return [(f"{MESES[m - 1]} {str(a)[2:]}", conteo.get((a, m), 0)) for a, m in reversed(claves)]


def build_historial_view(
    page: ft.Page,
    api: ApiClient,
    on_back: Callable[[], None],
    on_nuevo: Callable[[], None],
    on_session_expired: Callable[[], None],
) -> ft.Control:
    progreso = ft.ProgressRing(width=22, height=22, stroke_width=2)
    contenido = ft.Column(spacing=16)
    subtitulo = ft.Text("Cargando…", size=13, color=theme.TEXT_MUTED)

    def notify(msg: str, color: str | None = None):
        page.show_dialog(ft.SnackBar(content=ft.Text(msg, color=theme.TEXT_ON_PRIMARY), bgcolor=color or theme.PRIMARY))

    def tarjeta(*controles, titulo: str | None = None) -> ft.Control:
        return ft.Container(
            padding=16,
            border_radius=16,
            bgcolor=theme.BG_SURFACE,
            border=ft.Border.all(1, theme.BORDER_SUBTLE),
            content=ft.Column(spacing=12, controls=[
                *([ft.Text(titulo, size=15, weight=ft.FontWeight.W_600, color=theme.TEXT_MAIN)] if titulo else []),
                *controles,
            ]),
        )

    def indicador(icono, valor: str, etiqueta: str) -> ft.Control:
        return ft.Container(
            col={"xs": 6, "md": 3},
            padding=14,
            border_radius=16,
            bgcolor=theme.BG_SURFACE,
            border=ft.Border.all(1, theme.BORDER_SUBTLE),
            content=ft.Column(spacing=4, controls=[
                ft.Icon(icono, size=20, color=theme.PRIMARY_HOVER),
                ft.Text(valor, size=24, weight=ft.FontWeight.BOLD, color=theme.TEXT_MAIN),
                ft.Text(etiqueta, size=12, color=theme.TEXT_MUTED),
            ]),
        )

    def barras(datos: list[tuple[str, int]], total: int) -> ft.Control:
        """Barras horizontales de una sola serie: un solo tono, sin leyenda; el número va en texto neutro."""
        maximo = max((n for _, n in datos), default=0) or 1
        filas = []
        for etiqueta, n in datos:
            porcentaje = n / total * 100 if total else 0
            filas.append(ft.Column(spacing=4, controls=[
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                    ft.Text(etiqueta, size=13, color=theme.TEXT_MAIN, expand=True, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"{n}", size=13, weight=ft.FontWeight.W_600, color=theme.TEXT_MAIN),
                ]),
                ft.Container(
                    tooltip=f"{etiqueta}: {n} registro{'s' if n != 1 else ''} ({porcentaje:.0f}%)",
                    content=ft.ProgressBar(value=n / maximo, height=8, border_radius=4,
                                           color=theme.PRIMARY_HOVER, bgcolor=theme.PRIMARY_LIGHT),
                ),
            ]))
        return ft.Column(spacing=10, controls=filas)

    def columnas_mes(datos: list[tuple[str, int]]) -> ft.Control:
        maximo = max((n for _, n in datos), default=0) or 1
        alto = 90
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            vertical_alignment=ft.CrossAxisAlignment.END,
            controls=[
                ft.Column(spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                    ft.Text(f"{n}" if n else "", size=11, color=theme.TEXT_MUTED),
                    ft.Container(width=22, height=max(n / maximo * alto, 2), bgcolor=theme.PRIMARY_HOVER if n
                                 else theme.BORDER_SUBTLE, border_radius=ft.BorderRadius.only(top_left=4, top_right=4),
                                 tooltip=f"{mes}: {n} registro{'s' if n != 1 else ''}"),
                    ft.Text(mes, size=11, color=theme.TEXT_MUTED),
                ])
                for mes, n in datos
            ],
        )

    def linea_tiempo(registros: list[dict]) -> ft.Control:
        filas = []
        for i, r in enumerate(registros):
            f = _fecha(r.get("fechaRegistro"))
            zona = (r.get("zona") or {}).get("descripcion") or "Zona no identificada"
            ultimo = i == len(registros) - 1
            filas.append(ft.Row(spacing=12, vertical_alignment=ft.CrossAxisAlignment.START, controls=[
                ft.Column(spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                    ft.Container(width=12, height=12, border_radius=6, bgcolor=theme.PRIMARY_HOVER,
                                 margin=ft.Margin.only(top=3)),
                    *([] if ultimo else [ft.Container(width=2, height=40, bgcolor=theme.BORDER_SUBTLE)]),
                ]),
                ft.Column(spacing=2, expand=True, controls=[
                    ft.Text(r.get("cultivoDescripcion") or "", size=14, weight=ft.FontWeight.W_600,
                            color=theme.TEXT_MAIN),
                    ft.Text(zona, size=12, color=theme.TEXT_MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ]),
                ft.Text(f.strftime("%d/%m/%Y") if f else "", size=12, color=theme.TEXT_MUTED),
            ]))
        return ft.Column(spacing=0, controls=filas)

    def vacio() -> ft.Control:
        return ft.Container(padding=24, alignment=ft.Alignment.CENTER, content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8, controls=[
                ft.Icon(ft.Icons.INSIGHTS, size=48, color=theme.BORDER_SUBTLE),
                ft.Text("Aún no hay registros para resumir", color=theme.TEXT_MUTED),
                ft.Button(content="Registrar mi primera parcela", bgcolor=theme.PRIMARY,
                          color=theme.TEXT_ON_PRIMARY, on_click=lambda e: on_nuevo()),
            ]))

    def pintar(registros: list[dict], total_servidor: int):
        activos = [r for r in registros if r.get("estado", True)]
        anulados = len(registros) - len(activos)
        n = len(activos)
        subtitulo.value = f"{n} registro{'s' if n != 1 else ''} activo{'s' if n != 1 else ''}" + (
            f" · {anulados} anulado{'s' if anulados != 1 else ''}" if anulados else "")
        if total_servidor > len(registros):
            subtitulo.value += f" · resumen de los últimos {len(registros)}"
        if not activos:
            contenido.controls = [vacio()]
            return

        cultivos = Counter(r.get("cultivoDescripcion") or "Sin cultivo" for r in activos)
        zonas = Counter((r.get("zona") or {}).get("departamento") or "Sin identificar" for r in activos)
        riegos = Counter(TIPOS_RIEGO.get(r.get("tipoRiego"), r.get("tipoRiego") or "—") for r in activos)
        fechas = [f for f in (_fecha(r.get("fechaRegistro")) for r in activos) if f]
        puntajes = [r["puntaje"] for r in activos if r.get("puntaje") is not None]
        sugeridos = sum(1 for r in activos if r.get("sugerido"))

        contenido.controls = [
            ft.ResponsiveRow(spacing=12, run_spacing=12, controls=[
                indicador(ft.Icons.FACT_CHECK_OUTLINED, str(n), "Registros activos"),
                indicador(ft.Icons.GRASS, str(len(cultivos)), "Cultivos distintos"),
                indicador(ft.Icons.PLACE_OUTLINED, str(len([z for z in zonas if z != "Sin identificar"])),
                          "Departamentos"),
                indicador(ft.Icons.INSIGHTS, f"{sum(puntajes) / len(puntajes):.0f}" if puntajes else "–",
                          "Aptitud promedio /100"),
            ]),
            tarjeta(columnas_mes(_ultimos_meses(fechas)), titulo="Registros por mes"),
            tarjeta(barras(_agrupar(cultivos), n), titulo="Por cultivo"),
            tarjeta(barras(_agrupar(zonas), n), titulo="Por departamento"),
            tarjeta(barras(_agrupar(riegos), n),
                    ft.Text(f"Elegiste el cultivo sugerido en {sugeridos} de {n} registros "
                            f"({sugeridos / n * 100:.0f}%).", size=12, color=theme.TEXT_MUTED),
                    titulo="Por tipo de riego"),
            tarjeta(linea_tiempo(activos[:8]), titulo="Actividad reciente"),
        ]

    async def cargar(e=None):
        progreso.visible = True
        page.update()
        registros: list[dict] = []
        total = 0
        try:
            for pagina in range(MAX_PAGINAS):
                data = await asyncio.to_thread(campo_service.listar, api, pagina, TAMANO_PAGINA)
                registros.extend(data.get("content") or [])
                total = data.get("totalElements", len(registros))
                if data.get("last", True):
                    break
        except SesionExpirada as ex:
            notify(str(ex), theme.DANGER)
            on_session_expired()
            return
        except ApiError as ex:
            notify(str(ex), theme.DANGER)
            subtitulo.value = "No se pudo cargar el resumen"
            return
        finally:
            progreso.visible = False
            page.update()
        pintar(registros, total)
        page.update()

    vista = ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=16,
        controls=[
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Row(controls=[
                    ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=theme.PRIMARY, tooltip="Volver",
                                  on_click=lambda e: on_back()),
                    ft.Column(spacing=0, controls=[
                        ft.Text("Historial", size=20, weight=ft.FontWeight.BOLD, color=theme.TEXT_MAIN),
                        subtitulo,
                    ]),
                ]),
                ft.Row(spacing=4, controls=[
                    progreso,
                    ft.IconButton(icon=ft.Icons.REFRESH, icon_color=theme.PRIMARY, tooltip="Actualizar",
                                  on_click=cargar),
                ]),
            ]),
            contenido,
        ],
    )
    page.run_task(cargar)
    return vista
