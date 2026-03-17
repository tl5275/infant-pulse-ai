from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import random
import time
from typing import Any, Sequence

from app.services.live_monitor import LiveMonitorService


def _clamp(value: float, lower: float, upper: float) -> float:
    return float(max(lower, min(value, upper)))


@dataclass(slots=True)
class RequestBabyState:
    id: int
    nicu_bed: str
    name: str
    heart_rate: float
    spo2: float
    temperature: float
    respiration: float
    tick: int = 0
    vitals_history: list[dict[str, float]] = field(default_factory=list)


class RequestTelemetryService:
    """Generates fresh vitals on each request without background workers."""

    def __init__(self, live_monitor: LiveMonitorService, history_size: int = 24) -> None:
        self._live_monitor = live_monitor
        self._history_size = history_size
        self._rng = random.Random()
        self._states_by_label: dict[str, RequestBabyState] = {}
        self._states_by_numeric_id: dict[int, RequestBabyState] = {}
        self._ordered_labels: list[str] = []

    def seed_babies(self, babies: Sequence[Any]) -> None:
        self._states_by_label.clear()
        self._states_by_numeric_id.clear()
        self._ordered_labels.clear()

        ordered_babies = sorted(babies, key=lambda item: item.nicu_bed)
        for index, baby in enumerate(ordered_babies, start=1):
            state = RequestBabyState(
                id=int(baby.id),
                nicu_bed=str(baby.nicu_bed),
                name=str(baby.name),
                heart_rate=138.0 + index,
                spo2=96.0 + (index % 2),
                temperature=36.6 + (index * 0.05),
                respiration=38.0 + (index % 5),
            )
            for _ in range(12):
                self._advance_state(state)

            self._states_by_label[state.nicu_bed] = state
            self._states_by_numeric_id[state.id] = state
            self._ordered_labels.append(state.nicu_bed)

    def refresh_all(self) -> dict[str, Any]:
        for label in self._ordered_labels:
            self.refresh_baby(label)
        return self._live_monitor.get_overview()

    def refresh_baby(self, identifier: int | str) -> dict[str, Any] | None:
        state = self._resolve_state(identifier)
        if state is None:
            return None

        history = self._advance_state(state)
        analysis_result = self._build_analysis(state, history)
        return self._live_monitor.update_baby(
            baby=state,
            vitals_history=history,
            analysis_result=analysis_result,
            timestamp=datetime.now(timezone.utc),
        )

    def get_baby_payload(self, identifier: int | str) -> dict[str, Any] | None:
        snapshot = self.refresh_baby(identifier)
        if snapshot is None:
            return None

        actual_bp = next(
            (
                point
                for point in reversed(snapshot.get("bpChartData", []))
                if point.get("systolic") is not None and point.get("diastolic") is not None
            ),
            None,
        )
        ecg = [point["ecg"] for point in snapshot.get("ecgChartData", []) if point.get("ecg") is not None]
        bp_value = int(round(float(actual_bp["systolic"]))) if actual_bp is not None else 80

        return {
            "id": snapshot["id"],
            "heart_rate": snapshot["vitals"]["heartRate"],
            "spo2": snapshot["vitals"]["spo2"],
            "temperature": snapshot["vitals"]["temperature"],
            "bp": bp_value,
            "ecg": ecg,
            "timestamp": time.time(),
        }

    def _resolve_state(self, identifier: int | str) -> RequestBabyState | None:
        if isinstance(identifier, int):
            return self._states_by_numeric_id.get(identifier)

        value = str(identifier)
        if value.isdigit():
            numeric_state = self._states_by_numeric_id.get(int(value))
            if numeric_state is not None:
                return numeric_state

        return self._states_by_label.get(value)

    def _advance_state(self, state: RequestBabyState) -> list[dict[str, float]]:
        previous = (
            int(round(state.heart_rate)),
            int(round(state.spo2)),
            round(state.temperature, 1),
            int(round(state.respiration)),
        )

        state.tick += 1
        phase = state.tick / 2.4 + state.id * 0.33

        state.heart_rate += self._rng.randint(-3, 3) + math.sin(phase) * 0.9
        state.spo2 += self._rng.randint(-1, 1) + math.cos(phase * 0.8) * 0.25
        state.temperature += self._rng.uniform(-0.1, 0.1) + math.sin(phase * 0.55) * 0.02
        state.respiration += self._rng.randint(-2, 2) + math.cos(phase * 0.65) * 0.5

        state.heart_rate = _clamp(state.heart_rate, 110.0, 180.0)
        state.spo2 = _clamp(state.spo2, 85.0, 100.0)
        state.temperature = _clamp(state.temperature, 35.0, 38.0)
        state.respiration = _clamp(state.respiration, 24.0, 70.0)

        current = (
            int(round(state.heart_rate)),
            int(round(state.spo2)),
            round(state.temperature, 1),
            int(round(state.respiration)),
        )
        if current == previous:
            direction = -1.0 if state.heart_rate >= 180.0 else 1.0
            state.heart_rate = _clamp(state.heart_rate + direction, 110.0, 180.0)

        state.vitals_history.append(
            {
                "heart_rate": float(int(round(state.heart_rate))),
                "spo2": float(int(round(state.spo2))),
                "temperature": float(round(state.temperature, 1)),
                "respiration": float(int(round(state.respiration))),
            }
        )
        state.vitals_history = state.vitals_history[-self._history_size :]
        return list(state.vitals_history)

    def _build_analysis(self, state: RequestBabyState, history: list[dict[str, float]]) -> dict[str, Any]:
        latest = history[-1]
        heart_rate = float(latest["heart_rate"])
        spo2 = float(latest["spo2"])
        temperature = float(latest["temperature"])
        respiration = float(latest["respiration"])

        risk_score = 0.12
        reasons: list[str] = []
        if heart_rate > 170.0 or heart_rate < 115.0:
            risk_score += 0.24
            reasons.append(f"Heart rate is outside the preferred NICU range at {heart_rate:.0f} bpm.")
        if spo2 < 93.0:
            risk_score += 0.32
            reasons.append(f"SpO2 is trending low at {spo2:.0f}%.")
        if temperature > 37.6 or temperature < 36.1:
            risk_score += 0.16
            reasons.append(f"Temperature is drifting to {temperature:.1f} C.")
        if respiration > 60.0 or respiration < 28.0:
            risk_score += 0.12
            reasons.append(f"Respiration is at {respiration:.0f} rpm.")

        risk_score = round(_clamp(risk_score, 0.08, 0.96), 4)
        if risk_score >= 0.7:
            status = "CRITICAL"
        elif risk_score >= 0.4:
            status = "WARNING"
        else:
            status = "STABLE"

        anomaly = "anomaly" if status != "STABLE" else "normal"
        early_warning = status != "STABLE"
        if not reasons:
            reasons.append("Vitals remain within expected neonatal operating bounds.")

        ecg_signal = self._generate_ecg(state)
        predicted_ecg = self._predict_ecg(ecg_signal)

        return {
            "risk_score": risk_score,
            "status": status,
            "anomaly": anomaly,
            "early_warning": early_warning,
            "message": reasons[0],
            "explanation": {
                "top_reasons": reasons[:3],
            },
            "ecg_signal": ecg_signal,
            "predicted_ecg": predicted_ecg,
        }

    def _generate_ecg(self, state: RequestBabyState, points: int = 180) -> list[float]:
        phase_offset = time.time() + state.tick * 0.12 + state.id * 0.5
        signal: list[float] = []
        for index in range(points):
            phase = phase_offset + index * 0.08
            value = math.sin(phase)
            value += 0.35 * math.sin(phase * 2.1)
            value += 0.12 * math.sin(phase * 6.0)
            value += self._rng.uniform(-0.05, 0.05)
            signal.append(round(value, 6))
        return signal

    def _predict_ecg(self, signal: list[float], horizon: int = 20) -> list[float]:
        seed = signal[-horizon:] if len(signal) >= horizon else signal
        if not seed:
            seed = [0.0]

        baseline = float(seed[-1])
        slope = (float(seed[-1]) - float(seed[0])) / max(len(seed) - 1, 1)
        return [
            round(
                _clamp(
                    baseline + slope * (index + 1) + self._rng.uniform(-0.03, 0.03),
                    -2.5,
                    2.5,
                ),
                6,
            )
            for index in range(horizon)
        ]
