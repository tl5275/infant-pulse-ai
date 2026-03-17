"""Synthetic neonatal ECG and vital sign simulator."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass
class BabyState:
    """Mutable simulator state for a single infant."""

    baby_id: str
    heart_rate: float
    spo2: float
    temperature: float
    respiration: float
    vitals_history: deque[dict[str, float]] = field(default_factory=lambda: deque(maxlen=12))


def _clamp(value: float, lower: float, upper: float) -> float:
    """Clamp a scalar to a bounded interval."""
    return float(max(lower, min(value, upper)))


def simulate_ecg_waveform(
    duration_seconds: float = 4.0,
    sampling_rate: float = 250.0,
    heart_rate: float = 140.0,
    noise_scale: float = 0.02,
    anomaly: bool = False,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Generate a synthetic ECG waveform using sinusoidal rhythm and beat morphology."""
    generator = rng or np.random.default_rng()
    sample_count = int(duration_seconds * sampling_rate)
    timeline = np.arange(sample_count, dtype=float) / sampling_rate
    beat_period = 60.0 / max(heart_rate, 1.0)
    phase = np.mod(timeline, beat_period) / beat_period

    p_wave = 0.08 * np.exp(-((phase - 0.16) ** 2) / (2 * 0.018**2))
    q_wave = -0.12 * np.exp(-((phase - 0.30) ** 2) / (2 * 0.006**2))
    r_wave = 1.1 * np.exp(-((phase - 0.32) ** 2) / (2 * 0.004**2))
    s_wave = -0.22 * np.exp(-((phase - 0.35) ** 2) / (2 * 0.008**2))
    t_wave = 0.28 * np.exp(-((phase - 0.55) ** 2) / (2 * 0.05**2))

    baseline_wander = 0.03 * np.sin(2 * np.pi * 0.33 * timeline)
    rhythm = 0.02 * np.sin(2 * np.pi * (heart_rate / 60.0) * timeline)
    ecg = p_wave + q_wave + r_wave + s_wave + t_wave + baseline_wander + rhythm

    if anomaly:
        for burst_center in generator.choice(sample_count, size=3, replace=False):
            width = int(generator.integers(5, 18))
            amplitude = float(generator.uniform(-0.7, 0.9))
            end_index = min(sample_count, burst_center + width)
            ecg[burst_center:end_index] += amplitude * np.hanning(max(end_index - burst_center, 1))
        ecg += 0.05 * np.sin(2 * np.pi * 6.0 * timeline)

    ecg += generator.normal(0.0, noise_scale, sample_count)
    return ecg.astype(float)


class InfantPulseSimulator:
    """Stateful simulator that produces streaming payloads for multiple babies."""

    def __init__(
        self,
        num_babies: int = 5,
        sampling_rate: float = 250.0,
        history_length: int = 12,
        seed: int = 42,
    ) -> None:
        """Initialize baby baselines and prime each history buffer."""
        self.sampling_rate = sampling_rate
        self.history_length = history_length
        self.rng = np.random.default_rng(seed)
        self.babies = {
            f"baby_{index + 1:02d}": BabyState(
                baby_id=f"baby_{index + 1:02d}",
                heart_rate=float(self.rng.normal(142.0, 6.0)),
                spo2=float(self.rng.normal(97.0, 1.0)),
                temperature=float(self.rng.normal(36.8, 0.15)),
                respiration=float(self.rng.normal(42.0, 4.0)),
                vitals_history=deque(maxlen=history_length),
            )
            for index in range(num_babies)
        }

        for state in self.babies.values():
            for _ in range(history_length):
                state.vitals_history.append(self._next_vitals(state, force_anomaly=False))

    def _next_vitals(self, state: BabyState, force_anomaly: bool | None = None) -> dict[str, float]:
        """Advance one baby's vitals with bounded drift and optional risk trends."""
        anomaly = bool(force_anomaly) if force_anomaly is not None else bool(self.rng.random() < 0.12)

        heart_rate_shift = float(self.rng.normal(0.0, 1.4))
        spo2_shift = float(self.rng.normal(0.0, 0.18))
        temperature_shift = float(self.rng.normal(0.0, 0.04))
        respiration_shift = float(self.rng.normal(0.0, 0.9))

        if anomaly:
            heart_rate_shift += float(self.rng.uniform(1.5, 3.5))
            spo2_shift -= float(self.rng.uniform(0.4, 1.2))
            respiration_shift += float(self.rng.uniform(0.8, 2.0))

        state.heart_rate = _clamp(state.heart_rate + heart_rate_shift, 95.0, 195.0)
        state.spo2 = _clamp(state.spo2 + spo2_shift, 82.0, 100.0)
        state.temperature = _clamp(state.temperature + temperature_shift, 35.8, 38.6)
        state.respiration = _clamp(state.respiration + respiration_shift, 20.0, 78.0)

        return {
            "heart_rate": round(state.heart_rate, 2),
            "spo2": round(state.spo2, 2),
            "temperature": round(state.temperature, 2),
            "respiration": round(state.respiration, 2),
        }

    def get_next_payload(self, baby_id: str, force_anomaly: bool | None = None) -> dict[str, object]:
        """Generate the next streaming payload for a single infant."""
        state = self.babies[baby_id]
        latest_vitals = self._next_vitals(state, force_anomaly=force_anomaly)
        state.vitals_history.append(latest_vitals)

        anomaly = bool(force_anomaly) if force_anomaly is not None else latest_vitals["spo2"] < 92 or latest_vitals["heart_rate"] > 175
        ecg = simulate_ecg_waveform(
            duration_seconds=4.0,
            sampling_rate=self.sampling_rate,
            heart_rate=latest_vitals["heart_rate"],
            anomaly=anomaly,
            rng=self.rng,
        )
        return {
            "baby_id": baby_id,
            "vitals": list(state.vitals_history),
            "ecg": np.round(ecg, 6).tolist(),
            "sampling_rate": self.sampling_rate,
        }

    def generate_batch(self, force_anomaly: bool | None = None) -> list[dict[str, object]]:
        """Generate one payload per simulated baby."""
        return [
            self.get_next_payload(baby_id=baby_id, force_anomaly=force_anomaly)
            for baby_id in self.babies
        ]


