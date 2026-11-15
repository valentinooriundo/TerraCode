from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform


ROOT = Path(__file__).resolve().parents[2]

AVOCADO_PATH = ROOT / "data" / "gaez_v5" / "avocado_irrigated.tif"


def avocado_suitability(lat, lon):

    with rasterio.open(AVOCADO_PATH) as dataset:

        xs, ys = transform(
            "EPSG:4326",
            dataset.crs,
            [lon],
            [lat]
        )

        row, col = dataset.index(xs[0], ys[0])

        if not (
            0 <= row < dataset.height
            and 0 <= col < dataset.width
        ):
            return None

        value = next(
            dataset.sample(
                [(xs[0], ys[0])],
                masked=True
            )
        )[0]

        if np.ma.is_masked(value):
            return None

        raw = float(value)

        if not 0 <= raw <= 10000:
            return None

        return round(raw / 100, 2)


if __name__ == "__main__":

    locations = {
        "Ica": (-14.06, -75.73),
        "San Juan Bautista": (-14.02346, -75.71921),
        "Santiago": (-14.18269, -75.72305),
        "Pachacútec": (-14.18337, -75.65874),
    }

    print("DIAGNÓSTICO DE PALTA - FAO GAEZ V5")
    print("-" * 45)

    for name, (lat, lon) in locations.items():

        score = avocado_suitability(lat, lon)

        if score is None:
            print(f"{name}: Sin datos")
        else:
            print(f"{name}: {score:.2f}/100")