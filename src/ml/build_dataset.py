from pathlib import Path
from statistics import mean
from calendar import monthrange
from time import sleep
import argparse
import random

import httpx
import numpy as np
import pandas as pd
import rasterio


ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data" / "raw" / "gaez"
OUTPUT = ROOT / "data" / "processed" / "crop_dataset.csv"

NASA_URL = (
    "https://power.larc.nasa.gov/api/temporal/monthly/point"
)

CROPS = {
    "mze": "Maíz",
    "phb": "Frijol",
    "wpo": "Papa",
}

METRICS = {
    "T2M": "temperature_mean",
    "T2M_MIN": "temperature_min_monthly_mean",
    "T2M_MAX": "temperature_max_monthly_mean",
    "PRECTOTCORR": "precipitation_annual_mm",
    "RH2M": "air_humidity",
    "GWETTOP": "surface_soil_wetness",
    "GWETROOT": "root_soil_wetness",
    "WS2M": "wind_speed",
}


def historical_features(client, lat, lon):

    response = client.get(
        NASA_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "community": "AG",
            "parameters": ",".join(METRICS),
            "start": 1981,
            "end": 2010,
            "format": "JSON",
        },
    )

    response.raise_for_status()

    data = response.json()

    parameters = data["properties"]["parameter"]
    fill = data["header"]["fill_value"]

    features = {}

    for metric, name in METRICS.items():

        series = parameters.get(metric, {})

        values = []

        for year in range(1981, 2011):
            for month in range(1, 13):

                key = f"{year}{month:02d}"
                value = series.get(key)

                if (
                    value is None
                    or value == fill
                    or not np.isfinite(value)
                ):
                    raise ValueError(
                        f"Datos incompletos: {metric}"
                    )

                if metric == "PRECTOTCORR":
                    days = monthrange(year, month)[1]
                    values.append(value * days)
                else:
                    values.append(value)

        if metric == "PRECTOTCORR":
            features[name] = sum(values) / 30
        else:
            features[name] = mean(values)

    return features


def geographic_samples():

    points = [
        (lon, lat)
        for lat in range(-58, 79, 4)
        for lon in range(-178, 180, 4)
    ]

    scores = {}

    for code in CROPS:

        filename = DATA_DIR / f"sxHr_{code}.tif"

        with rasterio.open(filename) as raster:

            if raster.crs.to_epsg() != 4326:
                raise ValueError(
                    f"Sistema de coordenadas inesperado: {filename}"
                )

            scores[code] = [
                sample[0]
                for sample in raster.sample(
                    points, masked=True
                )
            ]

    samples = []

    for index, (lon, lat) in enumerate(points):

        labels = {}

        for code in CROPS:

            value = scores[code][index]

            if (
                np.ma.is_masked(value)
                or not 0 <= value <= 10000
            ):
                break

            labels[code] = float(value) / 100

        if len(labels) == len(CROPS):
            samples.append((lat, lon, labels))

    random.Random(42).shuffle(samples)

    return samples


def build_dataset(total_points=20):

    OUTPUT.parent.mkdir(
        parents=True, exist_ok=True
    )

    records = (
        pd.read_csv(OUTPUT).to_dict("records")
        if OUTPUT.exists()
        else []
    )

    completed = {
        (row["latitude"], row["longitude"])
        for row in records
    }

    samples = geographic_samples()

    attempts = 0
    max_attempts = max(
        0, (total_points - len(completed)) * 3
    )

    with httpx.Client(timeout=60) as client:

        for lat, lon, labels in samples:

            if len(completed) >= total_points:
                break

            if (lat, lon) in completed:
                continue

            if attempts >= max_attempts:
                break

            attempts += 1

            print(f"Analizando: {lat}, {lon}")

            try:

                features = historical_features(
                    client, lat, lon
                )

                for code, crop in CROPS.items():

                    records.append({
                        "latitude": lat,
                        "longitude": lon,
                        **features,
                        "crop_code": code,
                        "crop": crop,
                        "water_supply": "rainfed",
                        "suitability": labels[code],
                    })

                completed.add((lat, lon))

                pd.DataFrame(records).to_csv(
                    OUTPUT, index=False
                )

                print(
                    f"Ubicaciones: {len(completed)}"
                    f"/{total_points}"
                )

            except httpx.HTTPError as error:
                print(f"Error de conexión: {error}")
                break

            except ValueError as error:
                print(f"Ubicación omitida: {error}")

            sleep(0.75)

    print(f"Registros obtenidos: {len(records)}")
    print(f"Archivo: {OUTPUT}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--points", type=int, default=20
    )

    args = parser.parse_args()

    build_dataset(args.points)
