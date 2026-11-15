from pathlib import Path
from time import sleep
from random import Random

import httpx
import numpy as np
import pandas as pd
import rasterio

from .predictor import get_features
from .expand_dataset import (
    CROPS,
    SCENARIOS,
    download_raster,
)

ROOT = Path(__file__).resolve().parents[2]

RAW = ROOT / "data/raw"
PROCESSED = ROOT / "data/processed"

BASE = PROCESSED / "crop_dataset_v3.csv"
CHECKPOINT = PROCESSED / "regional_checkpoint.csv"
OUTPUT = PROCESSED / "crop_dataset_v3_regional.csv"

# Zonas de muestreo regional
ZONES = {
    "Costa norte": (-8.5, -3.5, -81.25, -76.25),
    "Costa central": (-13.5, -9, -79.375, -73.125),
    "Costa sur": (-18.5, -14, -76.875, -69.375),
}

POINTS_PER_ZONE = 40


def grid_id(lat, lon):
    return (
        round(lat / 0.5),
        round(lon / 0.625),
    )


def generate_points(base):

    existing = {
        grid_id(row.latitude, row.longitude)
        for row in base.itertuples()
    }

    zones = {}

    for name, bounds in ZONES.items():

        min_lat, max_lat, min_lon, max_lon = bounds

        candidates = []

        for lat in np.arange(
            min_lat, max_lat + 0.01, 0.5
        ):
            for lon in np.arange(
                min_lon, max_lon + 0.01, 0.625
            ):

                point = float(lat), float(lon)

                if grid_id(*point) not in existing:
                    candidates.append(point)

        Random(42).shuffle(candidates)

        # Priorizar algunas ubicaciones cercanas a Ica
        if name == "Costa sur":

            nearby = sorted(
                candidates,
                key=lambda p: (
                    (p[0] + 14.06) ** 2
                    + (p[1] + 75.73) ** 2
                )
            )[:12]

            candidates = nearby + [
                p for p in candidates
                if p not in nearby
            ]

        zones[name] = candidates

    return zones


def load_labels(points):

    labels = {point: {} for point in points}

    with httpx.Client(
        timeout=120,
        follow_redirects=True,
    ) as client:

        for code in CROPS:
            for scenario, suffix in SCENARIOS.items():

                filename = f"sxH{suffix}_{code}.tif"

                path = next(
                    RAW.rglob(filename),
                    None
                )

                if path is None:
                    path = download_raster(
                        client, filename
                    )

                active = list(labels)

                coordinates = [
                    (lon, lat)
                    for lat, lon in active
                ]

                with rasterio.open(path) as raster:

                    if raster.crs.to_epsg() != 4326:
                        raise ValueError("CRS inesperado")

                    samples = raster.sample(
                        coordinates,
                        masked=True,
                    )

                    for point, sample in zip(
                        active, samples
                    ):

                        value = sample[0]

                        if (
                            np.ma.is_masked(value)
                            or not np.isfinite(value)
                            or not 0 <= value <= 10000
                        ):
                            labels.pop(point, None)
                            continue

                        labels[point][code, scenario] = (
                            float(value) / 100
                        )

    return labels


def main():

    base = pd.read_csv(BASE)

    zones = generate_points(base)

    points = list({
        point
        for candidates in zones.values()
        for point in candidates
    })

    print("Verificando mapas FAO GAEZ...")

    labels = load_labels(points)

    if CHECKPOINT.exists():
        saved = pd.read_csv(CHECKPOINT)
    else:
        saved = pd.DataFrame(columns=base.columns)

    completed = {
        (row.latitude, row.longitude)
        for row in saved.itertuples()
    }

    for zone, candidates in zones.items():

        count = sum(
            point in completed
            for point in candidates
        )

        print(f"\nAnalizando: {zone}")

        for lat, lon in candidates:

            if count >= POINTS_PER_ZONE:
                break

            if (lat, lon) in completed:
                continue

            if (lat, lon) not in labels:
                continue

            print(
                f"NASA POWER: {lat}, {lon} "
                f"({count + 1}/{POINTS_PER_ZONE})"
            )

            features = get_features(lat, lon)

            if not features:
                continue

            rows = []

            for code, name in CROPS.items():
                for scenario in SCENARIOS:

                    rows.append({
                        **features,
                        "latitude": lat,
                        "longitude": lon,
                        "crop_code": code,
                        "crop": name,
                        "water_supply": scenario,
                        "suitability": labels[
                            (lat, lon)
                        ][(code, scenario)],
                    })

            saved = pd.concat(
                [saved, pd.DataFrame(rows)],
                ignore_index=True,
            )

            # Guardar avance para poder reanudar
            temp = CHECKPOINT.with_suffix(".tmp")
            saved.to_csv(temp, index=False)
            temp.replace(CHECKPOINT)

            completed.add((lat, lon))
            count += 1

            sleep(1)

        print(f"{zone}: {count} puntos")

    result = pd.concat(
        [base, saved],
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

    result.to_csv(OUTPUT, index=False)

    total_points = result.drop_duplicates(
        subset=["latitude", "longitude"]
    )

    print("\nDATASET REGIONAL GENERADO")
    print("---------------------------")
    print(f"Ubicaciones: {len(total_points)}")
    print(f"Cultivos: {result['crop_code'].nunique()}")
    print(f"Registros: {len(result)}")
    print(f"Archivo: {OUTPUT}")


if __name__ == "__main__":
    main()