"""Tests for the four core services.

Run with::

    uv run pytest tests/test_core.py -v

``asyncio_mode = "auto"`` (set in ``pyproject.toml``) means async test
functions are picked up without explicit decorators, but a few
``@pytest.mark.asyncio`` marks remain for clarity.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest

from core.events import EventBus, get_event_bus, reset_event_bus
from core.scenes import SceneEngine
from core.scheduler import Scheduler
from core.state import StateStore
from drivers.base import DeviceDriver
from drivers.registry import DriverRegistry
from schemas.device import (
    DeviceAction,
    DeviceCapability,
    DeviceInfo,
    DeviceState,
    DeviceType,
)
from schemas.events import Event, EventType
from schemas.scene import Scene, SceneAction
from schemas.schedule import Schedule


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


class FakeDriver(DeviceDriver):
    """In-memory driver used by scene/registry tests."""

    def __init__(
        self,
        device_id: str,
        *,
        fail_on: set[str] | None = None,
    ) -> None:
        self._info = DeviceInfo(
            id=device_id,
            name=device_id,
            device_type=DeviceType.SWITCH,
            driver_name="FakeDriver",
            capabilities=[DeviceCapability.TOGGLE],
            state=DeviceState(power=False),
        )
        self._fail_on = fail_on or set()
        self.calls: list[DeviceAction] = []

    async def get_info(self) -> DeviceInfo:
        return self._info

    async def get_state(self) -> DeviceState:
        return self._info.state

    async def execute(self, action: DeviceAction) -> DeviceState:
        self.calls.append(action)
        verb = action.action.value if hasattr(action.action, "value") else action.action
        if verb in self._fail_on:
            raise RuntimeError(f"forced failure on {verb}")
        if verb == "turn_on":
            self._info.state = DeviceState(power=True, attributes={})
        elif verb == "turn_off":
            self._info.state = DeviceState(power=False, attributes={})
        elif verb == "toggle":
            self._info.state = DeviceState(power=not self._info.state.power)
        return self._info.state

    async def get_capabilities(self) -> list[DeviceCapability]:
        return self._info.capabilities


@pytest.fixture
def event_bus() -> EventBus:
    """A fresh EventBus per test (no singleton bleed-through)."""

    return EventBus()


@pytest.fixture
async def state_store(tmp_path, event_bus):
    db_file = tmp_path / "state.db"
    store = StateStore(str(db_file), event_bus)
    await store.start()
    try:
        yield store
    finally:
        await store.close()


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


async def test_event_bus_publish_invokes_subscriber(event_bus):
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    event_bus.subscribe(EventType.SCENE_EXECUTED, handler)

    evt = Event(type=EventType.SCENE_EXECUTED, source="test", data={"hi": 1})
    await event_bus.publish(evt)

    assert len(received) == 1
    assert received[0].data == {"hi": 1}


async def test_event_bus_multiple_subscribers(event_bus):
    seen_a: list[Event] = []
    seen_b: list[Event] = []

    async def a(event: Event) -> None:
        seen_a.append(event)

    async def b(event: Event) -> None:
        seen_b.append(event)

    event_bus.subscribe(EventType.DEVICE_STATE_CHANGED, a)
    event_bus.subscribe(EventType.DEVICE_STATE_CHANGED, b)

    evt = Event(
        type=EventType.DEVICE_STATE_CHANGED,
        source="test",
        device_id="dev-1",
        data={"state": {"power": True, "attributes": {}}},
    )
    await event_bus.publish(evt)

    assert len(seen_a) == 1
    assert len(seen_b) == 1


async def test_event_bus_failure_isolation(event_bus):
    survivors: list[Event] = []

    async def boom(event: Event) -> None:
        raise RuntimeError("intentional")

    async def fine(event: Event) -> None:
        survivors.append(event)

    event_bus.subscribe(EventType.SCENE_EXECUTED, boom)
    event_bus.subscribe(EventType.SCENE_EXECUTED, fine)

    await event_bus.publish(
        Event(type=EventType.SCENE_EXECUTED, source="test", data={})
    )

    # The failing subscriber must not block the second subscriber.
    assert len(survivors) == 1


async def test_event_bus_unsubscribe(event_bus):
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    event_bus.subscribe(EventType.SCENE_EXECUTED, handler)
    event_bus.unsubscribe(EventType.SCENE_EXECUTED, handler)

    await event_bus.publish(
        Event(type=EventType.SCENE_EXECUTED, source="test", data={})
    )

    assert received == []


def test_event_bus_singleton_round_trip():
    reset_event_bus()
    a = get_event_bus()
    b = get_event_bus()
    assert a is b
    reset_event_bus()


# ---------------------------------------------------------------------------
# StateStore
# ---------------------------------------------------------------------------


async def test_state_store_device_round_trip(state_store):
    info = DeviceInfo(
        id="dev-1",
        name="Dev 1",
        device_type=DeviceType.SWITCH,
        driver_name="FakeDriver",
        capabilities=[DeviceCapability.TOGGLE],
        state=DeviceState(power=False),
    )
    await state_store.upsert_device(info)

    fetched = await state_store.get_device("dev-1")
    assert fetched is not None
    assert isinstance(fetched, DeviceInfo)
    assert fetched.id == "dev-1"
    assert fetched.state.power is False

    listed = await state_store.list_devices()
    assert len(listed) == 1
    assert listed[0].id == "dev-1"


async def test_state_store_scene_and_schedule_round_trip(state_store):
    scene = Scene(
        id="bedtime",
        name="Bedtime",
        description="All off",
        actions=[SceneAction(device_id="dev-1", action="turn_off")],
    )
    await state_store.upsert_scene(scene)
    fetched_scene = await state_store.get_scene("bedtime")
    assert fetched_scene is not None
    assert isinstance(fetched_scene, Scene)
    assert fetched_scene.actions[0].device_id == "dev-1"

    schedule = Schedule(
        id="bedtime-sched",
        name="Bedtime sched",
        scene_id="bedtime",
        time="23:00",
    )
    await state_store.upsert_schedule(schedule)
    fetched_sched = await state_store.get_schedule("bedtime-sched")
    assert fetched_sched is not None
    assert isinstance(fetched_sched, Schedule)
    assert fetched_sched.time == "23:00"

    await state_store.delete_scene("bedtime")
    assert await state_store.get_scene("bedtime") is None
    await state_store.delete_schedule("bedtime-sched")
    assert await state_store.get_schedule("bedtime-sched") is None


async def test_state_store_auto_persists_state_changed(state_store, event_bus):
    info = DeviceInfo(
        id="dev-1",
        name="Dev 1",
        device_type=DeviceType.SWITCH,
        driver_name="FakeDriver",
        capabilities=[DeviceCapability.TOGGLE],
        state=DeviceState(power=False),
    )
    await state_store.upsert_device(info)

    new_state = DeviceState(power=True, attributes={"brightness": 75})
    await event_bus.publish(
        Event(
            type=EventType.DEVICE_STATE_CHANGED,
            source="test",
            device_id="dev-1",
            data={"state": new_state.model_dump(mode="json")},
        )
    )

    persisted = await state_store.get_device("dev-1")
    assert persisted is not None
    assert persisted.state.power is True
    assert persisted.state.attributes == {"brightness": 75}


async def test_state_store_logs_every_event(state_store, event_bus):
    await event_bus.publish(
        Event(type=EventType.SCENE_EXECUTED, source="test", data={"scene_id": "s"})
    )
    await event_bus.publish(
        Event(
            type=EventType.SCHEDULE_TRIGGERED,
            source="test",
            data={"schedule_id": "sched", "scene_id": "s"},
        )
    )

    events = await state_store.list_events()
    types = [e.type for e in events]
    assert EventType.SCENE_EXECUTED in types
    assert EventType.SCHEDULE_TRIGGERED in types


# ---------------------------------------------------------------------------
# SceneEngine
# ---------------------------------------------------------------------------


async def _collect_events(bus: EventBus) -> tuple[list[Event], callable]:
    """Subscribe a sink for every EventType; return (events, unsubscribe)."""

    events: list[Event] = []

    async def sink(event: Event) -> None:
        events.append(event)

    for et in EventType:
        bus.subscribe(et, sink)

    def detach() -> None:
        for et in EventType:
            bus.unsubscribe(et, sink)

    return events, detach


async def test_scene_engine_runs_actions_in_order(event_bus):
    # Phase 3 reconciliation: the registry is the publisher of
    # DEVICE_STATE_CHANGED, so we wire it with the bus to keep the
    # "3 state-changed events fired" assertion meaningful.
    registry = DriverRegistry(event_bus=event_bus)
    a = FakeDriver("dev-a")
    b = FakeDriver("dev-b")
    c = FakeDriver("dev-c")
    registry.register("dev-a", a)
    registry.register("dev-b", b)
    registry.register("dev-c", c)

    engine = SceneEngine(registry, event_bus)
    events, detach = await _collect_events(event_bus)

    scene = Scene(
        id="test-scene",
        name="Test",
        actions=[
            SceneAction(device_id="dev-a", action="turn_on"),
            SceneAction(device_id="dev-b", action="turn_on", delay_ms=100),
            SceneAction(device_id="dev-c", action="turn_on"),
        ],
    )

    start = asyncio.get_event_loop().time()
    results = await engine.execute_scene(scene)
    elapsed = asyncio.get_event_loop().time() - start
    detach()

    assert [r["device_id"] for r in results] == ["dev-a", "dev-b", "dev-c"]
    assert all(r["success"] for r in results)
    # delay_ms=100 means at least ~0.1s total
    assert elapsed >= 0.1

    state_changed = [e for e in events if e.type == EventType.DEVICE_STATE_CHANGED]
    scene_done = [e for e in events if e.type == EventType.SCENE_EXECUTED]
    assert len(state_changed) == 3
    assert len(scene_done) == 1
    assert scene_done[0].data["scene_id"] == "test-scene"


async def test_scene_engine_partial_failure(event_bus):
    # Wire the registry with the bus so DEVICE_STATE_CHANGED publishes for
    # the two successful dispatches (registry-level publish, Phase 3).
    registry = DriverRegistry(event_bus=event_bus)
    registry.register("dev-a", FakeDriver("dev-a"))
    registry.register("dev-b", FakeDriver("dev-b", fail_on={"turn_on"}))
    registry.register("dev-c", FakeDriver("dev-c"))

    engine = SceneEngine(registry, event_bus)
    events, detach = await _collect_events(event_bus)

    scene = Scene(
        id="partial",
        name="Partial",
        actions=[
            SceneAction(device_id="dev-a", action="turn_on"),
            SceneAction(device_id="dev-b", action="turn_on"),
            SceneAction(device_id="dev-c", action="turn_on"),
        ],
    )
    results = await engine.execute_scene(scene)
    detach()

    assert results[0]["success"] is True
    assert results[1]["success"] is False
    assert results[1]["error"] is not None
    assert results[2]["success"] is True

    # Two successful state-change events, one device-error event, one scene-executed.
    state_changed = [e for e in events if e.type == EventType.DEVICE_STATE_CHANGED]
    errors = [e for e in events if e.type == EventType.DEVICE_ERROR]
    assert len(state_changed) == 2
    assert len(errors) == 1
    assert errors[0].device_id == "dev-b"


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


async def test_scheduler_fires_at_target_time(state_store, event_bus):
    registry = DriverRegistry()
    registry.register("dev-a", FakeDriver("dev-a"))

    scene = Scene(
        id="sched-scene",
        name="Sched scene",
        actions=[SceneAction(device_id="dev-a", action="turn_on")],
    )
    await state_store.upsert_scene(scene)

    tick = 2
    target = (datetime.now() + timedelta(seconds=tick + 5)).strftime("%H:%M")

    schedule = Schedule(
        id="sched-1",
        name="Sched 1",
        scene_id="sched-scene",
        time=target,
        enabled=True,
    )
    await state_store.upsert_schedule(schedule)

    triggered: list[Event] = []

    async def sink(event: Event) -> None:
        triggered.append(event)

    event_bus.subscribe(EventType.SCHEDULE_TRIGGERED, sink)

    engine = SceneEngine(registry, event_bus)
    sched = Scheduler(state_store, engine, event_bus, tick_seconds=tick)
    await sched.start()
    try:
        # Wait long enough for at least one tick to land in the target minute.
        # Worst case: target_seconds_away (up to tick+5) + one tick.
        await asyncio.sleep(tick * 4 + 6)
    finally:
        await sched.stop()

    event_bus.unsubscribe(EventType.SCHEDULE_TRIGGERED, sink)

    assert len(triggered) >= 1, (
        f"no SCHEDULE_TRIGGERED received; target={target}"
    )
    assert triggered[0].data == {
        "schedule_id": "sched-1",
        "scene_id": "sched-scene",
    }


async def test_scheduler_skips_disabled_schedules(state_store, event_bus):
    registry = DriverRegistry()
    registry.register("dev-a", FakeDriver("dev-a"))

    scene = Scene(
        id="sched-scene",
        name="Sched scene",
        actions=[SceneAction(device_id="dev-a", action="turn_on")],
    )
    await state_store.upsert_scene(scene)

    target = datetime.now().strftime("%H:%M")
    await state_store.upsert_schedule(
        Schedule(
            id="off",
            name="off",
            scene_id="sched-scene",
            time=target,
            enabled=False,
        )
    )

    triggered: list[Event] = []

    async def sink(event: Event) -> None:
        triggered.append(event)

    event_bus.subscribe(EventType.SCHEDULE_TRIGGERED, sink)

    engine = SceneEngine(registry, event_bus)
    sched = Scheduler(state_store, engine, event_bus, tick_seconds=1)
    await sched.start()
    try:
        await asyncio.sleep(2.5)
    finally:
        await sched.stop()

    event_bus.unsubscribe(EventType.SCHEDULE_TRIGGERED, sink)

    assert triggered == []


async def test_scheduler_no_duplicate_fires(state_store, event_bus):
    """Two ticks within the same minute should fire the schedule once."""

    registry = DriverRegistry()
    registry.register("dev-a", FakeDriver("dev-a"))

    scene = Scene(
        id="sched-scene",
        name="Sched scene",
        actions=[SceneAction(device_id="dev-a", action="turn_on")],
    )
    await state_store.upsert_scene(scene)

    target = datetime.now().strftime("%H:%M")
    await state_store.upsert_schedule(
        Schedule(id="dup", name="Dup", scene_id="sched-scene", time=target)
    )

    triggered: list[Event] = []

    async def sink(event: Event) -> None:
        triggered.append(event)

    event_bus.subscribe(EventType.SCHEDULE_TRIGGERED, sink)

    engine = SceneEngine(registry, event_bus)
    sched = Scheduler(state_store, engine, event_bus, tick_seconds=1)
    await sched.start()
    try:
        # Multiple ticks within the same target minute.
        await asyncio.sleep(3.5)
    finally:
        await sched.stop()

    event_bus.unsubscribe(EventType.SCHEDULE_TRIGGERED, sink)

    assert len(triggered) == 1, f"expected 1 fire, got {len(triggered)}"
