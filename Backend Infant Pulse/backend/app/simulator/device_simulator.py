from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass

import httpx

from app.schemas.vital import VitalCreate

logger = logging.getLogger(__name__)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


@dataclass(slots=True)
class BabyState:
    heart_rate: int
    spo2: int
    temperature: float
    resp_rate: int


class DeviceSimulator:
    def __init__(
        self,
        api_url: str,
        baby_count: int,
        interval_seconds: float,
        anomaly_probability: float,
        rng: random.Random | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.baby_count = baby_count
        self.interval_seconds = interval_seconds
        self.anomaly_probability = anomaly_probability
        self._rng = rng or random.Random()
        self._states: dict[int, BabyState] = {}

    async def fetch_babies(self, client: httpx.AsyncClient) -> list[dict]:
        response = await client.get("/babies")
        response.raise_for_status()
        babies: list[dict] = response.json()
        return babies[: self.baby_count]

    def build_payload(self, baby_id: int) -> VitalCreate:
        state = self._states.setdefault(
            baby_id,
            BabyState(
                heart_rate=self._rng.randint(125, 155),
                spo2=self._rng.randint(94, 99),
                temperature=round(self._rng.uniform(36.4, 37.3), 1),
                resp_rate=self._rng.randint(35, 50),
            ),
        )

        normal_heart_rate = int(clamp(state.heart_rate + self._rng.randint(-3, 3), 110, 165))
        normal_spo2 = int(clamp(state.spo2 + self._rng.randint(-1, 1), 92, 100))
        normal_temperature = round(clamp(state.temperature + self._rng.uniform(-0.1, 0.1), 36.0, 37.7), 1)
        normal_resp_rate = int(clamp(state.resp_rate + self._rng.randint(-2, 2), 30, 60))

        state.heart_rate = normal_heart_rate
        state.spo2 = normal_spo2
        state.temperature = normal_temperature
        state.resp_rate = normal_resp_rate

        heart_rate = normal_heart_rate
        spo2 = normal_spo2

        if self._rng.random() < self.anomaly_probability:
            if self._rng.choice(["spo2_drop", "heart_rate_spike"]) == "spo2_drop":
                spo2 = self._rng.randint(85, 89)
            else:
                heart_rate = self._rng.randint(171, 185)

        return VitalCreate(
            baby_id=baby_id,
            heart_rate=heart_rate,
            spo2=spo2,
            temperature=normal_temperature,
            resp_rate=normal_resp_rate,
        )

    async def run(self) -> None:
        async with httpx.AsyncClient(base_url=self.api_url, timeout=10.0) as client:
            babies = await self.fetch_babies(client)
            if not babies:
                raise RuntimeError("No babies available to simulate. Start the API with DB seeding enabled.")

            baby_ids = [baby["id"] for baby in babies]
            logger.info("Simulator attached to baby_ids=%s", baby_ids)

            while True:
                payloads = [self.build_payload(baby_id).model_dump(mode="json") for baby_id in baby_ids]
                await asyncio.gather(*(self._send_payload(client, payload) for payload in payloads))
                await asyncio.sleep(self.interval_seconds)

    async def _send_payload(self, client: httpx.AsyncClient, payload: dict) -> None:
        response = await client.post("/vitals", json=payload)
        response.raise_for_status()
        logger.debug("Queued simulator payload=%s", payload)