def generate_training_payloads(
    num_samples: int = 240,
    num_babies: int = 8,
    seed: int = 42,
    force_anomaly: bool | None = False,
) -> list[dict[str, object]]:
    """Create synthetic inference payloads for model training or demos."""
    simulator = InfantPulseSimulator(num_babies=num_babies, seed=seed)
    baby_ids = list(simulator.babies.keys())
    payloads: list[dict[str, object]] = []
    for index in range(num_samples):
        baby_id = baby_ids[index % len(baby_ids)]
        payloads.append(simulator.get_next_payload(baby_id, force_anomaly=force_anomaly))
    return payloads


def generate_training_signals(
    num_signals: int = 64,
    duration_seconds: float = 6.0,
    sampling_rate: float = 250.0,
    anomaly_ratio: float = 0.0,
    seed: int = 42,
) -> list[np.ndarray]:
    """Generate ECG waveforms for LSTM training."""
    rng = np.random.default_rng(seed)
    signals: list[np.ndarray] = []
    for _ in range(num_signals):
        heart_rate = float(rng.normal(142.0, 8.0))
        anomaly = bool(rng.random() < anomaly_ratio)
        signals.append(
            simulate_ecg_waveform(
                duration_seconds=duration_seconds,
                sampling_rate=sampling_rate,
                heart_rate=heart_rate,
                anomaly=anomaly,
                rng=rng,
            )
        )
    return signals


def stream_to_api(
    api_url: str,
    num_babies: int = 5,
    interval_seconds: float = 1.0,
    iterations: int | None = None,
) -> None:
    """Continuously stream simulated infant data to the FastAPI analysis endpoint."""
    simulator = InfantPulseSimulator(num_babies=num_babies)
    cycle = 0

    while iterations is None or cycle < iterations:
        for payload in simulator.generate_batch():
            body = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                api_url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    result = json.loads(response.read().decode("utf-8"))
                print(
                    f"{payload['baby_id']}: status={result['status']}, "
                    f"risk={result['risk_score']}, anomaly={result['anomaly']['label']}"
                )
            except urllib.error.URLError as exc:
                print(f"Failed to send payload for {payload['baby_id']}: {exc}")
        cycle += 1
        time.sleep(interval_seconds)


def main() -> None:
    """Run the real-time simulator as a local API client."""
    parser = argparse.ArgumentParser(description="Infant Pulse real-time simulator")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/analyze")
    parser.add_argument("--num-babies", type=int, default=5)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--iterations", type=int, default=10)
    arguments = parser.parse_args()

    stream_to_api(
        api_url=arguments.api_url,
        num_babies=arguments.num_babies,
        interval_seconds=arguments.interval,
        iterations=arguments.iterations,
    )


if __name__ == "__main__":
    main()
