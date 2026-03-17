from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai import InferenceInput, MLInferenceService, simulate_ecg_waveform
from app.alerts.engine import build_alert_models, evaluate_vital
from app.models.alert import Alert
from app.models.baby import Baby
from app.models.vital import Vital
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.schemas.vital import VitalCreate, VitalRead
from app.services.live_monitor import LiveMonitorService
from app.services.vitals import build_vital_model

logger = logging.getLogger(__name__)


class MonitoringService:
    """Coordinates persistence, ML inference, alerts, and frontend snapshots."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ml_service: MLInferenceService,
        event_broadcast,
        live_broadcast,
        live_monitor: LiveMonitorService,
        recent_vitals_limit: int = 24,
    ) -> None:
        self._session_factory = session_factory
        self._ml_service = ml_service
        self._event_broadcast = event_broadcast
        self._live_broadcast = live_broadcast
        self._live_monitor = live_monitor
        self._recent_vitals_limit = recent_vitals_limit
        self._prediction_status: dict[int, str] = {}
        self._rng = np.random.default_rng(42)

    @property
    def model_ready(self) -> bool:
        return self._ml_service.is_ready

    async def bootstrap(self) -> None:
        async with self._session_factory() as session:
            result = await session.scalars(select(Baby).order_by(Baby.nicu_bed.asc()))
            babies = list(result.all())
        self._live_monitor.seed_babies(babies)

    def get_overview(self) -> dict[str, Any]:
        return self._live_monitor.get_overview()

    async def process_vital_payload(self, payload: VitalCreate) -> VitalRead:
        async with self._session_factory() as session:
            baby = await session.get(Baby, payload.baby_id)
            if baby is None:
                raise LookupError(f"Unknown baby_id={payload.baby_id}")

            vital = build_vital_model(payload)
            session.add(vital)
            await session.flush()

            history = await self._fetch_recent_history(session, baby.id)
            analysis_input = self._build_inference_input(
                baby_label=baby.nicu_bed,
                vitals_history=history,
            )
            analysis_result = self._ml_service.run_inference(analysis_input)

            threshold_alerts = build_alert_models(evaluate_vital(vital))
            predictive_alert = self._build_prediction_alert(baby.id, analysis_result, vital.timestamp)

            for alert in threshold_alerts:
                session.add(alert)
            if predictive_alert is not None:
                session.add(predictive_alert)

            await session.flush()
            emitted_alerts = threshold_alerts + ([predictive_alert] if predictive_alert is not None else [])
            await session.commit()

        await self._publish_update(baby, vital, history, analysis_result, emitted_alerts)
        return VitalRead.model_validate(vital)

    async def analyze_payload(self, payload: AnalyzeRequest) -> AnalyzeResponse:
        async with self._session_factory() as session:
            baby = await self._resolve_baby(session, payload.baby_id)
            if baby is None:
                raise LookupError(f"Unknown baby reference: {payload.baby_id}")

            normalized_history = self._normalize_history(payload.vitals)
            latest_vital = normalized_history[-1]
            timestamp = datetime.now(timezone.utc)
            emitted_alerts: list[Alert] = []
            vital_model: Vital | None = None

            if payload.persist:
                vital_model = build_vital_model(
                    VitalCreate(
                        baby_id=baby.id,
                        heart_rate=int(round(latest_vital["heart_rate"])),
                        spo2=int(round(latest_vital["spo2"])),
                        temperature=float(latest_vital["temperature"]),
                        resp_rate=int(round(latest_vital["respiration"])),
                        timestamp=timestamp,
                    )
                )
                session.add(vital_model)
                await session.flush()
                timestamp = vital_model.timestamp

            analysis_result = self._ml_service.run_inference(
                InferenceInput(
                    baby_id=baby.nicu_bed,
                    vitals_history=normalized_history,
                    ecg=payload.ecg,
                    sampling_rate=payload.sampling_rate,
                )
            )

            if payload.persist and vital_model is not None:
                threshold_alerts = build_alert_models(evaluate_vital(vital_model))
                predictive_alert = self._build_prediction_alert(baby.id, analysis_result, timestamp)
                for alert in threshold_alerts:
                    session.add(alert)
                if predictive_alert is not None:
                    session.add(predictive_alert)
                await session.flush()
                emitted_alerts = threshold_alerts + ([predictive_alert] if predictive_alert is not None else [])
                await session.commit()

        if payload.persist:
            await self._publish_update(baby, vital_model, normalized_history, analysis_result, emitted_alerts)

        return AnalyzeResponse(
            baby_numeric_id=baby.id,
            **analysis_result,
        )

    async def _resolve_baby(self, session: AsyncSession, identifier: int | str) -> Baby | None:
        if isinstance(identifier, int):
            return await session.get(Baby, identifier)

        value = str(identifier)
        if value.isdigit():
            numeric = await session.get(Baby, int(value))
            if numeric is not None:
                return numeric

        result = await session.scalars(select(Baby).where(Baby.nicu_bed == value))
        return result.first()

    async def _fetch_recent_history(self, session: AsyncSession, baby_id: int) -> list[dict[str, float]]:
        result = await session.scalars(
            select(Vital)
            .where(Vital.baby_id == baby_id)
            .order_by(Vital.timestamp.desc())
            .limit(self._recent_vitals_limit)
        )
        vitals = list(result.all())
        vitals.reverse()
        return [
            {
                "heart_rate": float(vital.heart_rate),
                "spo2": float(vital.spo2),
                "temperature": float(vital.temperature),
                "respiration": float(vital.resp_rate),
            }
            for vital in vitals
        ]

    def _normalize_history(self, vitals: list[Any]) -> list[dict[str, float]]:
        return [
            {
                "heart_rate": float(vital.heart_rate),
                "spo2": float(vital.spo2),
                "temperature": float(vital.temperature),
                "respiration": float(vital.respiration),
            }
            for vital in vitals
        ]

    def _build_inference_input(
        self,
        baby_label: str,
        vitals_history: list[dict[str, float]],
    ) -> InferenceInput:
        latest = vitals_history[-1] if vitals_history else {
            "heart_rate": 140.0,
            "spo2": 97.0,
            "temperature": 36.8,
            "respiration": 40.0,
        }
        anomaly = latest["spo2"] < 92.0 or latest["heart_rate"] > 175.0 or latest["temperature"] > 37.8
        ecg = simulate_ecg_waveform(
            heart_rate=float(latest["heart_rate"]),
            anomaly=anomaly,
            rng=self._rng,
        )
        return InferenceInput(
            baby_id=baby_label,
            vitals_history=vitals_history,
            ecg=np.round(ecg, 6).tolist(),
            sampling_rate=250.0,
        )

    def _build_prediction_alert(
        self,
        baby_id: int,
        analysis_result: dict[str, Any],
        timestamp: datetime,
    ) -> Alert | None:
        status = str(analysis_result.get("status", "STABLE")).upper()
        if status == "STABLE":
            self._prediction_status[baby_id] = status
            return None

        previous = self._prediction_status.get(baby_id)
        self._prediction_status[baby_id] = status
        if previous == status:
            return None

        severity = "CRITICAL" if status == "CRITICAL" else "WARNING"
        return Alert(
            baby_id=baby_id,
            alert_type=f"PREDICTIVE_{status}",
            severity=severity,
            message=str(analysis_result.get("message", "Predictive monitoring flagged a rising risk trend.")),
            timestamp=timestamp,
        )

    async def _publish_update(
        self,
        baby: Baby,
        vital: Vital | None,
        vitals_history: list[dict[str, float]],
        analysis_result: dict[str, Any],
        alerts: list[Alert],
    ) -> None:
        timestamp = vital.timestamp if vital is not None else datetime.now(timezone.utc)
        self._live_monitor.update_baby(
            baby=baby,
            vitals_history=vitals_history,
            analysis_result=analysis_result,
            timestamp=timestamp,
        )
        self._live_monitor.record_alerts(alerts)

        if vital is not None:
            await self._event_broadcast(
                {
                    "event": "vital",
                    "data": VitalRead.model_validate(vital).model_dump(mode="json"),
                }
            )

        for alert in alerts:
            await self._event_broadcast(
                {
                    "event": "alert",
                    "data": {
                        "id": alert.id,
                        "baby_id": alert.baby_id,
                        "alert_type": alert.alert_type,
                        "severity": alert.severity,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat(),
                    },
                }
            )

        await self._live_broadcast(jsonable_encoder(self._live_monitor.get_overview()))
