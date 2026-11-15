from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[2]

RAW = ROOT / "data" / "raw" / "irrigation"
PROCESSED = ROOT / "data" / "processed"

BASE_URL = (
    "https://gaez-v4-data.fao.org/data/"
    "res05/CRUTS32/Hist/8110H/"
)

CROPS = {
    "mze": "Maíz",
    "phb": "Frijol",
    "wpo": "Papa",
}


def download_rasters():
    RAW.mkdir(parents=True, exist_ok=True)

    for code, name in CROPS.items():
        filename = f"sxHg_{code}.tif"
        path = RAW / filename

        if path.exists():
            continue

        print(f"Descargando riego: {name}")

        response = httpx.get(
            BASE_URL + filename,
            timeout=120,
            follow_redirects=True,
        )

        response.raise_for_status()
        path.write_bytes(response.content)


def build_dataset():
    base = pd.read_csv(
        PROCESSED / "crop_dataset.csv"
    )

    rows = []

    for code, name in CROPS.items():
        path = RAW / f"sxHg_{code}.tif"

        subset = base[
            base["crop_code"] == code
        ]

        with rasterio.open(path) as raster:
            if raster.crs.to_epsg() != 4326:
                raise ValueError("CRS inesperado")

            for _, row in subset.iterrows():
                point = (
                    row["longitude"],
                    row["latitude"]
                )

                value = next(
                    raster.sample([point], masked=True)
                )[0]

                if np.ma.is_masked(value):
                    continue

                if not 0 <= value <= 10000:
                    continue

                new_row = row.to_dict()

                new_row["water_supply"] = (
                    "irrigated_gravity"
                )

                new_row["suitability"] = (
                    float(value) / 100
                )

                rows.append(new_row)

        print(f"Procesado: {name}")

    if not rows:
        raise ValueError("No se encontraron datos válidos")

    irrigation = pd.DataFrame(rows)

    result = pd.concat(
        [base, irrigation],
        ignore_index=True
    )

    output = PROCESSED / "crop_dataset_v2.csv"

    result.to_csv(output, index=False)

    print("\nDATASET GENERADO")
    print(result.groupby("water_supply").size())
    print(f"\nTotal de registros: {len(result)}")
    print(f"Archivo: {output}")


if __name__ == "__main__":
    download_rasters()
    build_dataset()
