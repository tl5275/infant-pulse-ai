from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info("WebSocket client connected. active_connections=%s", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("WebSocket client disconnected. active_connections=%s", len(self._connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            recipients = list(self._connections)

        if not recipients:
            return

        stale_connections: list[WebSocket] = []
        for websocket in recipients:
            try:
                await websocket.send_json(message)
            except Exception:
                stale_connections.append(websocket)

        if stale_connections:
            async with self._lock:
                for websocket in stale_connections:
                    self._connections.discard(websocket)
            logger.warning("Removed %s stale WebSocket connection(s)", len(stale_connections))

