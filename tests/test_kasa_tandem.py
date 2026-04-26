"""Pytest coverage for KasaDriver's tandem (multi-host) mode.

These tests use AsyncMock-based fake Kasa devices so they run on any
machine with no hardware. They verify:

- A list-of-hosts ``host=`` argument constructs cleanly.
- Each action fans out across every member device.
- ``power`` aggregates as any-on (touch responsiveness).
- Brightness aggregates as the average of currently-on members.
- A per-host failure during an action is logged but doesn't abort the
  fanout — surviving members still get the command.
- Construction-time connection failures raise (so /health surfaces them).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from drivers.kasa_driver import KasaDriver, _normalize_hosts
from schemas.device import DeviceAction


# -- helpers ---------------------------------------------------------------


def _fake_kasa_device(*, is_on: bool = False, brightness: int | None = None) -> AsyncMock:
    """Build a stand-in for a python-kasa Device handle."""

    d = AsyncMock()
    d.is_on = is_on
    if brightness is not None:
        d.brightness = brightness
    # No `modules` attribute → driver falls back to `device.set_brightness`.
    if hasattr(d, "modules"):
        delattr(d, "modules")
    d.update = AsyncMock()
    d.turn_on = AsyncMock(side_effect=lambda: setattr(d, "is_on", True))
    d.turn_off = AsyncMock(side_effect=lambda: setattr(d, "is_on", False))
    d.set_brightness = AsyncMock(
        side_effect=lambda lvl: (setattr(d, "brightness", lvl), setattr(d, "is_on", lvl > 0))
    )
    return d


# -- _normalize_hosts ------------------------------------------------------


def test_normalize_hosts_str() -> None:
    assert _normalize_hosts("192.168.1.6") == ["192.168.1.6"]


def test_normalize_hosts_list() -> None:
    assert _normalize_hosts(["192.168.1.6", "192.168.1.7"]) == [
        "192.168.1.6",
        "192.168.1.7",
    ]


def test_normalize_hosts_empty_list_raises() -> None:
    with pytest.raises(ValueError):
        _normalize_hosts([])


def test_normalize_hosts_bad_type_raises() -> None:
    with pytest.raises(ValueError):
        _normalize_hosts(42)  # type: ignore[arg-type]


# -- construction ----------------------------------------------------------


def test_construct_with_list_host() -> None:
    drv = KasaDriver(
        device_id="fixture",
        name="Fixture",
        host=["192.168.1.6", "192.168.1.7"],
        kind="bulb",
    )
    assert drv._hosts == ["192.168.1.6", "192.168.1.7"]
    assert drv._host == ["192.168.1.6", "192.168.1.7"]


# -- fanout: every member receives the command ----------------------------


@pytest.mark.asyncio
async def test_turn_on_fans_out() -> None:
    d1 = _fake_kasa_device()
    d2 = _fake_kasa_device()
    drv = KasaDriver(
        device_id="fixture", name="Fixture",
        host=["a", "b"], kind="plug",
    )
    drv._devices = [d1, d2]

    await drv.execute(DeviceAction(action="turn_on"))

    d1.turn_on.assert_awaited_once()
    d2.turn_on.assert_awaited_once()


@pytest.mark.asyncio
async def test_turn_off_fans_out() -> None:
    d1 = _fake_kasa_device(is_on=True)
    d2 = _fake_kasa_device(is_on=True)
    drv = KasaDriver(
        device_id="fixture", name="Fixture",
        host=["a", "b"], kind="plug",
    )
    drv._devices = [d1, d2]

    await drv.execute(DeviceAction(action="turn_off"))

    d1.turn_off.assert_awaited_once()
    d2.turn_off.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_brightness_fans_out() -> None:
    d1 = _fake_kasa_device(is_on=True, brightness=50)
    d2 = _fake_kasa_device(is_on=True, brightness=50)
    drv = KasaDriver(
        device_id="fixture", name="Fixture",
        host=["a", "b"], kind="bulb",
    )
    drv._devices = [d1, d2]

    await drv.execute(
        DeviceAction(action="set_brightness", params={"level": 80})
    )

    d1.set_brightness.assert_awaited_once_with(80)
    d2.set_brightness.assert_awaited_once_with(80)


# -- aggregation -----------------------------------------------------------


@pytest.mark.asyncio
async def test_power_any_on() -> None:
    """If any member is on, the group reports power=True."""

    d1 = _fake_kasa_device(is_on=True)
    d2 = _fake_kasa_device(is_on=False)
    drv = KasaDriver(
        device_id="fixture", name="Fixture",
        host=["a", "b"], kind="plug",
    )
    drv._devices = [d1, d2]

    state = await drv.get_state()
    assert state.power is True


@pytest.mark.asyncio
async def test_power_all_off() -> None:
    d1 = _fake_kasa_device(is_on=False)
    d2 = _fake_kasa_device(is_on=False)
    drv = KasaDriver(
        device_id="fixture", name="Fixture",
        host=["a", "b"], kind="plug",
    )
    drv._devices = [d1, d2]

    state = await drv.get_state()
    assert state.power is False


@pytest.mark.asyncio
async def test_brightness_averages() -> None:
    """Brightness is averaged across members that report a value."""

    d1 = _fake_kasa_device(is_on=True, brightness=20)
    d2 = _fake_kasa_device(is_on=True, brightness=80)
    drv = KasaDriver(
        device_id="fixture", name="Fixture",
        host=["a", "b"], kind="bulb",
    )
    drv._devices = [d1, d2]

    state = await drv.get_state()
    assert state.attributes["brightness"] == 50


@pytest.mark.asyncio
async def test_state_attributes_preserve_original_host_shape() -> None:
    d1 = _fake_kasa_device(is_on=True)
    d2 = _fake_kasa_device(is_on=False)
    drv = KasaDriver(
        device_id="fixture", name="Fixture",
        host=["a", "b"], kind="plug",
    )
    drv._devices = [d1, d2]

    state = await drv.get_state()
    assert state.attributes["host"] == ["a", "b"]


# -- partial failure -------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_failure_does_not_abort_fanout() -> None:
    """Member 2's turn_on raising must not prevent member 1 from getting it."""

    from drivers.kasa_driver import KasaException

    d1 = _fake_kasa_device()
    d2 = _fake_kasa_device()
    d2.turn_on.side_effect = KasaException("simulated network blip")

    drv = KasaDriver(
        device_id="fixture", name="Fixture",
        host=["a", "b"], kind="plug",
    )
    drv._devices = [d1, d2]

    # Should NOT raise — partial failures are logged.
    await drv.execute(DeviceAction(action="turn_on"))

    d1.turn_on.assert_awaited_once()
    d2.turn_on.assert_awaited_once()


