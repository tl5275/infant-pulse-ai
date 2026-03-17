from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from app.services.blood_pressure import build_bp_series, project_bp_series


def _status_to_frontend(status: str) -> str:
    normalized = status.upper()
    if normalized == "CRITICAL":
        return "critical"
    if normalized == "WARNING":
        return "warning"
    return "stable"


def _trend_label(previous: float, current: float, tolerance: float = 1.0) -> str:
    if current > previous + tolerance:
        return "up"
    if current < previous - tolerance:
        return "down"
    return "steady"


def _project_series(
    values: list[float],
    horizon: int,
    lower: float,
    upper: float,
    digits: int = 0,
) -> list[float]:
    if not values:
        values = [lower]

    latest = float(values[-1])
    reference_window = values[-5:] if len(values) >= 5 else values
    baseline = float(reference_window[0])
    slope = (latest - baseline) / max(len(reference_window) - 1, 1)

    series: list[float] = []
    for step in range(horizon):
        next_value = max(lower, min(upper, latest + slope * (step + 1)))
        series.append(round(next_value, digits))
    return series


def _compress_signal(signal: list[float], target_points: int) -> list[float]:
    if not signal:
        return [0.0] * target_points
    if len(signal) <= target_points:
        return [round(float(value), 4) for value in signal]

    step = len(signal) / float(target_points)
    compressed = [signal[int(index * step)] for index in range(target_points)]
    return [round(float(value), 4) for value in compressed]


def _format_timestamp(value: datetime | None) -> str:
    if value is None:
        value = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%H:%M:%S UTC")


