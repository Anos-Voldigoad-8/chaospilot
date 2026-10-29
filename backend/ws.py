"""WebSocket fan-out for the live ChaosPilot dashboard."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

LOGGER = logging.getLogger(__name__)


class EventHub:
    """Tracks connected clients and broadcasts JSON events to all of them."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        LOGGER.info("websocket connected (%s clients)", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        LOGGER.info("websocket disconnected (%s clients)", len(self._connections))

    async def broadcast(self, event: dict[str, Any]) -> None:
        """Send one event to every client, dropping sockets that fail."""
        if not self._connections:
            return
        stale: list[WebSocket] = []
        for websocket in list(self._connections):
            try:
                await websocket.send_json(event)
            except Exception as exc:  # a client closing mid-send is normal
                LOGGER.debug("dropping websocket after send failure: %s", exc)
                stale.append(websocket)
        for websocket in stale:
            self._connections.discard(websocket)

    async def log(self, level: str, text: str) -> None:
        await self.broadcast({"type": "log", "level": level, "text": text})
