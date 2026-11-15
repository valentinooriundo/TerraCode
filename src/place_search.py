"""Place-name search for the noncommercial TerraCode prototype."""

import json
from functools import lru_cache
from os import getenv
from urllib.parse import quote, urlencode
from urllib.request import urlopen

import httpx

from map_provider import google_requested

_google = httpx.Client(timeout=httpx.Timeout(7, connect=4))


def google_search_enabled():
    return google_requested() and bool(_places_key())


def _places_key():
    return (getenv("GOOGLE_PLACES_API_KEY") or getenv("GOOGLE_MAPS_API_KEY", "")).strip()


def google_places(query, token):
    response = _google.post(
        "https://places.googleapis.com/v1/places:autocomplete",
        headers={"X-Goog-Api-Key": _places_key(),
                 "X-Goog-FieldMask": "suggestions.placePrediction.placeId,suggestions.placePrediction.structuredFormat"},
        json={"input": query, "languageCode": "es", "sessionToken": token},
    )
    response.raise_for_status()
    matches = []
    for suggestion in response.json().get("suggestions", []):
        prediction = suggestion["placePrediction"]
        text = prediction["structuredFormat"]
        matches.append({"name": text["mainText"]["text"], "admin1": text.get("secondaryText", {}).get("text", ""),
                        "place_id": prediction["placeId"], "session_token": token})
    return matches


def google_location(place_id, token):
    response = _google.get(
        "https://places.googleapis.com/v1/places/" + quote(place_id, safe=""),
        params={"sessionToken": token, "languageCode": "es"},
        headers={"X-Goog-Api-Key": _places_key(), "X-Goog-FieldMask": "location"},
    )
    response.raise_for_status()
    location = response.json()["location"]
    return location["latitude"], location["longitude"]


def find_places(query):
    return _find_places(" ".join(query.casefold().split()))


@lru_cache(maxsize=96)
def _find_places(query):
    params = urlencode({"name": query, "count": 5, "language": "es", "format": "json"})
    with urlopen(f"https://geocoding-api.open-meteo.com/v1/search?{params}", timeout=7) as response:
        return json.load(response).get("results", [])
