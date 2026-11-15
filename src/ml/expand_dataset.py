from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import rasterio

ROOT = Path(__file__).resolve().parents[2]

RAW = ROOT / "data/raw/expanded"
PROCESSED = ROOT / "data/processed"

BASE_URL = (
    "https://gaez-v4-data.fao.org/data/"
    "res05/CRUTS32/Hist/8110H/"
)

CROPS = {
    "mze": "Maíz",
    "phb": "Frijol",
    "wpo": "Papa",
    "alf": "Alfalfa",
    "ban": "Plátano",
    "brl": "Cebada",
    "car": "Zanahoria",
    "chk": "Garbanzo",
    "cit": "Cítricos",
    "coc": "Cacao",
    "cof": "Café",
    "cot": "Algodón",
    "cow": "Frijol caupí",
    "grd": "Maní",
    "olv": "Olivo",
    "oni": "Cebolla",
    "soy": "Soya",
    "spo": "Camote",
    "tom": "Tomate",
    "whe": "Trigo",
}

SCENARIOS = {
    "rainfed": "r",
    "irrigated_gravity": "g",
}


def download_raster(client, filename):

    RAW.mkdir(parents=True, exist_ok=True)

    path = RAW / filename

    if path.exists():
        return path

    temp = path.with_suffix(".part")

    with client.stream(
        "GET",
        BASE_URL + filename,
    ) as response:

        response.raise_for_status()

        with temp.open("wb") as file:
            for chunk in response.iter_bytes():
                file.write(chunk)

    temp.replace(path)

    return path


def expand_dataset():

    base = pd.read_csv(
        PROCESSED / "crop_dataset_v2.csv"
    )

    points = base.drop_duplicates(
        subset=["latitude", "longitude"]
    )

    existing_crops = set(base["crop_code"])

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

        for code, name in CROPS.items():

            if code in existing_crops:
                continue

            for scenario, suffix in SCENARIOS.items():

                filename = f"sxH{suffix}_{code}.tif"

                print(f"Procesando {name}: {scenario}")

                path = download_raster(
                    client, filename
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
                        new_row["crop"] = name
                        new_row["water_supply"] = scenario

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

    output = PROCESSED / "crop_dataset_v3.csv"

    result.to_csv(output, index=False)

    print("\nDATASET V3 GENERADO")
    print("-----------------------------")
    print(f"Cultivos: {result['crop_code'].nunique()}")
    print(f"Ubicaciones: {len(points)}")
    print(f"Total de registros: {len(result)}")

    print("\nREGISTROS POR CULTIVO")

    print(
        result.groupby(
            ["crop", "water_supply"]
        ).size()
    )

    print(f"\nArchivo: {output}")


if __name__ == "__main__":
    expand_dataset()