@pytest.mark.asyncio
async def test_all_hosts_update_failure_returns_last_known_state() -> None:
    """If every host fails to update, fall back to last-known state."""

    from drivers.kasa_driver import KasaException

    d1 = _fake_kasa_device(is_on=True)
    d2 = _fake_kasa_device(is_on=True)
    d1.update.side_effect = KasaException("blip 1")
    d2.update.side_effect = KasaException("blip 2")

    drv = KasaDriver(
        device_id="fixture", name="Fixture",
        host=["a", "b"], kind="plug",
    )
    drv._devices = [d1, d2]
    # Seed a known last_state so the fallback is observable.
    from schemas.device import DeviceState
    drv._last_state = DeviceState(
        power=True, attributes={"host": ["a", "b"], "kind": "plug", "mock": False}
    )

    state = await drv.get_state()
    # Falls back to last_state's power=True even though devices "report" off.
    assert state.power is True


# -- construction-time failure raises --------------------------------------


@pytest.mark.asyncio
async def test_first_connect_failure_raises() -> None:
    """If any host fails to connect on first probe, the error must propagate."""

    from drivers.kasa_driver import KasaException

    drv = KasaDriver(
        device_id="fixture", name="Fixture",
        host=["a", "b"], kind="plug",
    )

    async def bad_connect(host: str):
        if host == "b":
            raise KasaException("unreachable")
        return _fake_kasa_device()

    with patch("drivers.kasa_driver.Device") as DeviceMock:
        DeviceMock.connect = bad_connect
        with pytest.raises(KasaException):
            await drv._ensure_devices()


# -- backward compatibility: single-host config still works ----------------


@pytest.mark.asyncio
async def test_single_host_str_still_works() -> None:
    """Existing single-host configs must continue to behave identically."""

    d = _fake_kasa_device()
    drv = KasaDriver(
        device_id="solo", name="Solo",
        host="192.168.1.10", kind="plug",
    )
    drv._devices = [d]

    await drv.execute(DeviceAction(action="turn_on"))
    d.turn_on.assert_awaited_once()

    state = await drv.get_state()
    assert state.attributes["host"] == "192.168.1.10"  # original shape preserved
