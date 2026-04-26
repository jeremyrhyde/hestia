"""In-process async event bus.

The event bus is the connective tissue between decoupled components. The
device manager (or scene engine) publishes events without knowing who
listens; the state store, websocket manager, and any future subscribers
register interest in particular event types and react.

Design notes
------------

- Subscribers are async callables: ``async def cb(event: Event) -> None``.
- ``publish`` invokes every subscriber concurrently via ``asyncio.gather``
  with ``return_exceptions=True`` so one failing subscriber cannot kill
  the rest. Exceptions are logged.
- A module-level :func:`get_event_bus` returns a process-wide singleton, but
  callers (especially tests) can also instantiate :class:`EventBus`
  directly and inject it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from schemas.events import Event, EventType

logger = logging.getLogger(__name__)

AsyncCallback = Callable[[Event], Awaitable[None]]


class EventBus:
    """Async pub/sub bus keyed by :class:`EventType`.

    Subscribers are stored in an insertion-ordered list per event type so
    publish order is deterministic for tests. The bus does not buffer
    events — ``publish`` invokes subscribers immediately.
    """

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[AsyncCallback]] = {}

    def subscribe(self, event_type: EventType, callback: AsyncCallback) -> None:
        """Register *callback* to receive events of *event_type*."""

        self._subscribers.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type: EventType, callback: AsyncCallback) -> None:
        """Remove *callback* from *event_type*'s subscriber list.

        No-op if the callback was not registered (so callers can safely
        unsubscribe in cleanup paths without tracking state).
        """

        subs = self._subscribers.get(event_type)
        if not subs:
            return
        try:
            subs.remove(callback)
        except ValueError:
            pass

    async def publish(self, event: Event) -> None:
        """Dispatch *event* to every subscriber for ``event.type``.

        Subscribers run concurrently. Any exception raised by a subscriber
        is logged and absorbed — the publisher and other subscribers are
        not affected.
        """

        subs = list(self._subscribers.get(event.type, ()))
        if not subs:
            return

        results = await asyncio.gather(
            *(self._invoke(cb, event) for cb in subs),
            return_exceptions=True,
        )
        for cb, result in zip(subs, results):
            if isinstance(result, Exception):
                logger.exception(
                    "event subscriber %r raised while handling %s: %s",
                    getattr(cb, "__qualname__", repr(cb)),
                    event.type.value,
                    result,
                    exc_info=result,
                )

    @staticmethod
    async def _invoke(callback: AsyncCallback, event: Event) -> None:
        await callback(event)


_default_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the process-wide :class:`EventBus` singleton.

    Lazily instantiated on first call. Tests that need isolation should
    construct their own :class:`EventBus` directly rather than touching
    this singleton.
    """

    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus


def reset_event_bus() -> None:
    """Reset the singleton (test helper)."""

    global _default_bus
    _default_bus = None
