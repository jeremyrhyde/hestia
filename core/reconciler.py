"""Device state reconciliation loop.

The UI is a write-through cache: it learns a device's state only when
*Hestia itself* changes it (via ``DriverRegistry.execute_action`` →
``DEVICE_STATE_CHANGED`` → WebSocket). Anything that moves a device
*outside* Hestia — the vendor's own app (e.g. Kasa/Casa), a cloud
schedule running on the device, or a physical switch — never travels
that path, so the cached state (and therefore the UI toggle) silently
drifts from reality.

The reconciler closes that gap **non-intrusively**: it periodically
*reads* each device's live state and, only when it differs from the
cached state in the :class:`~core.state.StateStore`, publishes a
``DEVICE_STATE_CHANGED`` event through the same bus the rest of the
system already uses. Everything downstream — state-store persistence
(``StateStore._on_state_changed``) and WebSocket broadcast
(``WebSocketManager.broadcast``) — then runs unchanged.

Design notes
------------

- **Observe, never command.** The loop calls ``driver.get_state()`` and
  nothing else. It never turns a device on or off, so the vendor app /
  device schedules stay fully authoritative over the hardware — Hestia's
  UI just stops lying about them.
- **Silent when nothing drifted.** An event is published only on an
  actual state difference, so a steady-state system produces no bus
  traffic and no UI flicker.
- **Gated on viewers.** Ticks are skipped entirely when no WebSocket
  client is connected — there's no point correcting a cache nobody is
  watching, and it keeps idle Pis quiet.
- **Failure isolation.** Each device is read in its own try/except; one
  unreachable bulb cannot stall or kill the loop. Reads are staggered by
  a small delay so all devices aren't probed in a single burst.

Mirrors :class:`core.scheduler.Scheduler`'s lifecycle (``start``/``stop``
managing a single background ``asyncio.Task`` guarded by a stop event).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from schemas.events import Event, EventType

if TYPE_CHECKING:  # pragma: no cover - type-checking only
    from core.events import EventBus
    from core.state import StateStore
    from core.websocket import WebSocketManager
    from drivers.registry import DriverRegistry

logger = logging.getLogger(__name__)


class StateReconciler:
    """Background loop that corrects UI/cache drift from out-of-band changes."""

    def __init__(
        self,
        registry: "DriverRegistry",
        state_store: "StateStore",
        event_bus: "EventBus",
        ws_manager: "WebSocketManager",
        *,
        poll_seconds: float = 7.0,
        stagger_seconds: float = 0.2,
    ) -> None:
        """Create the reconciler.

        Args:
            registry: Source of live device state (``get`` / driver
                ``get_state``).
            state_store: Holds the cached ``DeviceInfo.state`` to diff against.
            event_bus: Where drift is published as ``DEVICE_STATE_CHANGED``.
            ws_manager: Used to gate polling on having at least one connected
                client (``active_count``).
            poll_seconds: Seconds between reconciliation passes.
            stagger_seconds: Delay inserted between consecutive device reads
                so all devices aren't probed simultaneously.
        """

        self._registry = registry
        self._store = state_store
        self._bus = event_bus
        self._ws = ws_manager
        self._poll_seconds = poll_seconds
        self._stagger_seconds = stagger_seconds

        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Spawn the loop as a background task. No-op if already started."""

        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="reconciler-loop")

    async def stop(self) -> None:
        """Cancel the loop and await its exit."""

        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):  # pragma: no cover
            pass
        self._task = None

    # ------------------------------------------------------------------
    # Loop body
    # ------------------------------------------------------------------
    async def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    # Skip the whole pass when nobody's watching — no point
                    # correcting a cache no client is reading.
                    if self._ws.active_count > 0:
                        await self._tick()
                except Exception:
                    logger.exception("reconciler tick failed")

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self._poll_seconds
                    )
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass

    async def _tick(self) -> None:
        """One reconciliation pass over every registered device."""

        # Snapshot device IDs so a concurrent register/replace doesn't mutate
        # us mid-iteration. device_ids() already returns a fresh list.
        device_ids = self._registry.device_ids()

        for index, device_id in enumerate(device_ids):
            if self._stop_event.is_set():
                return
            # Stagger reads so we don't hit every bulb in the same instant.
            if index and self._stagger_seconds:
                await asyncio.sleep(self._stagger_seconds)
            try:
                await self._reconcile_device(device_id)
            except Exception:
                # One unreachable device must never stall the rest.
                logger.debug(
                    "reconciler: failed to reconcile %s", device_id,
                    exc_info=True,
                )

    async def _reconcile_device(self, device_id: str) -> None:
        """Read live state for *device_id* and publish if it drifted."""

        driver = self._registry.get(device_id)
        live_state = await driver.get_state()

        cached = await self._store.get_device(device_id)
        # If we have no cached row yet there's nothing meaningful to diff
        # against; the registration path seeds it, so just skip this round.
        if cached is None:
            return

        if cached.state == live_state:
            return  # No drift — stay silent.

        logger.info(
            "reconciler: drift detected on %s (cached power=%s -> live power=%s)"
            " — publishing correction",
            device_id,
            cached.state.power,
            live_state.power,
        )
        await self._bus.publish(
            Event(
                type=EventType.DEVICE_STATE_CHANGED,
                source="reconcile",
                device_id=device_id,
                data={"state": live_state.model_dump(mode="json")},
            )
        )
