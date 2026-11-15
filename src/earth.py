"""Orthographic view of NASA Blue Marble rendered for the Flet welcome screen."""

from functools import lru_cache
from io import BytesIO
from math import asin, atan2, cos, pi, radians, sin, sqrt
from urllib.request import urlopen

from PIL import Image

TEXTURE = (
    "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?"
    "SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=BlueMarble_NextGeneration"
    "&STYLES=&SRS=EPSG:4326&BBOX=-180,-90,180,90&WIDTH=4096&HEIGHT=2048&FORMAT=image/jpeg"
)


@lru_cache(maxsize=1)
def texture():
    with urlopen(TEXTURE, timeout=12) as response:
        return Image.open(BytesIO(response.read())).convert("RGB")


@lru_cache(maxsize=12)
def render(longitude, latitude=8, size=640):
    source = texture()
    pixels = source.load()
    result = Image.new("RGBA", (size, size))
    target = result.load()
    angle = radians(latitude)
    tilt_sin, tilt_cos = sin(angle), cos(angle)
    heading = radians(longitude)
    for row in range(size):
        y = 1 - (row + .5) * 2 / size
        for column in range(size):
            x = (column + .5) * 2 / size - 1
            distance = x * x + y * y
            if distance >= 1:
                continue
            z = sqrt(1 - distance)
            lat = asin(y * tilt_cos + z * tilt_sin)
            lon = heading + atan2(x, z * tilt_cos - y * tilt_sin)
            u = int(((lon + pi) / (2 * pi) % 1) * source.width)
            v = min(source.height - 1, int((.5 - lat / pi) * source.height))
            shade = min(1, .60 + .44 * z - .14 * x + .08 * y)
            target[column, row] = (*[int(c * shade) for c in pixels[u, v]], 255)
    output = BytesIO()
    result.save(output, format="PNG")
    return output.getvalue()
