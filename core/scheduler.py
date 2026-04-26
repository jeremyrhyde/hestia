"""In-process schedule runner.

The :class:`Scheduler` ticks on an async loop, reads enabled
:class:`schemas.schedule.Schedule` rows from the
:class:`core.state.StateStore`, and fires the matching scene whenever a
schedule's ``time`` (and optional ``days`` filter) matches the current
local time.

Why an internal service and not a cron job? Schedules are first-class
data exposed through the API and shown in the touchscreen UI. Putting
them inside the core process means the same SQLite row a user toggles
in the UI is the row the scheduler reads on its next tick — no
separate sync layer.

Duplicate-fire prevention
-------------------------

The loop ticks every ``tick_seconds`` (default 30s), so a schedule whose
``HH:MM`` matches the current minute could be hit twice within the same
day. We track ``set[(schedule_id, date)]`` of "fired today" entries and
clear it at the day boundary.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import TYPE_CHECKING

from core.events import EventBus
from schemas.events import Event, EventType
from schemas.schedule import Schedule

if TYPE_CHECKING:
    from core.scenes import SceneEngine
    from core.state import StateStore

logger = logging.getLogger(__name__)


# Match the lowercase three-letter codes documented in
# ``schemas/schedule.py``: ``mon``, ``tue``, ``wed``, ``thu``, ``fri``,
# ``sat``, ``sun``.
_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _weekday_code(when: datetime) -> str:
    return _WEEKDAYS[when.weekday()]


class Scheduler:
    """Async loop that fires scheduled scenes."""

    def __init__(
        self,
        state_store: "StateStore",
        scene_engine: "SceneEngine",
        event_bus: EventBus,
        tick_seconds: int = 30,
    ) -> None:
        self._store = state_store
        self._engine = scene_engine
        self._bus = event_bus
        self._tick_seconds = tick_seconds

        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

        # Cached enabled schedules; refreshed by ``reload`` and on each tick.
        self._schedules: list[Schedule] = []
        # ``(schedule_id, date)`` entries that have already fired.
        self._fired: set[tuple[str, date]] = set()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Spawn the loop as a background task.

        No-op if already started.
        """

        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        await self.reload()
        self._task = asyncio.create_task(self._run(), name="scheduler-loop")

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

    async def reload(self) -> None:
        """Re-read schedules from the state store.

        Called by the API after schedule CRUD operations. Disabled
        schedules are filtered out here so the tick loop does no extra
        work.
        """

        all_schedules = await self._store.list_schedules()
        self._schedules = [s for s in all_schedules if s.enabled]

    # ------------------------------------------------------------------
    # Loop body
    # ------------------------------------------------------------------
    async def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    await self._tick()
                except Exception:
                    logger.exception("scheduler tick failed")

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self._tick_seconds
                    )
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass

    async def _tick(self) -> None:
        now = datetime.now()
        today = now.date()
        # Drop "fired" entries from previous days so today's runs aren't blocked.
        self._fired = {entry for entry in self._fired if entry[1] == today}

        # Snapshot the schedule list to allow ``reload`` calls during iteration.
        for schedule in list(self._schedules):
            if not self._matches(schedule, now):
                continue
            key = (schedule.id, today)
            if key in self._fired:
                continue
            self._fired.add(key)
            await self._fire(schedule)

    @staticmethod
    def _matches(schedule: Schedule, now: datetime) -> bool:
        # Time match is HH:MM equality regardless of seconds — a 30s tick
        # may fire a schedule up to ~30s after its target minute, which the
        # spec accepts.
        if schedule.time != now.strftime("%H:%M"):
            return False
        if schedule.days is not None:
            if _weekday_code(now) not in {d.lower() for d in schedule.days}:
                return False
        return True

    async def _fire(self, schedule: Schedule) -> None:
        source = f"scheduler:{schedule.id}"
        await self._bus.publish(
            Event(
                type=EventType.SCHEDULE_TRIGGERED,
                source=source,
                data={
                    "schedule_id": schedule.id,
                    "scene_id": schedule.scene_id,
                },
            )
        )

        scene = await self._store.get_scene(schedule.scene_id)
        if scene is None:
            logger.error(
                "schedule %s references missing scene %s",
                schedule.id,
                schedule.scene_id,
            )
            return

        try:
            await self._engine.execute_scene(scene)
        except Exception:
            logger.exception(
                "scene execution from schedule %s failed", schedule.id
            )
