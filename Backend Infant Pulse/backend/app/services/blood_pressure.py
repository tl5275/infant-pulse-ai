from __future__ import annotations

import math


def _clamp(value: float, lower: float, upper: float) -> float:
    return float(max(lower, min(value, upper)))


def _project_series(
    values: list[float],
    horizon: int,
    lower: float,
    upper: float,
) -> list[float]:
    if not values:
        values = [lower]

    latest = float(values[-1])
    reference_window = values[-5:] if len(values) >= 5 else values
    baseline = float(reference_window[0])
    slope = (latest - baseline) / max(len(reference_window) - 1, 1)

    series: list[float] = []
    for step in range(horizon):
        next_value = _clamp(latest + slope * (step + 1), lower, upper)
        series.append(round(next_value, 1))
    return series


def derive_bp_point(vital: dict[str, float], index: int = 0) -> dict[str, float]:
    heart_rate = float(vital.get("heart_rate", 140.0))
    spo2 = float(vital.get("spo2", 97.0))
    temperature = float(vital.get("temperature", 36.8))
    respiration = float(vital.get("respiration", 40.0))

    pulsatility = 2.1 * math.sin(index / 2.6) + 0.8 * math.cos(index / 4.1)
    perfusion_penalty = max(0.0, 94.0 - spo2)

    systolic = 76.0
    systolic += 0.11 * (heart_rate - 140.0)
    systolic -= 0.4 * perfusion_penalty
    systolic += 1.9 * (temperature - 36.8)
    systolic += 0.06 * (respiration - 40.0)
    systolic += pulsatility
    systolic = round(_clamp(systolic, 60.0, 90.0), 1)

    diastolic = 43.0
    diastolic += 0.07 * (heart_rate - 140.0)
    diastolic -= 0.22 * perfusion_penalty
    diastolic += 1.2 * (temperature - 36.8)
    diastolic += 0.04 * (respiration - 40.0)
    diastolic += pulsatility * 0.7
    diastolic = round(_clamp(min(diastolic, systolic - 16.0), 30.0, 60.0), 1)

    if diastolic >= systolic:
        diastolic = round(max(30.0, systolic - 16.0), 1)

    return {
        "systolic": systolic,
        "diastolic": diastolic,
    }


def build_bp_series(vitals_history: list[dict[str, float]] | None) -> dict[str, list[float]]:
    history = vitals_history or [
        {
            "heart_rate": 140.0,
            "spo2": 97.0,
            "temperature": 36.8,
            "respiration": 40.0,
        }
    ]

    systolic: list[float] = []
    diastolic: list[float] = []
    for index, vital in enumerate(history):
        point = derive_bp_point(vital, index=index)
        systolic.append(point["systolic"])
        diastolic.append(point["diastolic"])

    return {
        "systolic": systolic,
        "diastolic": diastolic,
    }


def project_bp_series(bp_series: dict[str, list[float]] | None, horizon: int = 12) -> dict[str, list[float]]:
    values = bp_series or {}
    projected_systolic = _project_series(list(values.get("systolic", [])), horizon=horizon, lower=60.0, upper=90.0)
    projected_diastolic = _project_series(list(values.get("diastolic", [])), horizon=horizon, lower=30.0, upper=60.0)

    adjusted_diastolic = [
        round(min(diastolic, max(30.0, systolic - 16.0)), 1)
        for systolic, diastolic in zip(projected_systolic, projected_diastolic)
    ]

    return {
        "systolic": projected_systolic,
        "diastolic": adjusted_diastolic,
    }
