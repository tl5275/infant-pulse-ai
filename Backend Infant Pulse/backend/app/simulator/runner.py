from __future__ import annotations

import asyncio
import logging

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.simulator.analysis_streamer import MultiBabyAnalysisStreamer


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    simulator = MultiBabyAnalysisStreamer(
        api_url=settings.simulator_api_url,
        baby_count=settings.simulator_baby_count,
        interval_seconds=settings.simulator_interval_seconds,
        anomaly_probability=settings.simulator_anomaly_probability,
    )
    stop_event = asyncio.Event()
    await simulator.run(stop_event)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Simulator stopped")
