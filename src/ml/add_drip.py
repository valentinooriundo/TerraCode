from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import rasterio

from .expand_dataset import (
    CROPS,
    download_raster,
)

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data/processed"

DRIP_CROPS = [
    "phb",
    "car",
    "cit",
    "coc",
    "cof",
    "olv",
    "oni",
    "tom",
]

base = pd.read_csv(
    PROCESSED / "crop_dataset_v3_regional.csv"
)

points = base.drop_duplicates(
    subset=["latitude", "longitude"]
)

records = points.to_dict("records")

coordinates = [
    (row["longitude"], row["latitude"])
    for row in records
]

new_rows = []

with httpx.Client(
    timeout=120,
    follow_redirects=True,
) as client:

    for code in DRIP_CROPS:

        print(f"Procesando goteo: {CROPS[code]}")

        filename = f"sxHd_{code}.tif"

        path = download_raster(
            client,
            filename,
        )

        count = 0

        with rasterio.open(path) as raster:

            if raster.crs.to_epsg() != 4326:
                raise ValueError("CRS inesperado")

            samples = raster.sample(
                coordinates,
                masked=True,
            )

            for row, sample in zip(records, samples):

                value = sample[0]

                if np.ma.is_masked(value):
                    continue

                if not np.isfinite(value):
                    continue

                if not 0 <= value <= 10000:
                    continue

                new_row = row.copy()

                new_row["crop_code"] = code
                new_row["crop"] = CROPS[code]

                new_row["water_supply"] = (
                    "irrigated_drip"
                )

                new_row["suitability"] = (
                    float(value) / 100
                )

                new_rows.append(new_row)

                count += 1

        print(f"Registros válidos: {count}")

result = pd.concat(
    [base, pd.DataFrame(new_rows)],
    ignore_index=True,
)

result = result.drop_duplicates(
    subset=[
        "latitude",
        "longitude",
        "crop_code",
        "water_supply",
    ]
)

output = PROCESSED / "crop_dataset_v4.csv"

result.to_csv(output, index=False)

print("\nDATASET V4 GENERADO")
print(result.groupby("water_supply").size())
print(f"Total: {len(result)}")
print(f"Archivo: {output}")