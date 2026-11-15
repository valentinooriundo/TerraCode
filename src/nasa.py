from datetime import date
from functools import lru_cache
from time import monotonic
import httpx
from urllib.parse import urlsplit

METRICS = {
    "T2M": "Temperatura media del aire",
    "T2M_MIN": "Temperatura mínima del aire",
    "T2M_MAX": "Temperatura máxima del aire",
    "PRECTOTCORR": "Precipitación",
    "RH2M": "Humedad relativa del aire",
    "ALLSKY_SFC_SW_DWN": "Radiación solar",
    "WS2M": "Viento a 2 m",
}
BLUE_MARBLE = (
    "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
    "BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg"
)


_client = httpx.Client(
    timeout=httpx.Timeout(10, connect=4),
    transport=httpx.HTTPTransport(retries=1),
    limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
)


@lru_cache(maxsize=16)
def preview_image(url):
    host = urlsplit(url)
    if host.scheme != "https" or not host.hostname or not host.hostname.endswith(".earthdatacloud.nasa.gov"):
        raise ValueError("Origen de imagen no admitido")
    with _client.stream("GET", url) as response:
        response.raise_for_status()
        if not response.headers.get("content-type", "").startswith("image/"):
            raise ValueError("NASA no devolvió una imagen")
        image = bytearray()
        for chunk in response.iter_bytes():
            image.extend(chunk)
            if len(image) > 3_000_000:
                raise ValueError("Vista previa demasiado grande")
    return bytes(image)


@lru_cache(maxsize=128)
def _fetch(endpoint, parameters, cache_window):
    response = _client.get(endpoint, params=parameters)
    response.raise_for_status()
    return response.json()


def climate(lat, lon, start, end):
    return _fetch("https://power.larc.nasa.gov/api/temporal/daily/point", (
        ("latitude", round(lat, 4)), ("longitude", round(lon, 4)),
        ("community", "AG"), ("parameters", ",".join(METRICS)),
        ("start", start.strftime("%Y%m%d")), ("end", end.strftime("%Y%m%d")),
        ("format", "JSON"), ("time-standard", "UTC"),
    ), int(monotonic() // 900))


def scenes(lat, lon, start, end):
    result = _fetch("https://cmr.earthdata.nasa.gov/search/granules.json", (
        ("point", f"{lon},{lat}"), ("collection_concept_id", "C2076090826-LPCLOUD"),
        ("temporal", f"{start}T00:00:00Z,{end}T23:59:59Z"),
        ("page_size", 12), ("sort_key[]", "-start_date"),
    ), int(monotonic() // 900))
    return result["feed"].get("entry", [])


def daily(data, metric):
    fill = data.get("header", {}).get("fill_value", -999)
    return [
        (date(int(key[:4]), int(key[4:6]), int(key[6:])), value if value != fill else None)
        for key, value in sorted(data["properties"]["parameter"].get(metric, {}).items())
    ]


def dry_spell(values):
    previous = None
    count = longest = 0
    for day, value in values:
        if previous is None or (day - previous).days != 1:
            count = 0
        count = count + 1 if value is not None and value < 1 else 0
        longest = max(count, longest)
        previous = day
    return longest

SOIL_METRICS = {
    "GWETTOP": "Humedad relativa superficial del suelo",
    "GWETROOT": "Humedad relativa de la zona radicular",
}


def soil(lat, lon, start, end):
    return _fetch(
        "https://power.larc.nasa.gov/api/temporal/daily/point",
        (
            ("latitude", round(lat, 4)),
            ("longitude", round(lon, 4)),
            ("community", "AG"),
            ("parameters", ",".join(SOIL_METRICS)),
            ("start", start.strftime("%Y%m%d")),
            ("end", end.strftime("%Y%m%d")),
            ("format", "JSON"),
            ("time-standard", "UTC"),
        ),
        int(monotonic() // 900),
    )
