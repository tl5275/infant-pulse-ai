from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
import numpy as np

from app.ai import simulate_ecg_waveform


@dataclass(slots=True)
class StreamBabyState:
    baby_id: int
    label: str
    heart_rate: float
    spo2: float
    temperature: float
    respiration: float
    history: list[dict[str, float]] = field(default_factory=list)


def _clamp(value: float, lower: float, upper: float) -> float:
    return float(max(lower, min(value, upper)))


class MultiBabyAnalysisStreamer:
    """Posts multi-baby ECG analysis payloads into the unified backend."""

    def __init__(
        self,
        api_url: str,
        baby_count: int,
        interval_seconds: float,
        anomaly_probability: float,
        seed: int = 42,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.baby_count = baby_count
        self.interval_seconds = interval_seconds
        self.anomaly_probability = anomaly_probability
        self._rng = np.random.default_rng(seed)
        self._states: dict[int, StreamBabyState] = {}

    async def run(self, stop_event) -> None:
        async with httpx.AsyncClient(base_url=self.api_url, timeout=20.0) as client:
            babies = await self._fetch_babies(client)
            if not babies:
                raise RuntimeError("No babies available for streaming.")

            selected = babies[: self.baby_count]
            while not stop_event.is_set():
                payloads = [self._build_payload(baby) for baby in selected]
                await asyncio.gather(*(self._post_payload(client, payload) for payload in payloads))
                await asyncio.sleep(self.interval_seconds)

    async def _fetch_babies(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        response = await client.get("/babies")
        response.raise_for_status()
        return response.json()

    def _build_payload(self, baby: dict[str, Any]) -> dict[str, Any]:
        baby_id = int(baby["id"])
        label = str(baby["nicu_bed"])
        state = self._states.setdefault(
            baby_id,
            StreamBabyState(
                baby_id=baby_id,
                label=label,
                heart_rate=float(self._rng.normal(142.0, 5.0)),
                spo2=float(self._rng.normal(97.2, 0.8)),
                temperature=float(self._rng.normal(36.8, 0.12)),
                respiration=float(self._rng.normal(42.0, 3.0)),
                history=[],
            ),
        )

        anomaly = bool(self._rng.random() < self.anomaly_probability)
        heart_rate_shift = float(self._rng.normal(0.0, 1.2))
        spo2_shift = float(self._rng.normal(0.0, 0.15))
        temperature_shift = float(self._rng.normal(0.0, 0.03))
        respiration_shift = float(self._rng.normal(0.0, 0.8))

        if anomaly:
            heart_rate_shift += float(self._rng.uniform(1.4, 3.1))
            spo2_shift -= float(self._rng.uniform(0.6, 1.5))
            respiration_shift += float(self._rng.uniform(0.6, 1.7))

        state.heart_rate = _clamp(state.heart_rate + heart_rate_shift, 100.0, 188.0)
        state.spo2 = _clamp(state.spo2 + spo2_shift, 84.0, 100.0)
        state.temperature = _clamp(state.temperature + temperature_shift, 36.0, 38.6)
        state.respiration = _clamp(state.respiration + respiration_shift, 24.0, 74.0)

        latest_vitals = {
            "heart_rate": round(state.heart_rate, 2),
            "spo2": round(state.spo2, 2),
            "temperature": round(state.temperature, 2),
            "respiration": round(state.respiration, 2),
        }
        state.history = [*state.history[-11:], latest_vitals]
        while len(state.history) < 12:
            state.history.insert(0, latest_vitals)

        ecg = simulate_ecg_waveform(
            heart_rate=latest_vitals["heart_rate"],
            anomaly=anomaly or latest_vitals["spo2"] < 91.0 or latest_vitals["heart_rate"] > 175.0,
            rng=self._rng,
        )
        return {
            "baby_id": baby_id,
            "vitals": state.history,
            "ecg": np.round(ecg, 6).tolist(),
            "sampling_rate": 250.0,
            "persist": True,
        }

    async def _post_payload(self, client: httpx.AsyncClient, payload: dict[str, Any]) -> None:
        response = await client.post("/analyze", json=payload)
        response.raise_for_status()
