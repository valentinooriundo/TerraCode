from pathlib import Path
from functools import lru_cache

import httpx
import joblib
import pandas as pd

from .build_dataset import historical_features

from .gaez_v5 import avocado_suitability, AVOCADO_PATH


ROOT = Path(__file__).resolve().parents[2]

MODEL_PATH = ROOT / "models" / "crop_model_v4.joblib"


@lru_cache(maxsize=1)
def load_model():
    return joblib.load(MODEL_PATH)


@lru_cache(maxsize=128)
def get_features(lat, lon):

    with httpx.Client(timeout=60) as client:
        return historical_features(client, lat, lon)


def recommend(
    lat,
    lon,
    start=None,
    end=None,
    water_supply="rainfed",
):

    artifact = load_model()

    model = artifact["model"]

    # Obtener cultivos disponibles según el riego
    allowed_crops = artifact["crops_by_water_supply"].get(
        water_supply
    )

    if not allowed_crops:
        raise ValueError(
            "Escenario hídrico no disponible"
        )

    crops = {
        code: name
        for code, name in artifact["crops"].items()
        if code in allowed_crops
    }

    # Obtener variables históricas de NASA POWER
    features = get_features(
        round(lat, 4),
        round(lon, 4),
    )

    if not features:
        raise ValueError(
            "No se encontraron datos ambientales"
        )

    # Construir datos de entrada
    rows = [
        {
            **features,
            "crop_code": code,
            "water_supply": water_supply,
        }
        for code in crops
    ]

    X = pd.DataFrame(rows)

    # Generar predicciones
    predictions = model.predict(
        X[artifact["features"]]
    )

    results = []

    for (code, name), score in zip(
        crops.items(), predictions
    ):

        results.append({
            "code": code,
            "crop": name,
            "score": round(float(score), 2),
        })

    # Ordenar de mayor a menor aptitud
    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    avocado_score = None

    if water_supply in (
            "irrigated_gravity",
            "irrigated_drip"
        ) and AVOCADO_PATH.is_file():

            avocado_score = avocado_suitability(lat, lon)

    return {
        "recommendations": results,
        "metrics": artifact["metrics"],
        "reference_period": artifact["reference_period"],
        "water_supply": water_supply,
        "total_crops": len(results),
        "avocado_gaez_v5": avocado_score,
    }


def compare(lat, lon, start=None, end=None):

    return {
        "rainfed": recommend(
            lat,
            lon,
            start,
            end,
            water_supply="rainfed",
        ),
        "irrigated_gravity": recommend(
            lat,
            lon,
            start,
            end,
            water_supply="irrigated_gravity",
        ),
        "irrigated_drip": recommend(
            lat,
            lon,
            start,
            end,
            water_supply="irrigated_drip",
        ),
    }


if __name__ == "__main__":

    results = compare(-14.06, -75.73)

    names = {
        "rainfed": "SECANO",
        "irrigated_gravity": "RIEGO POR GRAVEDAD",
        "irrigated_drip": "RIEGO POR GOTEO",
    }

    for scenario, data in results.items():

        print(f"\n{names[scenario]}")
        print("-" * 35)

        for item in data["recommendations"]:

            print(
                f"{item['crop']}: "
                f"{item['score']:.2f}/100"
            )

        print(
            f"Total de cultivos: "
            f"{data['total_crops']}"
        )