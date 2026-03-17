from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.alert import Alert
from app.models.vital import Vital


@dataclass(slots=True)
class AlertCandidate:
    baby_id: int
    alert_type: str
    severity: str
    message: str
    timestamp: datetime


def evaluate_vital(vital: Vital) -> list[AlertCandidate]:
    alerts: list[AlertCandidate] = []

    if vital.spo2 < 90:
        alerts.append(
            AlertCandidate(
                baby_id=vital.baby_id,
                alert_type="LOW_SPO2",
                severity="CRITICAL",
                message=f"Critical SpO2 drop detected: {vital.spo2}%",
                timestamp=vital.timestamp,
            )
        )

    if vital.heart_rate > 170:
        alerts.append(
            AlertCandidate(
                baby_id=vital.baby_id,
                alert_type="HIGH_HEART_RATE",
                severity="WARNING",
                message=f"Elevated heart rate detected: {vital.heart_rate} bpm",
                timestamp=vital.timestamp,
            )
        )

    if vital.temperature > 37.8:
        alerts.append(
            AlertCandidate(
                baby_id=vital.baby_id,
                alert_type="HIGH_TEMPERATURE",
                severity="WARNING",
                message=f"Elevated temperature detected: {vital.temperature:.1f} C",
                timestamp=vital.timestamp,
            )
        )

    return alerts


def build_alert_models(alerts: list[AlertCandidate]) -> list[Alert]:
    return [
        Alert(
            baby_id=alert.baby_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            message=alert.message,
            timestamp=alert.timestamp,
        )
        for alert in alerts
    ]

