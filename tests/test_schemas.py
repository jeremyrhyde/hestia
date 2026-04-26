"""Phase 1 foundation tests.

Verifies that:

- every schema model can be instantiated, serialized to JSON, and
  round-tripped back to an equivalent instance;
- :class:`drivers.base.DeviceDriver` cannot be instantiated directly (abstract);
- :class:`drivers.registry.DriverRegistry` can register, retrieve, list, and
  dispatch actions to a mock driver.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from drivers.base import DeviceDriver
from drivers.registry import DriverRegistry
from schemas import (
    DeviceAction,
    DeviceCapability,
    DeviceInfo,
    DeviceState,
    DeviceType,
    Event,
    EventType,
    Scene,
    SceneAction,
    Schedule,
    StandardAction,
)


def _roundtrip(model: Any) -> None:
    """Helper: dump to JSON, parse back, assert equality."""

    cls = type(model)
    raw = model.model_dump_json()
    restored = cls.model_validate_json(raw)
    assert restored == model


def test_device_state_roundtrip() -> None:
    s = DeviceState(power=True, attributes={"volume": 80})
    _roundtrip(s)
    assert s.power is True
    assert s.attributes == {"volume": 80}


def test_device_state_default_attributes() -> None:
    s = DeviceState(power=False)
    assert s.attributes == {}


def test_device_action_roundtrip() -> None:
    a = DeviceAction(action="set_brightness", params={"level": 50})
    _roundtrip(a)
    a2 = DeviceAction(action="turn_on")
    _roundtrip(a2)
    assert a2.params is None


def test_device_action_known_verb_coerces_to_enum() -> None:
    """Known verb strings parse into ``StandardAction`` enum members."""

    a = DeviceAction(action="turn_on")
    assert a.action == StandardAction.TURN_ON
    assert isinstance(a.action, StandardAction)


def test_device_action_unknown_verb_passes_through_as_string() -> None:
    """Driver-specific verbs flow through as plain ``str``."""

    a = DeviceAction(action="shuffle")
    assert a.action == "shuffle"
    assert isinstance(a.action, str)
    assert not isinstance(a.action, StandardAction)


def test_device_action_known_verb_json_roundtrip() -> None:
    """JSON wire format is the lowercase string; round-trip preserves enum-ness."""

    a = DeviceAction(action="turn_on")
    raw = a.model_dump_json()
    assert raw == '{"action":"turn_on","params":null}'

    restored = DeviceAction.model_validate_json(raw)
    assert restored == a
    assert restored.action == StandardAction.TURN_ON
    assert isinstance(restored.action, StandardAction)


def test_device_action_unknown_verb_json_roundtrip() -> None:
    """Unknown verb survives a JSON round-trip as a plain string."""

    b = DeviceAction(action="shuffle")
    raw = b.model_dump_json()
    assert raw == '{"action":"shuffle","params":null}'

    restored = DeviceAction.model_validate_json(raw)
    assert restored == b
    assert restored.action == "shuffle"
    assert not isinstance(restored.action, StandardAction)


def test_device_action_accepts_enum_directly() -> None:
    """Passing the ``StandardAction`` enum value directly is supported."""

    c = DeviceAction(action=StandardAction.SET_VOLUME, params={"level": 70})
    assert c.action is StandardAction.SET_VOLUME
    assert c.params == {"level": 70}
    _roundtrip(c)
    # Wire format remains the lowercase string.
    assert c.model_dump_json() == (
        '{"action":"set_volume","params":{"level":70}}'
    )


def test_device_info_roundtrip() -> None:
    info = DeviceInfo(
        id="kasa-living-room",
        name="Living room lights",
        device_type=DeviceType.SWITCH,
        driver_name="KasaDriver",
        capabilities=[DeviceCapability.TOGGLE],
        state=DeviceState(power=False),
    )
    _roundtrip(info)
    assert info.device_type is DeviceType.SWITCH
    assert info.capabilities == [DeviceCapability.TOGGLE]


def test_scene_roundtrip() -> None:
    scene = Scene(
        id="bedtime",
        name="Bedtime",
        description="All off, fan on",
        actions=[
            SceneAction(device_id="kasa-living-room", action="turn_off"),
            SceneAction(
                device_id="relay-fan", action="turn_on", delay_ms=2000
            ),
        ],
    )
    _roundtrip(scene)
    assert len(scene.actions) == 2
    assert scene.actions[1].delay_ms == 2000


def test_schedule_roundtrip() -> None:
    s = Schedule(
        id="bedtime",
        name="Bedtime",
        scene_id="bedtime",
        time="23:00",
    )
    _roundtrip(s)
    assert s.enabled is True
    assert s.days is None

    s2 = Schedule(
        id="weekday-morning",
        name="Weekday morning",
        scene_id="morning",
        time="07:00",
        days=["mon", "tue", "wed", "thu", "fri"],
        enabled=False,
    )
    _roundtrip(s2)
    assert s2.enabled is False


def test_event_roundtrip() -> None:
    e = Event(
        type=EventType.DEVICE_STATE_CHANGED,
        device_id="kasa-living-room",
        data={"state": {"power": True, "attributes": {}}},
        source="api",
    )
    _roundtrip(e)
    assert e.type is EventType.DEVICE_STATE_CHANGED
    assert isinstance(e.timestamp, datetime)


def test_device_driver_is_abstract() -> None:
    with pytest.raises(TypeError):
        DeviceDriver()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Mock driver + registry tests


class MockDriver(DeviceDriver):
    """Minimal in-memory driver for exercising the registry."""

    def __init__(self, device_id: str, name: str) -> None:
        self._id = device_id
        self._name = name
        self._state = DeviceState(power=False, attributes={})

    async def get_info(self) -> DeviceInfo:
        return DeviceInfo(
            id=self._id,
            name=self._name,
            device_type=DeviceType.SWITCH,
            driver_name="MockDriver",
            capabilities=[DeviceCapability.TOGGLE],
            state=self._state,
        )

    async def get_state(self) -> DeviceState:
        return self._state

    async def execute(self, action: DeviceAction) -> DeviceState:
        if action.action == "turn_on":
            self._state = DeviceState(power=True, attributes={})
        elif action.action == "turn_off":
            self._state = DeviceState(power=False, attributes={})
        elif action.action == "toggle":
            self._state = DeviceState(power=not self._state.power, attributes={})
        else:
            raise ValueError(f"unsupported action: {action.action}")
        return self._state

    async def get_capabilities(self) -> list[DeviceCapability]:
        return [DeviceCapability.TOGGLE]


@pytest.mark.asyncio
async def test_registry_register_and_get() -> None:
    reg = DriverRegistry()
    drv = MockDriver("mock-1", "Mock 1")
    reg.register("mock-1", drv)
    assert reg.get("mock-1") is drv


@pytest.mark.asyncio
async def test_registry_get_missing_raises_keyerror() -> None:
    reg = DriverRegistry()
    with pytest.raises(KeyError):
        reg.get("does-not-exist")


@pytest.mark.asyncio
async def test_registry_list_devices() -> None:
    reg = DriverRegistry()
    reg.register("mock-1", MockDriver("mock-1", "Mock 1"))
    reg.register("mock-2", MockDriver("mock-2", "Mock 2"))

    infos = await reg.list_devices()
    ids = {i.id for i in infos}
    assert ids == {"mock-1", "mock-2"}
    assert all(isinstance(i, DeviceInfo) for i in infos)


@pytest.mark.asyncio
async def test_registry_execute_action() -> None:
    reg = DriverRegistry()
    drv = MockDriver("mock-1", "Mock 1")
    reg.register("mock-1", drv)

    state = await reg.execute_action("mock-1", DeviceAction(action="turn_on"))
    assert state.power is True

    state = await reg.execute_action("mock-1", DeviceAction(action="toggle"))
    assert state.power is False


@pytest.mark.asyncio
async def test_registry_execute_action_missing_device() -> None:
    reg = DriverRegistry()
    with pytest.raises(KeyError):
        await reg.execute_action("nope", DeviceAction(action="turn_on"))
