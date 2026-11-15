from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)


ROOT = Path(__file__).resolve().parents[2]

DATASET = ROOT / "data" / "processed" / "crop_dataset.csv"
MODEL_PATH = ROOT / "models" / "crop_model.joblib"


FEATURES = [
    "temperature_mean",
    "temperature_min_monthly_mean",
    "temperature_max_monthly_mean",
    "precipitation_annual_mm",
    "air_humidity",
    "surface_soil_wetness",
    "root_soil_wetness",
    "wind_speed",
]

CATEGORIES = ["crop_code"]


def train_model():

    df = pd.read_csv(DATASET)

    df = df.dropna(
        subset=FEATURES + CATEGORIES + ["suitability"]
    )

    df = df.drop_duplicates(
        subset=["latitude", "longitude", "crop_code"]
    ).reset_index(drop=True)

    if not df["water_supply"].eq("rainfed").all():
        raise ValueError("El dataset contiene otros sistemas de riego.")

    if not df["suitability"].between(0, 100).all():
        raise ValueError("Índices de aptitud fuera de rango.")

    locations = df[
        ["latitude", "longitude"]
    ].drop_duplicates()

    print(f"Registros: {len(df)}")
    print(f"Ubicaciones: {len(locations)}")
    print(f"Cultivos: {df['crop'].nunique()}")

    if len(locations) < 100:
        raise ValueError(
            "Se necesitan más ubicaciones para esta prueba."
        )

    X = df[FEATURES + CATEGORIES]
    y = df["suitability"]

    # Agrupar ubicaciones en bloques geográficos
    lat_group = ((df["latitude"] + 90) // 12).astype(int)
    lon_group = ((df["longitude"] + 180) // 12).astype(int)

    groups = (
        lat_group.astype(str)
        + "_"
        + lon_group.astype(str)
    )

    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=0.20,
        random_state=42
    )

    train_idx, test_idx = next(
        splitter.split(X, y, groups)
    )

    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]

    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]

    preprocessor = ColumnTransformer([
        (
            "numeric",
            "passthrough",
            FEATURES
        ),
        (
            "categorical",
            OneHotEncoder(handle_unknown="error"),
            CATEGORIES
        )
    ])

    forest = RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1
    )

    model = Pipeline([
        ("preprocessing", preprocessor),
        ("random_forest", forest)
    ])

    print("\nEntrenando Random Forest...")

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)

    rmse = np.sqrt(
        mean_squared_error(y_test, predictions)
    )

    r2 = r2_score(y_test, predictions)

    print("\nRESULTADOS DEL MODELO")
    print("-------------------------")
    print(f"MAE: {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"R²: {r2:.4f}")

    # Comparar contra una predicción básica por cultivo
    baseline_means = df.iloc[train_idx].groupby(
        "crop_code"
    )["suitability"].mean()

    baseline = X_test["crop_code"].map(baseline_means)

    baseline_mae = mean_absolute_error(
        y_test, baseline
    )

    print(f"MAE referencia: {baseline_mae:.4f}")

    if mae >= baseline_mae:
        print(
            "Advertencia: el modelo todavía no "
            "supera la referencia básica."
        )

    # Guardar el modelo evaluado y su configuración
    MODEL_PATH.parent.mkdir(
        parents=True, exist_ok=True
    )

    artifact = {
        "model": model,
        "features": FEATURES + CATEGORIES,
        "crops": (
            df[["crop_code", "crop"]]
            .drop_duplicates()
            .set_index("crop_code")["crop"]
            .to_dict()
        ),
        "water_supply": "rainfed",
        "reference_period": "1981-2010",
        "metrics": {
            "mae": float(mae),
            "rmse": float(rmse),
            "r2": float(r2),
            "baseline_mae": float(baseline_mae)
        }
    }

    joblib.dump(artifact, MODEL_PATH)

    print("\nModelo guardado correctamente:")
    print(MODEL_PATH)


if __name__ == "__main__":
    train_model()
