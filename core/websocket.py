"""WebSocket connection manager.

Maintains the set of currently-connected frontend WebSocket clients and
broadcasts :class:`Event` objects to all of them. Plugs into the
:class:`core.events.EventBus` by subscribing :meth:`broadcast` to
``DEVICE_STATE_CHANGED`` and ``SCENE_EXECUTED`` event types — the API
layer never has to broadcast manually, the bus does it.

Failure isolation
-----------------

A single dead client must never block the others. :meth:`broadcast`
fires every send concurrently via :func:`asyncio.gather` with
``return_exceptions=True``; any connection that raises is dropped from
the active set silently.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

from core.events import EventBus
from schemas.events import Event, EventType

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Tracks active WebSocket connections and broadcasts events to them."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    async def connect(self, websocket: WebSocket) -> None:
        """Accept the upgrade and register *websocket*."""

        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.debug(
            "WebSocketManager: client connected (total=%d)",
            len(self._connections),
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove *websocket* from the active set.

        No-op if the connection was already removed (e.g. by a failed
        broadcast). Safe to call multiple times.
        """

        async with self._lock:
            self._connections.discard(websocket)
        logger.debug(
            "WebSocketManager: client disconnected (total=%d)",
            len(self._connections),
        )

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------
    async def broadcast(self, event: Event) -> None:
        """Send the JSON-serialized *event* to every connected client.

        Connections that fail to send (closed sockets, network errors)
        are silently dropped from the active set.
        """

        # Snapshot the set so concurrent connect/disconnect don't mutate
        # us mid-loop.
        async with self._lock:
            targets = list(self._connections)

        if not targets:
            return

        payload = event.model_dump_json()
        results = await asyncio.gather(
            *(self._send(ws, payload) for ws in targets),
            return_exceptions=True,
        )

        dead: list[WebSocket] = []
        for ws, result in zip(targets, results):
            if isinstance(result, Exception):
                dead.append(ws)
                logger.debug(
                    "WebSocketManager: dropping client after send error: %r",
                    result,
                )

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)

    @staticmethod
    async def _send(websocket: WebSocket, payload: str) -> None:
        await websocket.send_text(payload)

    # ------------------------------------------------------------------
    # Bus integration
    # ------------------------------------------------------------------
    def subscribe_to_bus(self, bus: EventBus) -> None:
        """Wire the manager's :meth:`broadcast` into *bus*.

        Subscribes to ``DEVICE_STATE_CHANGED`` and ``SCENE_EXECUTED`` —
        the two event types the touchscreen UI cares about for
        real-time sync.
        """

        bus.subscribe(EventType.DEVICE_STATE_CHANGED, self.broadcast)
        bus.subscribe(EventType.SCENE_EXECUTED, self.broadcast)

    @property
    def active_count(self) -> int:
        """Number of connections currently in the active set."""

        return len(self._connections)