class LiveMonitorService:
    """Maintains the frontend-ready live dashboard snapshot."""

    def __init__(self, alert_limit: int = 8) -> None:
        self._alert_limit = alert_limit
        self._baby_order: list[int] = []
        self._babies: dict[int, dict[str, Any]] = {}
        self._external_ids: dict[int, str] = {}
        self._alerts: list[dict[str, Any]] = []

    def seed_babies(self, babies: Sequence[Any]) -> None:
        ordered_babies = sorted(babies, key=lambda item: item.nicu_bed)
        self._baby_order = [baby.id for baby in ordered_babies]

        for index, baby in enumerate(ordered_babies, start=1):
            self._external_ids[baby.id] = baby.nicu_bed
            self._babies[baby.id] = self._build_placeholder_baby(baby, index)

    def _build_placeholder_baby(self, baby: Any, index: int) -> dict[str, Any]:
        history = [
            {
                "heart_rate": 136 + index,
                "spo2": 97,
                "temperature": 36.7,
                "respiration": 40 + (index % 3),
            }
            for _ in range(12)
        ]
        analysis = {
            "risk_score": 0.12,
            "status": "STABLE",
            "anomaly": "normal",
            "early_warning": False,
            "message": "No early warning trends detected.",
            "explanation": {
                "top_reasons": ["All monitored features remain within expected operating bounds."],
            },
            "ecg_signal": [0.0] * 48,
            "predicted_ecg": [0.0] * 20,
        }
        return self._build_baby_snapshot(baby, history, analysis, index, datetime.now(timezone.utc))

    def update_baby(
        self,
        baby: Any,
        vitals_history: list[dict[str, float]],
        analysis_result: dict[str, Any],
        timestamp: datetime,
    ) -> dict[str, Any]:
        order_index = self._baby_order.index(baby.id) + 1 if baby.id in self._baby_order else len(self._baby_order) + 1
        self._external_ids[baby.id] = baby.nicu_bed
        self._babies[baby.id] = self._build_baby_snapshot(
            baby,
            vitals_history,
            analysis_result,
            order_index,
            timestamp,
        )
        return self._babies[baby.id]

    def record_alerts(self, alerts: Sequence[Any]) -> None:
        if not alerts:
            return

        next_alerts: list[dict[str, Any]] = []
        for alert in alerts:
            external_baby_id = self._external_ids.get(alert.baby_id, str(alert.baby_id))
            type_name = "prediction" if str(alert.alert_type).startswith("PREDICTIVE_") else "threshold"
            title = "Early warning escalation" if type_name == "prediction" else str(alert.alert_type).replace("_", " ").title()
            next_alerts.append(
                {
                    "id": str(alert.id),
                    "babyId": external_baby_id,
                    "type": type_name,
                    "severity": str(alert.severity).lower(),
                    "title": title,
                    "message": alert.message,
                    "timestamp": alert.timestamp,
                }
            )

        known_ids = {item["id"] for item in next_alerts}
        for alert in self._alerts:
            if alert["id"] not in known_ids:
                next_alerts.append(alert)

        self._alerts = next_alerts[: self._alert_limit]

    def get_overview(self) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc),
            "babies": [self._babies[baby_id] for baby_id in self._baby_order if baby_id in self._babies],
            "alerts": list(self._alerts),
        }

    def _build_baby_snapshot(
        self,
        baby: Any,
        vitals_history: list[dict[str, float]],
        analysis_result: dict[str, Any],
        order_index: int,
        timestamp: datetime,
    ) -> dict[str, Any]:
        history = vitals_history[-24:] if vitals_history else []
        if not history:
            history = [{"heart_rate": 0.0, "spo2": 0.0, "temperature": 0.0, "respiration": 0.0}]

        latest = history[-1]
        previous = history[-2] if len(history) > 1 else latest
        predicted_heart = _project_series(
            [float(item["heart_rate"]) for item in history],
            horizon=12,
            lower=80.0,
            upper=210.0,
        )
        predicted_spo2 = _project_series(
            [float(item["spo2"]) for item in history],
            horizon=12,
            lower=80.0,
            upper=100.0,
        )
        bp_series = build_bp_series(history)
        predicted_bp = project_bp_series(bp_series, horizon=12)
        chart_data = self._build_chart_data(history, predicted_heart, predicted_spo2)
        ecg_chart_data = self._build_ecg_chart_data(
            analysis_result.get("ecg_signal", []),
            analysis_result.get("predicted_ecg", []),
        )
        bp_chart_data = self._build_bp_chart_data(bp_series, predicted_bp)

        risk_score = int(round(float(analysis_result.get("risk_score", 0.0)) * 100))
        reasons = list(analysis_result.get("explanation", {}).get("top_reasons", []))
        if not reasons:
            message = str(analysis_result.get("message", "All monitored features remain within expected operating bounds."))
            reasons = [message]

        return {
            "id": baby.nicu_bed,
            "numericId": baby.id,
            "bed": f"B-{order_index:02d}",
            "name": baby.name,
            "ageLabel": f"{6 + order_index} days",
            "gestation": f"{29 + (order_index % 5)} weeks",
            "status": _status_to_frontend(str(analysis_result.get("status", "STABLE"))),
            "riskScore": risk_score,
            "vitals": {
                "heartRate": int(round(float(latest["heart_rate"]))),
                "spo2": int(round(float(latest["spo2"]))),
                "respiration": int(round(float(latest["respiration"]))),
                "temperature": round(float(latest["temperature"]), 1),
            },
            "trend": {
                "heartRate": _trend_label(float(previous["heart_rate"]), float(latest["heart_rate"])),
                "spo2": _trend_label(float(previous["spo2"]), float(latest["spo2"]), tolerance=0.6),
            },
            "prediction": {
                "predictedHeartRate": int(round(predicted_heart[-1])),
                "predictedSpo2": int(round(predicted_spo2[-1])),
                "riskLevel": str(analysis_result.get("status", "STABLE")),
                "reasons": [str(reason) for reason in reasons[:3]],
                "anomalyLabel": str(analysis_result.get("anomaly", "normal")),
                "earlyWarning": bool(analysis_result.get("early_warning", False)),
            },
            "chartData": chart_data,
            "ecgChartData": ecg_chart_data,
            "bpChartData": bp_chart_data,
            "lastUpdated": _format_timestamp(timestamp),
        }

    def _build_chart_data(
        self,
        history: list[dict[str, float]],
        predicted_heart: list[float],
        predicted_spo2: list[float],
    ) -> list[dict[str, float | str | None]]:
        actual_points = [
            {
                "label": f"-{len(history) - 1 - index}s",
                "heartRate": round(float(point["heart_rate"]), 1),
                "predictedHeartRate": None,
                "spo2": round(float(point["spo2"]), 1),
                "predictedSpo2": None,
            }
            for index, point in enumerate(history)
        ]
        future_points = [
            {
                "label": f"+{index + 1}s",
                "heartRate": None,
                "predictedHeartRate": round(float(predicted_heart[index]), 1),
                "spo2": None,
                "predictedSpo2": round(float(predicted_spo2[index]), 1),
            }
            for index in range(len(predicted_heart))
        ]
        return actual_points + future_points

    def _build_ecg_chart_data(
        self,
        signal: list[float],
        predicted_signal: list[float],
    ) -> list[dict[str, float | str | None]]:
        actual = _compress_signal(list(signal), target_points=48)
        predicted = _compress_signal(list(predicted_signal), target_points=20)

        actual_points = [
            {
                "label": f"-{len(actual) - 1 - index}",
                "ecg": round(float(value), 4),
                "predictedEcg": None,
            }
            for index, value in enumerate(actual)
        ]
        future_points = [
            {
                "label": f"+{index + 1}",
                "ecg": None,
                "predictedEcg": round(float(value), 4),
            }
            for index, value in enumerate(predicted)
        ]
        return actual_points + future_points

    def _build_bp_chart_data(
        self,
        bp_series: dict[str, list[float]],
        predicted_bp: dict[str, list[float]],
    ) -> list[dict[str, float | str | None]]:
        systolic = list(bp_series.get("systolic", []))
        diastolic = list(bp_series.get("diastolic", []))
        predicted_systolic = list(predicted_bp.get("systolic", []))
        predicted_diastolic = list(predicted_bp.get("diastolic", []))

        actual_count = min(len(systolic), len(diastolic))
        future_count = min(len(predicted_systolic), len(predicted_diastolic))

        actual_points = [
            {
                "label": f"-{actual_count - 1 - index}s",
                "systolic": round(float(systolic[index]), 1),
                "predictedSystolic": None,
                "diastolic": round(float(diastolic[index]), 1),
                "predictedDiastolic": None,
            }
            for index in range(actual_count)
        ]
        future_points = [
            {
                "label": f"+{index + 1}s",
                "systolic": None,
                "predictedSystolic": round(float(predicted_systolic[index]), 1),
                "diastolic": None,
                "predictedDiastolic": round(float(predicted_diastolic[index]), 1),
            }
            for index in range(future_count)
        ]
        return actual_points + future_points
