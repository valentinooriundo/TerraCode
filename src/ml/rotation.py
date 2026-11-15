from itertools import combinations
from pprint import pprint

from .predictor import recommend

# Familias botánicas de cultivos de rotación
FAMILIES = {
    "mze": "Poaceae",
    "whe": "Poaceae",
    "brl": "Poaceae",

    "phb": "Fabaceae",
    "cow": "Fabaceae",
    "chk": "Fabaceae",
    "soy": "Fabaceae",
    "grd": "Fabaceae",

    "wpo": "Solanaceae",
    "tom": "Solanaceae",

    "car": "Apiaceae",
    "cot": "Malvaceae",
    "oni": "Amaryllidaceae",
    "spo": "Convolvulaceae",
}

LEGUMES = {
    "phb", "cow", "chk", "soy", "grd"
}

# Cultivos de larga duración excluidos
# de las rotaciones anuales simples
PERENNIALS = {
    "alf", "ban", "cit", "coc", "cof", "olv"
}

# Umbral experimental de TerraSprout
MIN_SUITABILITY = 40


def recommend_rotations(
    data,
    previous_crop,
    min_score=MIN_SUITABILITY,
):

    if previous_crop in PERENNIALS:
        return {
            "status": "perennial",
            "message": (
                "Este cultivo requiere planificación "
                "de largo plazo."
            ),
            "next_crops": [],
            "plans": [],
        }

    if previous_crop not in FAMILIES:
        raise ValueError(
            "Cultivo anterior no reconocido"
        )

    previous_family = FAMILIES[previous_crop]

    candidates = []

    for item in data["recommendations"]:

        code = item["code"]

        if code not in FAMILIES:
            continue

        family = FAMILIES[code]

        # Evitar repetir la misma familia
        if family == previous_family:
            continue

        reason = (
            "Pertenece a una familia botánica "
            "diferente a la del cultivo anterior."
        )

        if code in LEGUMES:
            reason += (
                " Puede contribuir a la fijación "
                "biológica de nitrógeno."
            )

        candidates.append({
            "code": code,
            "crop": item["crop"],
            "family": family,
            "score": item["score"],
            "legume": code in LEGUMES,
            "reason": reason,
        })

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    eligible = [
        item for item in candidates
        if item["score"] >= min_score
    ]

    if not eligible:
        return {
            "status": "insufficient",
            "message": (
                "No se encontraron alternativas "
                "con aptitud suficiente."
            ),
            "threshold": min_score,
            "best_alternative": (
                candidates[0] if candidates else None
            ),
            "next_crops": [],
            "plans": [],
        }

    plans = []

    for first, second in combinations(eligible, 2):

        # Evitar repetir familias consecutivas
        if first["family"] == second["family"]:
            continue

        # Considerar leguminosa primero
        if second["legume"] and not first["legume"]:
            first, second = second, first

        plans.append({
            "sequence": [
                previous_crop,
                first["code"],
                second["code"],
            ],
            "crops": [
                first["crop"],
                second["crop"],
            ],
            "scores": [
                first["score"],
                second["score"],
            ],
            "minimum_suitability": min(
                first["score"],
                second["score"],
            ),
        })

    plans.sort(
        key=lambda plan: (
            plan["minimum_suitability"],
            sum(plan["scores"]),
        ),
        reverse=True,
    )

    return {
        "status": "ok",
        "message": "Alternativas de rotación encontradas.",
        "water_supply": data["water_supply"],
        "previous_crop": previous_crop,
        "next_crops": eligible[:5],
        "plans": plans[:5],
    }


if __name__ == "__main__":

    data = recommend(
        -14.06,
        -75.73,
        water_supply="irrigated_gravity",
    )

    result = recommend_rotations(
        data,
        previous_crop="mze",
    )

    pprint(result)