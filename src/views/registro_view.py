"""Nuevo registro de campo: ubicación GPS → zona y cultivos recomendados por el modelo → guardar."""

import asyncio
import logging
from math import isfinite
from typing import Callable

import flet as ft
import flet_geolocator as gps

import theme
from services import campo_service
from services.api_client import ApiClient, ApiError, SesionExpirada
from services.campo_service import TIPOS_RIEGO

log = logging.getLogger(__name__)

# Por encima de este margen, el punto puede caer fuera de la parcela
PRECISION_RECOMENDADA = 50
TIMEOUT_GPS = 25
OTRO = "__otro__"
MAX_CULTIVOS = 8


def _posicion_valida(p) -> bool:
    return (
        p is not None
        and p.latitude is not None and -90 <= p.latitude <= 90
        and p.longitude is not None and -180 <= p.longitude <= 180
        and (p.accuracy is None or (isfinite(p.accuracy) and p.accuracy >= 0))
    )


def _tarjeta(titulo: str, icono, *controles: ft.Control) -> ft.Container:
    return ft.Container(
        padding=16,
        border_radius=16,
        bgcolor=theme.BG_SURFACE,
        border=ft.Border.all(1, theme.BORDER_SUBTLE),
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(icono, color=theme.PRIMARY_HOVER, size=20),
                        ft.Text(titulo, size=16, weight=ft.FontWeight.W_600, color=theme.TEXT_MAIN),
                    ],
                ),
                *controles,
            ],
        ),
    )


