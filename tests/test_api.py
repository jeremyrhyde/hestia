"""FastAPI route + WebSocket tests.

Builds a hermetic app via :func:`core.api.create_app` with mock drivers
so the suite never touches real hardware. Uses
:class:`fastapi.testclient.TestClient` (which spins up an internal
event loop) for both REST and WebSocket coverage.

Run with::

    uv run pytest tests/test_api.py -v
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.api import create_app
from core.events import EventBus
from core.scenes import SceneEngine
from core.scheduler import Scheduler
from core.state import StateStore
from core.websocket import WebSocketManager
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


# ---------------------------------------------------------------------------
# Mock driver
# ---------------------------------------------------------------------------


class MockDriver(DeviceDriver):
    """In-memory driver used by the API tests."""

    def __init__(self, device_id: str, name: str | None = None) -> None:
        self._info = DeviceInfo(
            id=device_id,
            name=name or device_id,
            device_type=DeviceType.SWITCH,
            driver_name="MockDriver",
            capabilities=[DeviceCapability.TOGGLE],
            state=DeviceState(power=False),
        )
        self.calls: list[DeviceAction] = []
        self.closed = False

    async def get_info(self) -> DeviceInfo:
        return self._info

    async def get_state(self) -> DeviceState:
        return self._info.state

    async def execute(self, action: DeviceAction) -> DeviceState:
        self.calls.append(action)
        verb = (
            action.action.value
            if hasattr(action.action, "value")
            else action.action
        )
        if verb == "turn_on":
            self._info.state = DeviceState(power=True)
        elif verb == "turn_off":
            self._info.state = DeviceState(power=False)
        elif verb == "toggle":
            self._info.state = DeviceState(power=not self._info.state.power)
        else:
            raise ValueError(f"unsupported action: {verb!r}")
        return self._info.state

    async def get_capabilities(self) -> list[DeviceCapability]:
        return self._info.capabilities

    async def close(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_bundle(tmp_path) -> Iterator[dict[str, Any]]:
    """Build a fully-wired app with two mock drivers.

    Drives :class:`StateStore`, :class:`SceneEngine`, :class:`Scheduler`,
    and :class:`WebSocketManager` end-to-end against a per-test SQLite
    file. The ``TestClient`` context manager runs FastAPI's startup /
    shutdown handlers, so the scheduler loop is started and stopped
    automatically.
    """

    db_path = tmp_path / "api.db"

    bus = EventBus()
    store = StateStore(str(db_path), bus)

    registry = DriverRegistry(event_bus=bus)
    dev_a = MockDriver("dev-a", "Device A")
    dev_b = MockDriver("dev-b", "Device B")
    registry.register("dev-a", dev_a)
    registry.register("dev-b", dev_b)

    engine = SceneEngine(registry, bus)
    scheduler = Scheduler(store, engine, bus, tick_seconds=60)

    ws_manager = WebSocketManager()
    ws_manager.subscribe_to_bus(bus)

    app = create_app(
        registry=registry,
        state_store=store,
        scene_engine=engine,
        scheduler=scheduler,
        ws_manager=ws_manager,
        settings=None,
        mount_static=False,
    )

    # We have to run StateStore.start() and seed device rows before any
    # request fires. Use the test event loop policy: open the connection
    # before constructing TestClient.
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(store.start())
        info_a = loop.run_until_complete(dev_a.get_info())
        info_b = loop.run_until_complete(dev_b.get_info())
        loop.run_until_complete(store.upsert_device(info_a))
        loop.run_until_complete(store.upsert_device(info_b))

        yield {
            "app": app,
            "bus": bus,
            "store": store,
            "registry": registry,
            "engine": engine,
            "scheduler": scheduler,
            "ws_manager": ws_manager,
            "dev_a": dev_a,
            "dev_b": dev_b,
            "loop": loop,
        }
    finally:
        loop.run_until_complete(scheduler.stop())
        loop.run_until_complete(registry.close_all())
        loop.run_until_complete(store.close())
        loop.close()


@pytest.fixture
def client(app_bundle) -> Iterator[TestClient]:
    with TestClient(app_bundle["app"]) as c:
        yield c


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------


def test_list_devices_returns_registered(client):
    response = client.get("/devices/")
    assert response.status_code == 200
    body = response.json()
    ids = sorted(d["id"] for d in body)
    assert ids == ["dev-a", "dev-b"]


def test_get_device_known(client):
    response = client.get("/devices/dev-a")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "dev-a"
    assert body["name"] == "Device A"


def test_get_device_unknown_returns_404(client):
    response = client.get("/devices/does-not-exist")
    assert response.status_code == 404


def test_post_device_action_returns_new_state_and_publishes_event(
    client, app_bundle
):
    """The registry-level publish must fire on direct API calls."""

    bus = app_bundle["bus"]
    received: list[Event] = []

    async def sink(event: Event) -> None:
        received.append(event)

    bus.subscribe(EventType.DEVICE_STATE_CHANGED, sink)

    response = client.post("/devices/dev-a/action", json={"action": "turn_on"})
    assert response.status_code == 200
    body = response.json()
    assert body["power"] is True

    # Registry publishes DEVICE_STATE_CHANGED on success — verify it arrived.
    matching = [
        e for e in received
        if e.type == EventType.DEVICE_STATE_CHANGED and e.device_id == "dev-a"
    ]
    assert len(matching) == 1
    assert matching[0].source == "api"
    assert matching[0].data["state"]["power"] is True


def test_post_device_action_unknown_device_404(client):
    response = client.post(
        "/devices/nope/action", json={"action": "turn_on"}
    )
    assert response.status_code == 404


def test_post_device_action_malformed_body_422(client):
    # Missing required ``action`` key.
    response = client.post("/devices/dev-a/action", json={"foo": "bar"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------


def _scene_payload(scene_id: str = "s1") -> dict[str, Any]:
    return {
        "id": scene_id,
        "name": f"Scene {scene_id}",
        "description": "test",
        "actions": [
            {"device_id": "dev-a", "action": "turn_on"},
            {"device_id": "dev-b", "action": "turn_on"},
        ],
    }


def test_scene_crud_round_trip(client):
    # initial list empty
    assert client.get("/scenes/").json() == []

    # create
    payload = _scene_payload("s1")
    r = client.post("/scenes/", json=payload)
    assert r.status_code == 200
    assert r.json()["id"] == "s1"

    # list
    listing = client.get("/scenes/").json()
    assert [s["id"] for s in listing] == ["s1"]

    # get
    fetched = client.get("/scenes/s1").json()
    assert fetched["name"] == "Scene s1"

    # update via PUT
    payload["description"] = "updated"
    r = client.put("/scenes/s1", json=payload)
    assert r.status_code == 200
    assert r.json()["description"] == "updated"

    # PUT with mismatched id is 400
    payload_bad = dict(payload)
    payload_bad["id"] = "different"
    r = client.put("/scenes/s1", json=payload_bad)
    assert r.status_code == 400

    # delete
    r = client.delete("/scenes/s1")
    assert r.status_code == 204
    assert client.get("/scenes/s1").status_code == 404


def test_scene_execute_runs_actions(client, app_bundle):
    payload = _scene_payload("exec-s1")
    client.post("/scenes/", json=payload)

    r = client.post("/scenes/exec-s1/execute")
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 2
    assert all(item["success"] is True for item in results)
    assert {item["device_id"] for item in results} == {"dev-a", "dev-b"}

    # Both mock drivers should now report power=True.
    assert app_bundle["dev_a"]._info.state.power is True
    assert app_bundle["dev_b"]._info.state.power is True


def test_scene_execute_unknown_404(client):
    r = client.post("/scenes/missing/execute")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------


def _schedule_payload(schedule_id: str = "sched-1") -> dict[str, Any]:
    return {
        "id": schedule_id,
        "name": f"Sched {schedule_id}",
        "scene_id": "s1",
        "time": "08:00",
        "days": ["mon", "tue"],
        "enabled": True,
    }


def test_schedule_crud_and_reload(client):
    # create
    payload = _schedule_payload("sched-1")
    r = client.post("/schedules/", json=payload)
    assert r.status_code == 200
    assert r.json()["enabled"] is True

    # list
    rows = client.get("/schedules/").json()
    assert [s["id"] for s in rows] == ["sched-1"]

    # PATCH toggle enabled
    r = client.patch("/schedules/sched-1", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    # PATCH unknown -> 404
    r = client.patch("/schedules/missing", json={"enabled": False})
    assert r.status_code == 404

    # delete
    r = client.delete("/schedules/sched-1")
    assert r.status_code == 204
    assert client.get("/schedules/").json() == []


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


def test_websocket_receives_device_state_changed(client):
    """Connect WS, trigger a REST action, observe the broadcast."""

    with client.websocket_connect("/ws") as ws:
        # Trigger a state change via REST.
        r = client.post(
            "/devices/dev-a/action", json={"action": "turn_on"}
        )
        assert r.status_code == 200

        # The registry publishes DEVICE_STATE_CHANGED -> WebSocketManager
        # broadcasts -> our client receives.
        raw = ws.receive_text()
        evt = json.loads(raw)
        assert evt["type"] == "device_state_changed"
        assert evt["device_id"] == "dev-a"
        assert evt["data"]["state"]["power"] is True


def test_websocket_receives_scene_executed(client):
    payload = _scene_payload("ws-scene")
    client.post("/scenes/", json=payload)

    with client.websocket_connect("/ws") as ws:
        r = client.post("/scenes/ws-scene/execute")
        assert r.status_code == 200

        # Drain: expect two DEVICE_STATE_CHANGED + one SCENE_EXECUTED.
        types_seen: list[str] = []
        for _ in range(3):
            raw = ws.receive_text()
            evt = json.loads(raw)
            types_seen.append(evt["type"])

        assert types_seen.count("device_state_changed") == 2
        assert types_seen.count("scene_executed") == 1
