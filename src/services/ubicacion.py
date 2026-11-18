"""Ubicación actual del celular (o del navegador en la versión web) con flet-geolocator."""

import asyncio
import logging
from dataclasses import dataclass
from math import isfinite

import flet as ft
import flet_geolocator as gps

log = logging.getLogger(__name__)

TIMEOUT_GPS = 25


@dataclass
class Posicion:
    latitud: float
    longitud: float
    precision: float | None
    simulada: bool


class UbicacionError(Exception):
    """Mensaje listo para mostrar."""


async def obtener(page: ft.Page, geo: gps.Geolocator) -> Posicion:
    try:
        if not page.web:
            await asyncio.wait_for(geo.request_permission(), timeout=15)
        configuracion = gps.GeolocatorWebConfiguration(
            accuracy=gps.GeolocatorPositionAccuracy.HIGH,
            time_limit=ft.Duration(seconds=TIMEOUT_GPS),
            maximum_age=ft.Duration(seconds=0),
        ) if page.web else None
        p = await asyncio.wait_for(geo.get_current_position(configuracion), timeout=TIMEOUT_GPS + 2)
    except TimeoutError as e:
        raise UbicacionError("El GPS no respondió a tiempo. Sal a cielo abierto y reintenta.") from e
    except Exception as e:  # el plugin reporta permisos denegados o GPS apagado como excepción
        log.warning("Geolocalización: %s", e)
        motivo = str(e).lower()
        if "denied" in motivo or "permission" in motivo:
            raise UbicacionError("Permite el acceso a la ubicación para TerraCode y reintenta.") from e
        if "disabled" in motivo or "service" in motivo:
            raise UbicacionError("Activa la ubicación (GPS) del celular y reintenta.") from e
        raise UbicacionError("No se pudo obtener la ubicación. Reintenta.") from e

    if (p is None or p.latitude is None or p.longitude is None
            or not -90 <= p.latitude <= 90 or not -180 <= p.longitude <= 180):
        raise UbicacionError("El GPS devolvió una ubicación no válida. Reintenta.")
    precision = p.accuracy if p.accuracy is not None and isfinite(p.accuracy) and p.accuracy >= 0 else None
    return Posicion(p.latitude, p.longitude, precision, bool(p.mocked))
