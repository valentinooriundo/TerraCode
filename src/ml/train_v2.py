from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

ROOT = Path(__file__).resolve().parents[2]

DATASET = ROOT / "data/processed/crop_dataset_v2.csv"
MODEL = ROOT / "models/crop_model_v2.joblib"

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

CATEGORIES = [
    "crop_code",
    "water_supply",
]

CROPS = {
    "mze": "Maíz",
    "phb": "Frijol",
    "wpo": "Papa",
}

# Cargar dataset
df = pd.read_csv(DATASET)

df = df.dropna(
    subset=FEATURES + CATEGORIES + [
        "latitude",
        "longitude",
        "suitability",
    ]
)

df = df.drop_duplicates(
    subset=[
        "latitude",
        "longitude",
        "crop_code",
        "water_supply",
    ]
)

df = df[df["suitability"].between(0, 100)]

X = df[FEATURES + CATEGORIES]
y = df["suitability"]

# Agrupación geográfica
lat_group = ((df["latitude"] + 90) // 12).astype(int)
lon_group = ((df["longitude"] + 180) // 12).astype(int)

groups = lat_group.astype(str) + "_" + lon_group.astype(str)

split = GroupShuffleSplit(
    n_splits=1,
    test_size=0.20,
    random_state=42,
)

train_idx, test_idx = next(
    split.split(X, y, groups)
)

X_train = X.iloc[train_idx]
X_test = X.iloc[test_idx]

y_train = y.iloc[train_idx]
y_test = y.iloc[test_idx]

# Preprocesamiento
preprocessor = ColumnTransformer([
    ("numeric", "passthrough", FEATURES),
    (
        "categorical",
        OneHotEncoder(handle_unknown="error"),
        CATEGORIES,
    ),
])

# Modelo Random Forest
model = Pipeline([
    ("preprocessor", preprocessor),
    (
        "regressor",
        RandomForestRegressor(
            n_estimators=300,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1,
        ),
    ),
])

print("Entrenando TerraSprout AI V2...")

model.fit(X_train, y_train)

predictions = model.predict(X_test)

# Evaluación
mae = mean_absolute_error(y_test, predictions)

rmse = np.sqrt(
    mean_squared_error(y_test, predictions)
)

r2 = r2_score(y_test, predictions)

print("\nRESULTADOS DEL MODELO V2")
print("--------------------------------")
print(f"Registros: {len(df)}")
print(f"Entrenamiento: {len(X_train)}")
print(f"Evaluación: {len(X_test)}")
print(f"MAE: {mae:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"R²: {r2:.4f}")

# Evaluación por escenario
print("\nRESULTADOS POR ESCENARIO")

for scenario in df["water_supply"].unique():
    mask = X_test["water_supply"] == scenario

    if mask.any():
        error = mean_absolute_error(
            y_test[mask],
            predictions[mask.to_numpy()],
        )

        print(f"{scenario}: MAE = {error:.4f}")

# Guardar modelo
MODEL.parent.mkdir(parents=True, exist_ok=True)

joblib.dump(
    {
        "model": model,
        "features": FEATURES + CATEGORIES,
        "crops": CROPS,
        "water_supply": [
            "rainfed",
            "irrigated_gravity",
        ],
        "reference_period": "1981-2010",
        "metrics": {
            "mae": float(mae),
            "rmse": float(rmse),
            "r2": float(r2),
        },
    },
    MODEL,
)

print(f"\nModelo guardado correctamente:\n{MODEL}")
