from statistics import mean
from math import isfinite

import nasa


def valid_values(data, metric):
    return [
        value
        for _, value in nasa.daily(data, metric)
        if isinstance(value, (int, float))
        and isfinite(value)
    ]


def aggregate(data, metric, function=mean):
    values = valid_values(data, metric)

    return function(values) if values else None


def extract_features(climate_data, soil_data):
    return {
        "temperature_mean": aggregate(
            climate_data, "T2M"
        ),
        "temperature_min": aggregate(
            climate_data, "T2M_MIN", min
        ),
        "temperature_max": aggregate(
            climate_data, "T2M_MAX", max
        ),
        "precipitation": aggregate(
            climate_data, "PRECTOTCORR", sum
        ),
        "air_humidity": aggregate(
            climate_data, "RH2M"
        ),
        "solar_radiation": aggregate(
            climate_data, "ALLSKY_SFC_SW_DWN"
        ),
        "wind_speed": aggregate(
            climate_data, "WS2M"
        ),
        "surface_soil_wetness": aggregate(
            soil_data, "GWETTOP"
        ),
        "root_soil_wetness": aggregate(
            soil_data, "GWETROOT"
        ),
        "dry_spell": nasa.dry_spell(
            nasa.daily(climate_data, "PRECTOTCORR")
        ) if valid_values(
            climate_data, "PRECTOTCORR"
        ) else None,
    }
