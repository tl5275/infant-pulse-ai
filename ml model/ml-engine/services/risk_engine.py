"""Risk scoring engine for Infant Pulse."""

from __future__ import annotations

import numpy as np


def assess_vital_thresholds(latest_vitals: dict[str, float]) -> dict[str, object]:
    """Score the latest vital signs against neonatal safety thresholds."""
    heart_rate = float(latest_vitals.get("heart_rate", 0.0))
    spo2 = float(latest_vitals.get("spo2", 0.0))
    temperature = float(latest_vitals.get("temperature", 0.0))
    respiration = float(latest_vitals.get("respiration", 0.0))

    score = 0.0
    reasons: list[str] = []

    if heart_rate < 100 or heart_rate > 180:
        score += 0.35
        reasons.append(f"Heart rate {heart_rate:.1f} bpm is outside the NICU target range.")
    elif heart_rate < 110 or heart_rate > 170:
        score += 0.15

    if spo2 < 90:
        score += 0.4
        reasons.append(f"SpO2 {spo2:.1f}% is critically low.")
    elif spo2 < 94:
        score += 0.2
        reasons.append(f"SpO2 {spo2:.1f}% is trending below the preferred range.")

    if temperature < 36.2 or temperature > 37.8:
        score += 0.15
        reasons.append(f"Temperature {temperature:.1f} C is outside the expected range.")

    if respiration < 25 or respiration > 70:
        score += 0.15
        reasons.append(f"Respiration {respiration:.1f} rpm is abnormal for the infant.")

    return {"score": float(np.clip(score, 0.0, 1.0)), "reasons": reasons}


def _categorize_status(risk_score: float) -> str:
    """Map a continuous risk score to a triage-ready status label."""
    if risk_score >= 0.7:
        return "CRITICAL"
    if risk_score >= 0.4:
        return "WARNING"
    return "STABLE"


def compute_risk_score(
    anomaly_result: dict[str, float | str],
    latest_vitals: dict[str, float],
    early_warning_result: dict[str, object],
) -> dict[str, object]:
    """Combine anomaly, threshold, and trend signals into a single risk score."""
    anomaly_score = float(anomaly_result.get("anomaly_score", 0.0))
    vital_result = assess_vital_thresholds(latest_vitals)
    warning_active = bool(early_warning_result.get("early_warning", False))
    warning_bonus = 0.2 if warning_active else 0.0

    risk_score = float(
        np.clip(
            0.45 * anomaly_score + 0.35 * float(vital_result["score"]) + warning_bonus,
            0.0,
            1.0,
        )
    )

    reasons = list(vital_result["reasons"])
    reasons.extend(str(reason) for reason in early_warning_result.get("reasons", []))
    if anomaly_result.get("label") == "anomaly":
        reasons.insert(0, "Isolation Forest flagged the current pattern as an outlier.")
    if not reasons:
        reasons.append("All monitored features remain within expected operating bounds.")

    return {
        "risk_score": round(risk_score, 4),
        "status": _categorize_status(risk_score),
        "reasons": reasons,
        "components": {
            "anomaly_score": round(anomaly_score, 4),
            "vital_score": round(float(vital_result["score"]), 4),
            "warning_score": round(warning_bonus, 4),
        },
    }
