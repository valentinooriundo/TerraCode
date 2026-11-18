"""Mis registros de campo: listado paginado, ver en el mapa y anular."""

import asyncio
from datetime import datetime
from typing import Callable

import flet as ft

import theme
from services import campo_service
from services.api_client import ApiClient, ApiError, SesionExpirada
from services.campo_service import TIPOS_RIEGO

TAMANO_PAGINA = 20


def _fecha(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


def build_registros_view(
    page: ft.Page,
    api: ApiClient,
    on_back: Callable[[], None],
    on_nuevo: Callable[[], None],
    on_session_expired: Callable[[], None],
) -> ft.Control:
    estado: dict = {"pagina": 0, "ultima": True, "cargando": False}
    lista = ft.Column(spacing=12)
    resumen = ft.Text("", size=13, color=theme.TEXT_MUTED)
    progreso = ft.ProgressRing(width=22, height=22, stroke_width=2, visible=False)
    vacio = ft.Container(
        visible=False,
        padding=24,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.Icon(ft.Icons.AGRICULTURE, size=48, color=theme.BORDER_SUBTLE),
                ft.Text("Aún no tienes registros", color=theme.TEXT_MUTED),
                ft.Button(content="Registrar mi primera parcela", bgcolor=theme.PRIMARY, color=theme.TEXT_ON_PRIMARY,
                          on_click=lambda e: on_nuevo()),
            ],
        ),
    )

    def notify(msg: str, color: str | None = None):
        page.show_dialog(ft.SnackBar(content=ft.Text(msg, color=theme.TEXT_ON_PRIMARY), bgcolor=color or theme.PRIMARY))

    async def ver_mapa(r: dict):
        await ft.UrlLauncher().launch_url(f"https://www.google.com/maps/search/?api=1&query={r['latitud']},{r['longitud']}")

    def confirmar_anular(r: dict):
        async def anular(e):
            page.pop_dialog()
            try:
                await asyncio.to_thread(campo_service.anular, api, r["id"])
            except SesionExpirada as ex:
                notify(str(ex), theme.DANGER)
                on_session_expired()
                return
            except ApiError as ex:
                notify(str(ex), theme.DANGER)
                return
            notify("Registro anulado")
            await recargar()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("¿Anular registro?"),
            content=ft.Text(f"{r['cultivoDescripcion']} · {_fecha(r.get('fechaRegistro'))}\n"
                            "El registro se conserva como anulado y no se puede reactivar."),
            actions=[
                ft.TextButton(content="Cancelar", on_click=lambda e: page.pop_dialog()),
                ft.TextButton(content="Anular", style=ft.ButtonStyle(color=theme.DANGER), on_click=anular),
            ],
        ))

    def tarjeta(r: dict) -> ft.Control:
        zona = (r.get("zona") or {}).get("descripcion") or "Zona no identificada"
        activo = r.get("estado", True)
        puntaje = r.get("puntaje")
        chips = [ft.Text(TIPOS_RIEGO.get(r.get("tipoRiego"), r.get("tipoRiego") or ""), size=12,
                         color=theme.TEXT_MUTED)]
        if puntaje is not None:
            chips.append(ft.Text(f"Aptitud {puntaje:.0f}/100", size=12, color=theme.PRIMARY_HOVER,
                                 weight=ft.FontWeight.W_600))
        if not activo:
            chips.append(ft.Text("ANULADO", size=12, color=theme.DANGER, weight=ft.FontWeight.BOLD))
        precision = r.get("precisionMetros")
        coordenadas = f"{r['latitud']:.5f}, {r['longitud']:.5f}" + (f" (±{precision:.0f} m)" if precision else "")

        acciones = [
            ft.IconButton(icon=ft.Icons.MAP_OUTLINED, icon_color=theme.PRIMARY_HOVER, tooltip="Ver en el mapa",
                          on_click=lambda e, r=r: page.run_task(ver_mapa, r)),
        ]
        if activo:
            acciones.append(ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=theme.DANGER, tooltip="Anular",
                                          on_click=lambda e, r=r: confirmar_anular(r)))

        return ft.Container(
            padding=16,
            border_radius=16,
            bgcolor=theme.BG_SURFACE,
            border=ft.Border.all(1, theme.BORDER_SUBTLE),
            opacity=1.0 if activo else 0.6,
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(spacing=8, expand=True, controls=[
                                ft.Icon(ft.Icons.GRASS, color=theme.PRIMARY_HOVER, size=20),
                                ft.Text(r["cultivoDescripcion"], size=16, weight=ft.FontWeight.BOLD,
                                        color=theme.TEXT_MAIN, expand=True),
                            ]),
                            ft.Row(spacing=0, controls=acciones),
                        ],
                    ),
                    ft.Row(spacing=6, controls=[ft.Icon(ft.Icons.PLACE_OUTLINED, size=16, color=theme.TEXT_MUTED),
                                                ft.Text(zona, size=13, color=theme.TEXT_MAIN, expand=True)]),
                    ft.Text(coordenadas, size=12, color=theme.TEXT_MUTED),
                    ft.Row(spacing=12, wrap=True, controls=chips),
                    *([ft.Text(r["observacion"], size=12, color=theme.TEXT_MUTED, italic=True)]
                      if r.get("observacion") else []),
                    ft.Text(_fecha(r.get("fechaRegistro")), size=11, color=theme.TEXT_MUTED),
                ],
            ),
        )

    boton_mas = ft.OutlinedButton(content="Cargar más", visible=False)

    async def cargar(reiniciar: bool):
        if estado["cargando"]:
            return
        estado["cargando"] = True
        progreso.visible = True
        boton_mas.visible = False
        page.update()
        pagina = 0 if reiniciar else estado["pagina"] + 1
        try:
            data = await asyncio.to_thread(campo_service.listar, api, pagina, TAMANO_PAGINA)
        except SesionExpirada as ex:
            notify(str(ex), theme.DANGER)
            on_session_expired()
            return
        except ApiError as ex:
            notify(str(ex), theme.DANGER)
            boton_mas.visible = not estado["ultima"]
            return
        finally:
            estado["cargando"] = False
            progreso.visible = False
            page.update()

        if reiniciar:
            lista.controls.clear()
        lista.controls.extend(tarjeta(r) for r in data.get("content") or [])
        estado["pagina"] = pagina
        estado["ultima"] = data.get("last", True)
        total = data.get("totalElements", 0)
        resumen.value = f"{total} registro{'s' if total != 1 else ''}"
        vacio.visible = total == 0
        boton_mas.visible = not estado["ultima"]
        page.update()

    async def recargar(e=None):
        await cargar(True)

    async def mas(e):
        await cargar(False)

    boton_mas.on_click = mas

    vista = ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=16,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(controls=[
                        ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=theme.PRIMARY, tooltip="Volver",
                                      on_click=lambda e: on_back()),
                        ft.Column(spacing=0, controls=[
                            ft.Text("Mis registros", size=20, weight=ft.FontWeight.BOLD, color=theme.TEXT_MAIN),
                            resumen,
                        ]),
                    ]),
                    ft.Row(spacing=0, controls=[
                        ft.IconButton(icon=ft.Icons.REFRESH, icon_color=theme.PRIMARY, tooltip="Actualizar",
                                      on_click=recargar),
                        ft.IconButton(icon=ft.Icons.ADD_LOCATION_ALT_OUTLINED, icon_color=theme.ACCENT,
                                      tooltip="Nuevo registro", on_click=lambda e: on_nuevo()),
                    ]),
                ],
            ),
            vacio,
            lista,
            ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[progreso, boton_mas]),
        ],
    )
    page.run_task(recargar)
    return vista
