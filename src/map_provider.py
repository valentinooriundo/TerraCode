"""Basemap configuration shared by the Flet map."""

import json
from functools import lru_cache
from os import getenv
from pathlib import Path
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OSM_CREDIT = "© OpenStreetMap contributors"
TOPO_URL = "https://a.tile.opentopomap.org/{z}/{x}/{y}.png"
TOPO_CREDIT = "© OpenStreetMap · SRTM, Sonny · © OpenTopoMap (CC BY-SA)"


def google_requested():
    return getenv("MAP_PROVIDER", "OpenStreetMap").strip().casefold() == "google"


def google_tiles():
    key = getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        raise ValueError("Falta GOOGLE_MAPS_API_KEY")
    return _google_session(key, getenv("GOOGLE_MAPS_REGION", "PE"), int(monotonic() // 3600))


@lru_cache(maxsize=4)
def _google_session(key, region, cache_window):
    request = Request(
        "https://tile.googleapis.com/v1/createSession?" + urlencode({"key": key}),
        data=json.dumps({"mapType": "roadmap", "language": "es-PE",
                         "region": region}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=8) as response:
        session = json.load(response)["session"]
    credentials = urlencode({"key": key, "session": session})
    return "https://tile.googleapis.com/v1/2dtiles/{z}/{x}/{y}?" + credentials, credentials


def google_credit(credentials, zoom, north, south, east, west):
    bounds = urlencode(dict(zoom=zoom, north=north, south=south, east=east, west=west))
    with urlopen(f"https://tile.googleapis.com/tile/v1/viewport?{credentials}&{bounds}", timeout=6) as response:
        return json.load(response)["copyright"]