def build_registro_view(
    page: ft.Page,
    api: ApiClient,
    geo: gps.Geolocator,
    on_back: Callable[[], None],
    on_saved: Callable[[], None],
    on_session_expired: Callable[[], None],
) -> ft.Control:
    estado: dict = {"posicion": None, "recomendacion": None, "ocupado": False}

    def notify(msg: str, color: str | None = None):
        page.show_dialog(ft.SnackBar(content=ft.Text(msg, color=theme.TEXT_ON_PRIMARY), bgcolor=color or theme.PRIMARY))

    # ---------- Ubicación ----------

    ubicacion_texto = ft.Text("Aún no se obtuvo la ubicación", color=theme.TEXT_MUTED, size=13)
    precision_aviso = ft.Text("", size=12, color=theme.ACCENT_DARK, visible=False)
    gps_progreso = ft.ProgressRing(width=18, height=18, stroke_width=2, visible=False)

    async def obtener_ubicacion(e):
        if estado["ocupado"]:
            return
        estado["ocupado"] = True
        boton_gps.disabled = True
        gps_progreso.visible = True
        ubicacion_texto.value = "Buscando ubicación… Si aparece el permiso, elige Permitir."
        ubicacion_texto.color = theme.TEXT_MUTED
        precision_aviso.visible = False
        page.update()
        try:
            if not page.web:
                await asyncio.wait_for(geo.request_permission(), timeout=15)
            configuracion = gps.GeolocatorWebConfiguration(
                accuracy=gps.GeolocatorPositionAccuracy.HIGH,
                time_limit=ft.Duration(seconds=TIMEOUT_GPS),
                maximum_age=ft.Duration(seconds=0),
            ) if page.web else None
            posicion = await asyncio.wait_for(geo.get_current_position(configuracion), timeout=TIMEOUT_GPS + 2)
        except TimeoutError:
            ubicacion_texto.value = "El GPS no respondió a tiempo. Sal a cielo abierto y reintenta."
            ubicacion_texto.color = theme.DANGER
            return
        except Exception as error:  # el plugin reporta permisos denegados o GPS apagado como excepción
            log.warning("Geolocalización: %s", error)
            motivo = str(error).lower()
            if "denied" in motivo or "permission" in motivo:
                ubicacion_texto.value = "Permite el acceso a la ubicación para TerraCode y reintenta."
            elif "disabled" in motivo or "service" in motivo:
                ubicacion_texto.value = "Activa la ubicación (GPS) del celular y reintenta."
            else:
                ubicacion_texto.value = "No se pudo obtener la ubicación. Reintenta."
            ubicacion_texto.color = theme.DANGER
            return
        finally:
            estado["ocupado"] = False
            boton_gps.disabled = False
            gps_progreso.visible = False
            page.update()

        if not _posicion_valida(posicion):
            ubicacion_texto.value = "El GPS devolvió una ubicación no válida. Reintenta."
            ubicacion_texto.color = theme.DANGER
            page.update()
            return

        estado["posicion"] = posicion
        precision = posicion.accuracy
        margen = f" · margen ±{precision:.0f} m" if precision is not None else ""
        ubicacion_texto.value = f"{posicion.latitude:.6f}, {posicion.longitude:.6f}{margen}"
        ubicacion_texto.color = theme.TEXT_MAIN
        if posicion.mocked:
            precision_aviso.value = "El celular indica una ubicación simulada."
            precision_aviso.visible = True
        elif precision is not None and precision > PRECISION_RECOMENDADA:
            precision_aviso.value = "Ubicación poco precisa. Para mejorar, acércate al centro de la parcela y reintenta."
            precision_aviso.visible = True
        boton_gps.content = "Actualizar ubicación"
        limpiar_recomendacion()
        boton_analizar.disabled = False
        page.update()

    boton_gps = ft.Button(
        content="Obtener mi ubicación",
        icon=ft.Icons.MY_LOCATION,
        bgcolor=theme.PRIMARY,
        color=theme.TEXT_ON_PRIMARY,
        on_click=obtener_ubicacion,
    )

    # ---------- Tipo de riego ----------

    riego = ft.RadioGroup(
        value="SECANO",
        content=ft.Column(
            spacing=0,
            controls=[ft.Radio(value=codigo, label=texto) for codigo, texto in TIPOS_RIEGO.items()],
        ),
    )

    def cambio_riego(e):
        if estado["recomendacion"] is not None:
            limpiar_recomendacion()
            notify("Cambiaste el riego: vuelve a analizar para actualizar los cultivos.", theme.ACCENT_DARK)
        page.update()

    riego.on_change = cambio_riego

    # ---------- Análisis (zona + cultivos) ----------

    analisis_progreso = ft.Row(
        visible=False,
        spacing=10,
        controls=[
            ft.ProgressRing(width=18, height=18, stroke_width=2),
            ft.Text(
                "Analizando el clima histórico de la zona… puede tardar hasta un minuto la primera vez.",
                size=12, color=theme.TEXT_MUTED, expand=True,
            ),
        ],
    )
    zona_texto = ft.Text("", size=15, weight=ft.FontWeight.W_600, color=theme.TEXT_MAIN)
    zona_detalle = ft.Text("", size=12, color=theme.TEXT_MUTED)
    tarjeta_zona = _tarjeta("Zona", ft.Icons.PLACE_OUTLINED, zona_texto, zona_detalle)
    tarjeta_zona.visible = False

    cultivos_lista = ft.Column(spacing=4)
    cultivo_grupo = ft.RadioGroup(content=cultivos_lista)
    otro_cultivo = ft.TextField(label="¿Qué cultivo es?", max_length=100, visible=False)
    nota_modelo = ft.Text("", size=11, color=theme.TEXT_MUTED)

    def cambio_cultivo(e):
        otro_cultivo.visible = cultivo_grupo.value == OTRO
        page.update()

    cultivo_grupo.on_change = cambio_cultivo

    def fila_cultivo(c: dict, sugerido: bool) -> ft.Control:
        etiqueta = ft.Row(
            spacing=6,
            controls=[ft.Text(c["descripcion"], color=theme.TEXT_MAIN, weight=ft.FontWeight.W_500)]
            + ([ft.Container(
                content=ft.Text("Sugerido", size=10, color=theme.TEXT_ON_PRIMARY),
                bgcolor=theme.ACCENT, border_radius=8, padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            )] if sugerido else []),
        )
        return ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Radio(value=c["codigo"]),
                ft.Column(
                    expand=True,
                    spacing=4,
                    controls=[
                        etiqueta,
                        ft.ProgressBar(
                            value=max(0.0, min(1.0, c["puntaje"] / 100)),
                            color=theme.PRIMARY_HOVER, bgcolor=theme.PRIMARY_LIGHT,
                            bar_height=6, border_radius=3,
                        ),
                    ],
                ),
                ft.Text(f"{c['puntaje']:.0f}/100", size=12, color=theme.TEXT_MUTED, width=52,
                        text_align=ft.TextAlign.RIGHT),
            ],
        )

    def mostrar_cultivos(cultivos: list[dict]):
        cultivos_lista.controls = [fila_cultivo(c, i == 0) for i, c in enumerate(cultivos[:MAX_CULTIVOS])]
        cultivos_lista.controls.append(ft.Radio(value=OTRO, label="Otro cultivo"))
        cultivo_grupo.value = cultivos[0]["codigo"] if cultivos else OTRO
        otro_cultivo.visible = cultivo_grupo.value == OTRO

    def limpiar_recomendacion():
        estado["recomendacion"] = None
        tarjeta_zona.visible = False
        nota_modelo.value = "Sin análisis: escribe el cultivo o pulsa «Analizar cultivos» para ver los más aptos."
        mostrar_cultivos([])

    async def analizar(e):
        posicion = estado["posicion"]
        if posicion is None or estado["ocupado"]:
            return
        estado["ocupado"] = True
        boton_analizar.disabled = True
        boton_gps.disabled = True
        analisis_progreso.visible = True
        page.update()
        try:
            rec = await asyncio.to_thread(
                campo_service.recomendar, api, posicion.latitude, posicion.longitude, riego.value
            )
        except SesionExpirada as ex:
            notify(str(ex), theme.DANGER)
            on_session_expired()
            return
        except ApiError as ex:
            notify(str(ex), theme.DANGER)
            return
        finally:
            estado["ocupado"] = False
            boton_analizar.disabled = estado["posicion"] is None
            boton_gps.disabled = False
            analisis_progreso.visible = False
            page.update()

        estado["recomendacion"] = rec
        zona = rec.get("zona") or {}
        zona_texto.value = zona.get("descripcion") or "Zona no identificada"
        detalle = [f"{k}: {zona[c]}" for k, c in (("Distrito", "distrito"), ("Provincia", "provincia"),
                                                  ("Departamento", "departamento"), ("País", "pais")) if zona.get(c)]
        zona_detalle.value = " · ".join(detalle)
        tarjeta_zona.visible = True
        mostrar_cultivos(rec.get("cultivos") or [])
        nota_modelo.value = (
            f"Aptitud de 0 a 100 estimada con el clima {rec.get('periodoReferencia', '1981-2010')} "
            f"(margen de error ±{rec.get('errorMedio', 0):.0f} puntos). Elige el cultivo que tienes sembrado."
        )
        page.update()

    boton_analizar = ft.Button(
        content="Analizar cultivos",
        icon=ft.Icons.AUTO_AWESOME,
        bgcolor=theme.ACCENT,
        color=theme.TEXT_ON_PRIMARY,
        disabled=True,
        on_click=analizar,
    )

    # ---------- Guardar ----------

    observacion = ft.TextField(label="Observación (opcional)", multiline=True, min_lines=2, max_lines=4,
                               max_length=500)
    guardar_progreso = ft.ProgressRing(width=18, height=18, stroke_width=2, visible=False)

    def armar_registro() -> dict | None:
        posicion = estado["posicion"]
        if posicion is None:
            notify("Primero obtén la ubicación de la parcela.", theme.DANGER)
            return None
        rec = estado["recomendacion"] or {}
        cultivos = {c["codigo"]: c for c in rec.get("cultivos") or []}
        elegido = cultivo_grupo.value
        if elegido == OTRO or elegido not in cultivos:
            nombre = (otro_cultivo.value or "").strip()
            if not nombre:
                otro_cultivo.error_text = "Escribe el cultivo"
                otro_cultivo.visible = True
                page.update()
                return None
            otro_cultivo.error_text = None
            codigo, puntaje, sugerido = None, None, False
        else:
            c = cultivos[elegido]
            nombre, codigo, puntaje = c["descripcion"], c["codigo"], c["puntaje"]
            sugerido = elegido == (rec.get("cultivos") or [{}])[0].get("codigo")
        return {
            "latitud": posicion.latitude,
            "longitud": posicion.longitude,
            "precisionMetros": posicion.accuracy,
            "zona": rec.get("zona"),
            "tipoRiego": riego.value,
            "cultivoCodigo": codigo,
            "cultivoDescripcion": nombre,
            "puntaje": puntaje,
            "sugerido": sugerido,
            "observacion": (observacion.value or "").strip() or None,
        }

    async def guardar(e):
        if estado["ocupado"]:
            return
        registro = armar_registro()
        if registro is None:
            return
        estado["ocupado"] = True
        boton_guardar.disabled = True
        guardar_progreso.visible = True
        page.update()
        try:
            await asyncio.to_thread(campo_service.registrar, api, registro)
        except SesionExpirada as ex:
            notify(str(ex), theme.DANGER)
            on_session_expired()
            return
        except ApiError as ex:
            notify(str(ex), theme.DANGER)
            return
        finally:
            estado["ocupado"] = False
            boton_guardar.disabled = False
            guardar_progreso.visible = False
            page.update()
        notify(f"Registro guardado: {registro['cultivoDescripcion']}")
        on_saved()

    boton_guardar = ft.Button(
        content="Guardar registro",
        icon=ft.Icons.SAVE_OUTLINED,
        bgcolor=theme.PRIMARY,
        color=theme.TEXT_ON_PRIMARY,
        on_click=guardar,
        expand=True,
    )

    limpiar_recomendacion()

    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=16,
        controls=[
            ft.Row(
                controls=[
                    ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_color=theme.PRIMARY, tooltip="Volver",
                                  on_click=lambda e: on_back()),
                    ft.Text("Nuevo registro", size=20, weight=ft.FontWeight.BOLD, color=theme.TEXT_MAIN),
                ],
            ),
            _tarjeta(
                "Ubicación de la parcela", ft.Icons.GPS_FIXED,
                ubicacion_texto, precision_aviso,
                ft.Row(spacing=12, controls=[boton_gps, gps_progreso]),
            ),
            _tarjeta("Tipo de riego", ft.Icons.WATER_DROP_OUTLINED, riego,
                     ft.Row(controls=[boton_analizar]), analisis_progreso),
            tarjeta_zona,
            _tarjeta("Cultivo", ft.Icons.GRASS, nota_modelo, cultivo_grupo, otro_cultivo),
            _tarjeta("Observación", ft.Icons.NOTES, observacion),
            ft.Row(spacing=12, controls=[boton_guardar, guardar_progreso]),
        ],
    )
