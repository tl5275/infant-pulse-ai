from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import random
import time
from typing import Any, Sequence


def _clamp(value: float, lower: float, upper: float) -> float:
    return float(max(lower, min(value, upper)))


def _format_timestamp(value: datetime | None = None) -> str:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%H:%M:%S UTC")


@dataclass(slots=True)
class RequestBabyProfile:
    id: int
    nicu_bed: str
    name: str
    index: int


class RequestTelemetryService:
    """Builds fresh NICU payloads on every request without cached chart data."""

    def __init__(self, alert_source=None) -> None:
        self._alert_source = alert_source
        self._profiles_by_label: dict[str, RequestBabyProfile] = {}
        self._profiles_by_numeric_id: dict[int, RequestBabyProfile] = {}
        self._ordered_labels: list[str] = []

    def seed_babies(self, babies: Sequence[Any]) -> None:
        self._profiles_by_label.clear()
        self._profiles_by_numeric_id.clear()
        self._ordered_labels.clear()

        for index, baby in enumerate(sorted(babies, key=lambda item: item.nicu_bed), start=1):
            profile = RequestBabyProfile(
                id=int(baby.id),
                nicu_bed=str(baby.nicu_bed),
                name=str(baby.name),
                index=index,
            )
            self._profiles_by_label[profile.nicu_bed] = profile
            self._profiles_by_numeric_id[profile.id] = profile
            self._ordered_labels.append(profile.nicu_bed)

    def generate_overview(self) -> dict[str, Any]:
        generated_at = datetime.now(timezone.utc)
        babies = [
            self._build_baby_snapshot(self._profiles_by_label[label], position=index, timestamp=generated_at)
            for index, label in enumerate(self._ordered_labels, start=1)
        ]
        alerts: list[dict[str, Any]] = []
        if self._alert_source is not None:
            alerts = list(self._alert_source.get_overview().get("alerts", []))

        return {
            "generated_at": generated_at,
            "babies": babies,
            "alerts": alerts,
        }

    def generate_baby_payload(self, identifier: int | str) -> dict[str, Any] | None:
        profile = self._resolve_profile(identifier)
        if profile is None:
            return None

        timestamp = datetime.now(timezone.utc)
        snapshot = self._build_baby_snapshot(profile, position=profile.index, timestamp=timestamp)
        return {
            "id": snapshot["id"],
            "name": snapshot["name"],
            "vitals": snapshot["vitals"],
            "chartData": snapshot["chartData"],
            "ecgChartData": snapshot["ecgChartData"],
            "bpChartData": snapshot["bpChartData"],
            "lastUpdated": snapshot["lastUpdated"],
            "timestamp": time.time(),
        }

    def _resolve_profile(self, identifier: int | str) -> RequestBabyProfile | None:
        if isinstance(identifier, int):
            return self._profiles_by_numeric_id.get(identifier)

        value = str(identifier)
        if value.isdigit():
            numeric = self._profiles_by_numeric_id.get(int(value))
            if numeric is not None:
                return numeric

        return self._profiles_by_label.get(value)

    def _build_baby_snapshot(
        self,
        profile: RequestBabyProfile,
        position: int,
        timestamp: datetime,
    ) -> dict[str, Any]:
        vitals = self._generate_vitals(profile)
        predicted_heart_rate = int(round(_clamp(vitals["heartRate"] + random.randint(-4, 4), 118, 168)))
        predicted_spo2 = int(round(_clamp(vitals["spo2"] + random.randint(-1, 1), 92, 100)))
        risk_score = self._compute_risk_score(vitals)
        status = self._categorize_status(risk_score)
        chart_data = self._generate_chart_data(profile, vitals, predicted_heart_rate, predicted_spo2)
        ecg_chart_data = self._generate_ecg_chart_data(profile)
        bp_chart_data = self._generate_bp_chart_data(profile, vitals)
        reasons = self._build_reasons(vitals, status)

        return {
            "id": profile.nicu_bed,
            "numericId": profile.id,
            "bed": f"B-{position:02d}",
            "name": profile.name,
            "ageLabel": f"{5 + position} days",
            "gestation": f"{29 + (position % 5)} weeks",
            "status": status.lower(),
            "riskScore": risk_score,
            "vitals": vitals,
            "trend": {
                "heartRate": "up" if predicted_heart_rate > vitals["heartRate"] else "down" if predicted_heart_rate < vitals["heartRate"] else "steady",
                "spo2": "up" if predicted_spo2 > vitals["spo2"] else "down" if predicted_spo2 < vitals["spo2"] else "steady",
            },
            "prediction": {
                "predictedHeartRate": predicted_heart_rate,
                "predictedSpo2": predicted_spo2,
                "riskLevel": status,
                "reasons": reasons,
                "anomalyLabel": "normal" if status == "STABLE" else "trend-watch",
                "earlyWarning": status != "STABLE",
            },
            "chartData": chart_data,
            "ecgChartData": ecg_chart_data,
            "bpChartData": bp_chart_data,
            "lastUpdated": _format_timestamp(timestamp),
        }

    def _generate_vitals(self, profile: RequestBabyProfile) -> dict[str, Any]:
        current_time = time.time()
        phase = current_time * 0.7 + profile.index * 0.91

        heart_rate = int(
            round(
                _clamp(
                    140.0 + 9.5 * math.sin(phase) + random.randint(-4, 4),
                    120.0,
                    160.0,
                )
            )
        )
        spo2 = int(
            round(
                _clamp(
                    97.0 + 2.0 * math.cos(phase * 0.8) + random.randint(-1, 1),
                    94.0,
                    100.0,
                )
            )
        )
        respiration = int(
            round(
                _clamp(
                    44.0 + 7.5 * math.sin(phase * 0.55) + random.randint(-3, 3),
                    30.0,
                    60.0,
                )
            )
        )
        temperature = round(
            _clamp(
                36.8 + 0.35 * math.cos(phase * 0.42) + random.uniform(-0.12, 0.12),
                36.2,
                37.5,
            ),
            1,
        )

        return {
            "heartRate": heart_rate,
            "spo2": spo2,
            "respiration": respiration,
            "temperature": temperature,
        }

    def _generate_chart_data(
        self,
        profile: RequestBabyProfile,
        vitals: dict[str, Any],
        predicted_heart_rate: int,
        predicted_spo2: int,
    ) -> list[dict[str, float | str | None]]:
        current_time = time.time()
        actual_points: list[dict[str, float | str | None]] = []
        future_points: list[dict[str, float | str | None]] = []

        for seconds_ago in range(10, -1, -1):
            phase = current_time - seconds_ago + profile.index * 0.17
            actual_points.append(
                {
                    "label": f"-{seconds_ago}s",
                    "heartRate": round(
                        _clamp(vitals["heartRate"] + math.sin(phase) * 3 + random.randint(-2, 2), 115.0, 170.0),
                        1,
                    ),
                    "predictedHeartRate": None,
                    "spo2": round(
                        _clamp(vitals["spo2"] + math.cos(phase * 0.75) * 1.3 + random.uniform(-0.6, 0.6), 92.0, 100.0),
                        1,
                    ),
                    "predictedSpo2": None,
                }
            )

        for step in range(1, 13):
            future_points.append(
                {
                    "label": f"+{step}s",
                    "heartRate": None,
                    "predictedHeartRate": round(
                        _clamp(predicted_heart_rate + math.sin((current_time + step) * 0.4) * 2.2, 115.0, 170.0),
                        1,
                    ),
                    "spo2": None,
                    "predictedSpo2": round(
                        _clamp(predicted_spo2 + math.cos((current_time + step) * 0.33) * 0.8, 92.0, 100.0),
                        1,
                    ),
                }
            )

        return actual_points + future_points

    def _generate_ecg_chart_data(self, profile: RequestBabyProfile) -> list[dict[str, float | str | None]]:
        base_time = time.time() + profile.index * 0.37
        actual_points = [
            {
                "label": f"-{47 - index}",
                "ecg": round(
                    math.sin(base_time * 2.0 + index * 0.2)
                    + 0.28 * math.sin(base_time * 4.6 + index * 0.31)
                    + random.uniform(-0.2, 0.2),
                    3,
                ),
                "predictedEcg": None,
            }
            for index in range(48)
        ]
        future_points = [
            {
                "label": f"+{index + 1}",
                "ecg": None,
                "predictedEcg": round(
                    math.sin((base_time + 0.35) * 2.0 + index * 0.2)
                    + 0.24 * math.sin((base_time + 0.35) * 4.2 + index * 0.3)
                    + random.uniform(-0.12, 0.12),
                    3,
                ),
            }
            for index in range(20)
        ]
        return actual_points + future_points

    def _generate_bp_chart_data(
        self,
        profile: RequestBabyProfile,
        vitals: dict[str, Any],
    ) -> list[dict[str, float | str | None]]:
        current_time = time.time() + profile.index * 0.21
        base_systolic = _clamp(76.0 + (vitals["heartRate"] - 140) * 0.16 + (vitals["temperature"] - 36.8) * 4.0, 62.0, 92.0)
        base_diastolic = _clamp(42.0 + (vitals["heartRate"] - 140) * 0.08 + (vitals["temperature"] - 36.8) * 2.1, 32.0, 58.0)

        actual_points: list[dict[str, float | str | None]] = []
        future_points: list[dict[str, float | str | None]] = []

        for seconds_ago in range(10, -1, -1):
            phase = current_time - seconds_ago
            systolic = round(_clamp(base_systolic + math.sin(phase * 0.7) * 2.2 + random.uniform(-1.1, 1.1), 60.0, 90.0), 1)
            diastolic = round(_clamp(min(base_diastolic + math.cos(phase * 0.6) * 1.4 + random.uniform(-0.8, 0.8), systolic - 16.0), 30.0, 60.0), 1)
            actual_points.append(
                {
                    "label": f"-{seconds_ago}s",
                    "systolic": systolic,
                    "predictedSystolic": None,
                    "diastolic": diastolic,
                    "predictedDiastolic": None,
                }
            )

        for step in range(1, 13):
            future_systolic = round(
                _clamp(base_systolic + math.sin((current_time + step) * 0.35) * 1.7 + random.uniform(-0.7, 0.7), 60.0, 90.0),
                1,
            )
            future_diastolic = round(
                _clamp(
                    min(base_diastolic + math.cos((current_time + step) * 0.31) * 1.1 + random.uniform(-0.5, 0.5), future_systolic - 16.0),
                    30.0,
                    60.0,
                ),
                1,
            )
            future_points.append(
                {
                    "label": f"+{step}s",
                    "systolic": None,
                    "predictedSystolic": future_systolic,
                    "diastolic": None,
                    "predictedDiastolic": future_diastolic,
                }
            )

        return actual_points + future_points

    def _compute_risk_score(self, vitals: dict[str, Any]) -> int:
        score = 12.0
        score += max(0.0, abs(vitals["heartRate"] - 140) * 1.2)
        score += max(0.0, 97 - vitals["spo2"]) * 9.0
        score += max(0.0, abs(vitals["temperature"] - 36.8) * 20.0)
        score += max(0.0, abs(vitals["respiration"] - 42) * 1.4)
        return int(round(_clamp(score, 8.0, 96.0)))

    def _categorize_status(self, risk_score: int) -> str:
        if risk_score >= 70:
            return "CRITICAL"
        if risk_score >= 40:
            return "WARNING"
        return "STABLE"

    def _build_reasons(self, vitals: dict[str, Any], status: str) -> list[str]:
        reasons: list[str] = []
        if vitals["spo2"] <= 94:
            reasons.append(f"SpO2 is at {vitals['spo2']}% and needs closer observation.")
        if vitals["heartRate"] >= 156:
            reasons.append(f"Heart rate is elevated at {vitals['heartRate']} bpm.")
        if vitals["temperature"] >= 37.3:
            reasons.append(f"Temperature is trending high at {vitals['temperature']:.1f} C.")
        if vitals["respiration"] >= 56:
            reasons.append(f"Respiration is elevated at {vitals['respiration']} rpm.")
        if not reasons:
            if status == "STABLE":
                reasons.append("Vitals remain within expected neonatal operating bounds.")
            else:
                reasons.append("Trend variability suggests closer monitoring is required.")
        return reasons[:3]
