"""WebSocket support for live ECG updates."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


def attach_live_websocket(
    app: FastAPI,
    latest_data_provider: Callable[[], dict[str, object]],
) -> None:
    """Register a live WebSocket endpoint that streams the latest prediction."""

    @app.websocket("/ws/live")
    async def live_stream(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(latest_data_provider())
                await asyncio.sleep(0.5)
        except WebSocketDisconnect:
            logger.info("Dashboard disconnected from /ws/live")
        except RuntimeError:
            logger.info("WebSocket transport closed for /ws/live")
