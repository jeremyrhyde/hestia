"""Device driver registry.

The registry is a flat ``device_id -> DeviceDriver`` map. The core API
dispatches every device-targeted call through this layer; ``core/`` is not
permitted to import concrete driver classes directly.

All accessor methods are async because :class:`drivers.base.DeviceDriver` is
async — see the design note in ``drivers/base.py``.

Event publishing
----------------

Phase 3 moved the ``DEVICE_STATE_CHANGED`` publish out of
:class:`core.scenes.SceneEngine` and into :meth:`DriverRegistry.execute_action`
so the bus broadcast fires uniformly regardless of caller (API handler,
scene engine, scheduler, voice). Construct the registry with
``event_bus=<EventBus>`` to opt in. The registry never imports
``core.events`` at runtime — that would violate the dependency rule
(``drivers/`` must not depend on ``core/``). The bus is duck-typed and only
referenced via :data:`TYPE_CHECKING` for IDE / type-checker support.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from drivers.base import DeviceDriver
from schemas.device import DeviceAction, DeviceInfo, DeviceState
from schemas.events import Event, EventType

if TYPE_CHECKING:  # pragma: no cover - type-checking only
    from core.events import EventBus  # noqa: F401

logger = logging.getLogger(__name__)


class DriverRegistry:
    """Holds the active set of drivers keyed by device ID."""

    def __init__(self, event_bus: "Any | None" = None) -> None:
        """Create an empty registry.

        Args:
            event_bus: Optional event bus. When provided, the registry
                publishes a :class:`Event` of type ``DEVICE_STATE_CHANGED``
                after each successful :meth:`execute_action` call. Typed as
                ``Any`` at runtime to keep the dependency rule
                (``drivers/`` must not import ``core/``); see the module
                docstring.
        """

        self._drivers: dict[str, DeviceDriver] = {}
        self._bus = event_bus

    def register(self, device_id: str, driver: DeviceDriver) -> None:
        """Add (or replace) the driver for *device_id*.

        Replacing is allowed so the API layer can swap a driver instance
        without restarting (e.g. on config reload).
        """

        self._drivers[device_id] = driver

    def device_ids(self) -> list[str]:
        """Return the IDs of every registered device.

        The system-level answer to "which devices exist?" — a cheap,
        I/O-free snapshot of the registry keys (unlike :meth:`list_devices`,
        which calls ``get_info`` on each driver). Returns a new list so
        callers can iterate safely while the registry is mutated.
        """

        return list(self._drivers.keys())

    def get(self, device_id: str) -> DeviceDriver:
        """Return the driver registered for *device_id*.

        Raises:
            KeyError: if no driver is registered for the given ID.
        """

        if device_id not in self._drivers:
            raise KeyError(f"no driver registered for device_id={device_id!r}")
        return self._drivers[device_id]

    async def list_devices(self) -> list[DeviceInfo]:
        """Return :class:`DeviceInfo` for every registered driver."""

        return [await driver.get_info() for driver in self._drivers.values()]

    async def execute_action(
        self,
        device_id: str,
        action: DeviceAction,
        *,
        source: str = "api",
    ) -> DeviceState:
        """Dispatch *action* to the driver for *device_id* and return the new state.

        After a successful dispatch, if an event bus was injected at
        construction, publish a :class:`Event` of type
        ``DEVICE_STATE_CHANGED`` with the resulting state. The *source*
        keyword argument lets callers identify where the action came
        from (default ``"api"``; the scene engine passes
        ``f"scene:{scene.id}"``).

        Raises:
            KeyError: if the device is not registered.
        """

        driver = self.get(device_id)
        new_state = await driver.execute(action)

        if self._bus is not None:
            try:
                await self._bus.publish(
                    Event(
                        type=EventType.DEVICE_STATE_CHANGED,
                        source=source,
                        device_id=device_id,
                        data={"state": new_state.model_dump(mode="json")},
                    )
                )
            except Exception:  # pragma: no cover - defensive
                logger.exception(
                    "DriverRegistry: failed to publish DEVICE_STATE_CHANGED for %s",
                    device_id,
                )

        return new_state

    async def close_all(self) -> None:
        """Close every registered driver that exposes ``async close()``.

        Drivers may optionally define an ``async def close(self)`` method to
        release hardware handles (GPIO pins, Kasa sockets, OAuth handles,
        etc.). Drivers without one are skipped. Exceptions are logged but
        never propagate so shutdown stays best-effort.
        """

        for device_id, driver in list(self._drivers.items()):
            close = getattr(driver, "close", None)
            if close is None:
                continue
            try:
                await close()
            except Exception:  # pragma: no cover - defensive
                logger.exception(
                    "DriverRegistry: error closing driver for %s", device_id
                )
