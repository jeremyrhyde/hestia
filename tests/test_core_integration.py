"""End-to-end micro-integration test for ``core/``.

Wires together :class:`EventBus`, :class:`StateStore`, a fake
:class:`DriverRegistry`, and :class:`SceneEngine`. Persists a scene,
executes it, and verifies that:

1. Each device's state was persisted to SQLite via the
   ``DEVICE_STATE_CHANGED`` auto-persist subscriber.
2. The ``event_log`` table contains both ``DEVICE_STATE_CHANGED`` rows
   and a ``SCENE_EXECUTED`` row.

Run as a script::

    uv run python tests/test_core_integration.py

Exits 0 with ``PASS`` printed on success, non-zero on failure.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# Ensure the repo root is on sys.path when invoked as a plain script.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.events import EventBus  # noqa: E402
from core.scenes import SceneEngine  # noqa: E402
from core.state import StateStore  # noqa: E402
from drivers.base import DeviceDriver  # noqa: E402
from drivers.registry import DriverRegistry  # noqa: E402
from schemas.device import (  # noqa: E402
    DeviceAction,
    DeviceCapability,
    DeviceInfo,
    DeviceState,
    DeviceType,
)
from schemas.events import EventType  # noqa: E402
from schemas.scene import Scene, SceneAction  # noqa: E402


class MockDriver(DeviceDriver):
    """Minimal in-memory driver."""

    def __init__(self, device_id: str) -> None:
        self._info = DeviceInfo(
            id=device_id,
            name=device_id,
            device_type=DeviceType.SWITCH,
            driver_name="MockDriver",
            capabilities=[DeviceCapability.TOGGLE],
            state=DeviceState(power=False),
        )

    async def get_info(self) -> DeviceInfo:
        return self._info

    async def get_state(self) -> DeviceState:
        return self._info.state

    async def execute(self, action: DeviceAction) -> DeviceState:
        verb = (
            action.action.value if hasattr(action.action, "value") else action.action
        )
        if verb == "turn_on":
            self._info.state = DeviceState(power=True)
        elif verb == "turn_off":
            self._info.state = DeviceState(power=False)
        elif verb == "toggle":
            self._info.state = DeviceState(power=not self._info.state.power)
        return self._info.state

    async def get_capabilities(self) -> list[DeviceCapability]:
        return self._info.capabilities


async def run_integration() -> None:
    tmp_dir = tempfile.mkdtemp(prefix="hestia-integration-")
    db_path = os.path.join(tmp_dir, "test-integration.db")

    bus = EventBus()
    store = StateStore(db_path, bus)
    await store.start()

    try:
        # Build the registry with two mock drivers. Wire the bus so the
        # registry publishes DEVICE_STATE_CHANGED on every successful
        # execute_action (Phase 3 reconciliation).
        registry = DriverRegistry(event_bus=bus)
        dev_a = MockDriver("dev-a")
        dev_b = MockDriver("dev-b")
        registry.register("dev-a", dev_a)
        registry.register("dev-b", dev_b)

        # Pre-register devices in the state store so the auto-persist
        # subscriber has something to update.
        await store.upsert_device(await dev_a.get_info())
        await store.upsert_device(await dev_b.get_info())

        # Wire the scene engine.
        engine = SceneEngine(registry, bus)

        # Persist the scene definition.
        scene = Scene(
            id="integration-scene",
            name="Integration scene",
            actions=[
                SceneAction(device_id="dev-a", action="turn_on"),
                SceneAction(device_id="dev-b", action="turn_on"),
            ],
        )
        await store.upsert_scene(scene)
        # Round-trip the scene from store to verify persistence.
        loaded = await store.get_scene("integration-scene")
        assert loaded is not None and len(loaded.actions) == 2

        # Execute the scene.
        results = await engine.execute_scene(loaded)
        assert all(r["success"] for r in results), f"results={results}"

        # Give the bus a moment to flush state-store subscribers (they're
        # already awaited inside publish, but we double-check).
        await asyncio.sleep(0)

        # Verify device states were persisted via the auto-persist hook.
        persisted_a = await store.get_device("dev-a")
        persisted_b = await store.get_device("dev-b")
        assert persisted_a is not None and persisted_a.state.power is True, (
            f"dev-a not persisted as on: {persisted_a}"
        )
        assert persisted_b is not None and persisted_b.state.power is True, (
            f"dev-b not persisted as on: {persisted_b}"
        )

        # Verify the event log captured the right rows.
        events = await store.list_events()
        types = [e.type for e in events]
        assert types.count(EventType.DEVICE_STATE_CHANGED) >= 2, (
            f"expected >= 2 DEVICE_STATE_CHANGED rows, got {types}"
        )
        assert EventType.SCENE_EXECUTED in types, (
            f"missing SCENE_EXECUTED in {types}"
        )

        print("PASS")
    finally:
        await store.close()
        try:
            os.remove(db_path)
        except OSError:
            pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass


def test_core_integration() -> None:
    """Pytest entry point so ``pytest tests/`` also runs this scenario."""

    asyncio.run(run_integration())


if __name__ == "__main__":
    try:
        asyncio.run(run_integration())
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # pragma: no cover
        print(f"FAIL: {exc!r}", file=sys.stderr)
        sys.exit(2)
