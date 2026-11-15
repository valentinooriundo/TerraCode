from pathlib import Path

import httpx
import rasterio
import numpy as np

from .predictor import recommend
from .expand_dataset import download_raster

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw"

# Coordenadas de la parcela de tu prueba
LAT = -14.18337
LON = -75.65874

data = recommend(
    LAT,
    LON,
    water_supply="irrigated_gravity",
)

print("\nDIAGNÓSTICO AGRÍCOLA - ICA")
print("-" * 60)

print(
    f"{'Cultivo':<20}"
    f"{'Random Forest':>15}"
    f"{'FAO GAEZ':>15}"
)

with httpx.Client(
    timeout=120,
    follow_redirects=True,
) as client:

    for item in data["recommendations"]:

        code = item["code"]
        filename = f"sxHg_{code}.tif"

        path = next(
            RAW.rglob(filename),
            None,
        )

        if path is None:
            path = download_raster(
                client, filename
            )

        with rasterio.open(path) as raster:

            sample = next(
                raster.sample(
                    [(LON, LAT)],
                    masked=True,
                )
            )[0]

            if (
                np.ma.is_masked(sample)
                or not 0 <= sample <= 10000
            ):
                reference = "Sin datos"
            else:
                reference = f"{float(sample) / 100:.2f}"

        print(
            f"{item['crop']:<20}"
            f"{item['score']:>15.2f}"
            f"{reference:>15}"
        )