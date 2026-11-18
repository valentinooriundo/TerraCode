"""Pronóstico del tiempo con Open-Meteo (https://open-meteo.com): gratis y sin clave.

Plan gratuito: uso no comercial y hasta 10 000 consultas al día. Si TerraCode pasa a uso comercial, contratar el
plan de pago o cambiar de proveedor.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from services.auth_service import _SSL

URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 15

# Códigos WMO de Open-Meteo → (descripción, icono de Material)
TIEMPO = {
    0: ("Despejado", "WB_SUNNY"),
    1: ("Mayormente despejado", "WB_SUNNY"),
    2: ("Parcialmente nublado", "WB_CLOUDY"),
    3: ("Nublado", "CLOUD"),
    45: ("Niebla", "FOGGY"),
    48: ("Niebla con escarcha", "FOGGY"),
    51: ("Llovizna ligera", "GRAIN"),
    53: ("Llovizna", "GRAIN"),
    55: ("Llovizna intensa", "GRAIN"),
    56: ("Llovizna helada", "AC_UNIT"),
    57: ("Llovizna helada intensa", "AC_UNIT"),
    61: ("Lluvia ligera", "WATER_DROP"),
    63: ("Lluvia", "WATER_DROP"),
    65: ("Lluvia intensa", "WATER_DROP"),
    66: ("Lluvia helada", "AC_UNIT"),
    67: ("Lluvia helada intensa", "AC_UNIT"),
    71: ("Nevada ligera", "AC_UNIT"),
    73: ("Nevada", "AC_UNIT"),
    75: ("Nevada intensa", "AC_UNIT"),
    77: ("Granizo fino", "AC_UNIT"),
    80: ("Chubascos ligeros", "UMBRELLA"),
    81: ("Chubascos", "UMBRELLA"),
    82: ("Chubascos fuertes", "UMBRELLA"),
    85: ("Chubascos de nieve", "AC_UNIT"),
    86: ("Chubascos de nieve fuertes", "AC_UNIT"),
    95: ("Tormenta", "THUNDERSTORM"),
    96: ("Tormenta con granizo", "THUNDERSTORM"),
    99: ("Tormenta con granizo fuerte", "THUNDERSTORM"),
}

DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


class ClimaError(Exception):
    """Mensaje listo para mostrar."""


def tiempo(codigo) -> tuple[str, str]:
    return TIEMPO.get(int(codigo) if codigo is not None else -1, ("Sin dato", "HELP_OUTLINE"))


def pronostico(latitud: float, longitud: float) -> dict:
    """Condiciones actuales y 7 días. Bloqueante: llamar con ``asyncio.to_thread``.

    Devuelve {"actual": {...}, "dias": [{"fecha", "dia", "codigo", "max", "min", "lluvia_mm", "prob_lluvia",
    "viento_max"}], "zona_horaria"}.
    """
    params = {
        "latitude": round(latitud, 4),
        "longitude": round(longitud, 4),
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,"
                   "wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "precipitation_probability_max,wind_speed_10m_max",
        "timezone": "auto",
        "forecast_days": 7,
    }
    url = f"{URL}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT, context=_SSL) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise ClimaError("No se pudo obtener el pronóstico. Revisa tu conexión e intenta nuevamente") from e

    try:
        c = data["current"]
        d = data["daily"]
        dias = []
        for i, fecha in enumerate(d["time"]):
            f = date.fromisoformat(fecha)
            dias.append({
                "fecha": f,
                "dia": "Hoy" if i == 0 else DIAS[f.weekday()],
                "codigo": d["weather_code"][i],
                "max": d["temperature_2m_max"][i],
                "min": d["temperature_2m_min"][i],
                "lluvia_mm": d["precipitation_sum"][i],
                "prob_lluvia": d["precipitation_probability_max"][i],
                "viento_max": d["wind_speed_10m_max"][i],
            })
        return {
            "actual": {
                "temperatura": c["temperature_2m"],
                "sensacion": c.get("apparent_temperature"),
                "humedad": c["relative_humidity_2m"],
                "lluvia_mm": c["precipitation"],
                "viento": c["wind_speed_10m"],
                "codigo": c["weather_code"],
            },
            "dias": dias,
            "zona_horaria": data.get("timezone"),
        }
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise ClimaError("El servicio del clima devolvió datos incompletos") from e
