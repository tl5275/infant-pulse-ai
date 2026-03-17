from __future__ import annotations

import asyncio
import logging

from app.schemas.vital import VitalCreate
from app.services.monitoring import MonitoringService

logger = logging.getLogger(__name__)


class QueueSaturatedError(RuntimeError):
    """Raised when the ingestion queue is full."""


class IngestionService:
    def __init__(
        self,
        monitoring_service: MonitoringService,
        queue_size: int,
    ) -> None:
        self._monitoring_service = monitoring_service
        self._queue: asyncio.Queue[VitalCreate | None] = asyncio.Queue(maxsize=queue_size)
        self._worker_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._worker_task is not None and not self._worker_task.done():
            return

        self._worker_task = asyncio.create_task(self._consume_queue(), name="vital-ingestion-worker")
        logger.info("Started ingestion worker")

    async def stop(self) -> None:
        if self._worker_task is None:
            return

        await self._queue.put(None)
        await self._worker_task
        self._worker_task = None
        logger.info("Stopped ingestion worker")

    async def enqueue(self, payload: VitalCreate) -> None:
        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull as exc:
            raise QueueSaturatedError("Vital ingestion queue is full") from exc

    async def _consume_queue(self) -> None:
        while True:
            payload = await self._queue.get()
            try:
                if payload is None:
                    return
                await self._monitoring_service.process_vital_payload(payload)
            except Exception:
                logger.exception("Failed to process vital payload")
            finally:
                self._queue.task_done()
