"""Kasa smart-plug / smart-bulb driver.

Wraps one or more TP-Link Kasa devices using ``python-kasa`` 0.10+. Devices
are addressed by IP/hostname; the new factory API (``Device.connect(host=...)``)
is used so the driver supports both the original IOT protocol family and the
newer SMART devices without code changes.

Single-device vs tandem fixtures
--------------------------------

The ``host`` parameter accepts either:

- a single string  (``host: 192.168.1.6``) — the historical, simple case
- a list of strings (``host: [192.168.1.6, 192.168.1.7]``) — a "tandem"
  fixture where multiple physical Kasa devices are presented as a single
  logical device. Common for double-bulb fixtures where a user wants the
  pair controlled together. From the API/UI perspective there is one
  device; internally each command fans out across all hosts concurrently.

For tandem fixtures:

- Power state is reported as ``any(d.is_on)`` — toggling the UI feels
  responsive even if the bulbs have drifted out of sync.
- Brightness is reported as the average of currently-on members'
  brightness (or simply averaged across all hosts when none are on).
- Capabilities are uniform across members. All hosts in a tandem
  fixture are assumed to be the same ``kind`` (plug or bulb) — mixing
  is not supported.

Plugs vs bulbs
--------------

The ``kind`` constructor argument is informational and decides which
capabilities the driver advertises:

- ``"plug"`` → ``[TOGGLE]``
- ``"bulb"`` → ``[TOGGLE, DIMMER]`` and accepts ``set_brightness``.

Network resilience
------------------

``await device.update()`` is what triggers I/O. Any
:class:`kasa.KasaException` raised during update / execute is logged and the
driver returns the last known state — this keeps a momentary WiFi blip from
killing a scene execution. ``self._last_state`` always holds the most recent
*successful* read.

Construction-time connection failures (any host unreachable) are RAISED so
they appear in ``/health.devices_failed`` rather than silently degrading to a
fake-success boot. Test scripts that want mock behavior set ``driver._mock =
True`` after construction.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from drivers.base import DeviceDriver
from schemas.device import (
    DeviceAction,
    DeviceCapability,
    DeviceInfo,
    DeviceState,
    DeviceType,
    StandardAction,
)

logger = logging.getLogger(__name__)

try:
    from kasa import Device, KasaException  # type: ignore[import-not-found]

    _KASA_AVAILABLE = True
except Exception as exc:  # pragma: no cover - kasa always installed in our env
    Device = None  # type: ignore[assignment, misc]
    KasaException = Exception  # type: ignore[assignment, misc]
    _KASA_AVAILABLE = False
    logger.debug("kasa unavailable at import time: %r", exc)


def _normalize_hosts(host: str | list[str]) -> list[str]:
    """Coerce a single host or a list into a non-empty list of hosts."""

    if isinstance(host, str):
        hosts = [host]
    elif isinstance(host, list):
        hosts = [str(h) for h in host]
    else:
        raise ValueError(
            f"KasaDriver: host must be a string or list of strings, got {type(host).__name__}"
        )
    if not hosts:
        raise ValueError("KasaDriver: host list must contain at least one entry")
    return hosts


class KasaDriver(DeviceDriver):
    """Driver for one or more Kasa smart plugs / bulbs.

    Args:
        device_id: Stable slug for the device.
        name: Human-readable label.
        host: IP address or hostname of the Kasa device, OR a list of such
            addresses for a tandem fixture (multiple physical devices
            presented as one logical device).
        kind: Either ``"plug"`` or ``"bulb"``. Determines advertised
            capabilities (bulbs add ``DIMMER``).

    Construction is non-blocking — actual ``Device.connect`` happens lazily
    on the first call so the registry can build the driver dictionary at
    import time without doing network I/O. Probing happens in ``main.py``'s
    startup loop via ``await driver.get_info()``.
    """

    def __init__(
        self,
        device_id: str,
        name: str,
        host: str | list[str],
        kind: Literal["plug", "bulb"] = "plug",
    ) -> None:
        if kind not in ("plug", "bulb"):
            raise ValueError(f"KasaDriver: kind must be 'plug' or 'bulb', got {kind!r}")

        self._id = device_id
        self._name = name
        self._host = host  # preserve original shape for debug / attributes
        self._hosts = _normalize_hosts(host)
        self._kind = kind
        # _devices is None until first connect; then a parallel list of handles.
        self._devices: list[Any] | None = None
        self._mock = not _KASA_AVAILABLE
        self._mock_power = False
        self._mock_brightness = 100
        self._last_state = DeviceState(
            power=False,
            attributes={"host": host, "kind": kind, "mock": self._mock},
        )

    # -- helpers --------------------------------------------------------

    async def _ensure_devices(self) -> list[Any] | None:
        """Connect to every host on first use; reuse handles after that."""

        if self._mock:
            return None
        if self._devices is not None:
            return self._devices

        async def _connect_one(host: str) -> Any:
            return await Device.connect(host=host)

        try:
            self._devices = await asyncio.gather(
                *(_connect_one(h) for h in self._hosts)
            )
            return self._devices
        except (KasaException, Exception) as exc:
            # Construction-time connection failures used to silently flip into
            # mock mode, which masked config errors (wrong IP, device offline)
            # behind a fake-success boot. We now surface the failure so the
            # operator sees it in /health and the registry doesn't pretend to
            # have a working device. For tandem fixtures, ANY host failing
            # raises — operators want to know the fixture is partially down.
            logger.error(
                "KasaDriver(%s): connect to %s failed (%r)",
                self._id,
                self._hosts,
                exc,
            )
            raise

    async def _refresh(self) -> DeviceState:
        if self._mock:
            self._last_state = DeviceState(
                power=self._mock_power,
                attributes=self._mock_attributes(),
            )
            return self._last_state

        devices = await self._ensure_devices()
        if devices is None:
            return self._last_state

        # Fan out updates concurrently.
        results = await asyncio.gather(
            *(self._update_one(d) for d in devices), return_exceptions=True
        )
        # Discard hosts whose update failed; aggregate over the rest.
        live = [
            d for d, r in zip(devices, results) if not isinstance(r, BaseException)
        ]
        if not live:
            # Every host failed — return the last known state so a brief
            # network blip doesn't poison the system.
            logger.warning(
                "KasaDriver(%s): all hosts failed update — returning last known state",
                self._id,
            )
            return self._last_state

        attrs: dict[str, Any] = {
            "host": self._host,
            "kind": self._kind,
            "mock": False,
        }
        if self._kind == "bulb":
            brightnesses = [
                b for b in (self._read_brightness(d) for d in live) if b is not None
            ]
            if brightnesses:
                # Average across whatever members reported a value.
                attrs["brightness"] = int(sum(brightnesses) / len(brightnesses))

        self._last_state = DeviceState(
            power=any(bool(d.is_on) for d in live),
            attributes=attrs,
        )
        return self._last_state

    async def _update_one(self, device: Any) -> None:
        """update() one device, letting the caller handle exceptions."""

        await device.update()

    def _read_brightness(self, device: Any) -> int | None:
        """Best-effort brightness read for a single Kasa device.

        Returns None if the device does not expose brightness (e.g. an on/off
        only smart bulb). python-kasa 0.10 may surface brightness either as
        an attribute or via the ``Light`` module.
        """

        brightness = getattr(device, "brightness", None)
        if brightness is None and hasattr(device, "modules"):
            try:
                light_module = device.modules.get("Light")
            except Exception:  # noqa: BLE001
                light_module = None
            if light_module is not None:
                brightness = getattr(light_module, "brightness", None)
        if brightness is None:
            return None
        return int(brightness)

    def _mock_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "host": self._host,
            "kind": self._kind,
            "mock": True,
        }
        if self._kind == "bulb":
            attrs["brightness"] = self._mock_brightness
        return attrs

    async def _set_brightness(self, level: int) -> None:
        if not 0 <= level <= 100:
            raise ValueError(
                f"KasaDriver: brightness level must be 0-100, got {level}"
            )
        if self._kind != "bulb":
            raise ValueError(
                "KasaDriver: set_brightness is only supported for bulbs"
            )

        if self._mock:
            self._mock_brightness = level
            self._mock_power = level > 0
            return

        devices = await self._ensure_devices()
        if devices is None:
            self._mock_brightness = level
            self._mock_power = level > 0
            return

        await self._fanout(self._set_brightness_one, level, label="set_brightness")

    async def _set_brightness_one(self, device: Any, level: int) -> None:
        """Set brightness on a single Kasa device."""

        light_module = None
        if hasattr(device, "modules"):
            try:
                light_module = device.modules.get("Light")
            except Exception:  # noqa: BLE001
                light_module = None
        if light_module is not None and hasattr(light_module, "set_brightness"):
            await light_module.set_brightness(level)
        elif hasattr(device, "set_brightness"):
            await device.set_brightness(level)
        else:
            raise ValueError(
                "KasaDriver: underlying device does not expose set_brightness"
            )

    async def _fanout(
        self,
        op: Any,
        *args: Any,
        label: str,
    ) -> None:
        """Run ``op(device, *args)`` against every member host concurrently.

        Per-host exceptions are caught and logged so a partial failure
        doesn't abort the rest of the fanout — the surviving members still
        get the command. Aggregated state will reflect what actually
        happened (the failing host won't update).
        """

        devices = await self._ensure_devices()
        if devices is None:
            return

        async def _run(host: str, device: Any) -> None:
            try:
                await op(device, *args)
            except KasaException as exc:
                logger.warning(
                    "KasaDriver(%s): %s on %s failed (%r)",
                    self._id,
                    label,
                    host,
                    exc,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "KasaDriver(%s): %s on %s raised (%r)",
                    self._id,
                    label,
                    host,
                    exc,
                )

        await asyncio.gather(
            *(_run(h, d) for h, d in zip(self._hosts, devices))
        )

    # -- DeviceDriver contract -----------------------------------------

    async def get_info(self) -> DeviceInfo:
        return DeviceInfo(
            id=self._id,
            name=self._name,
            device_type=DeviceType.SWITCH,
            driver_name="KasaDriver",
            capabilities=await self.get_capabilities(),
            state=await self.get_state(),
        )

    async def get_state(self) -> DeviceState:
        return await self._refresh()

    async def execute(self, action: DeviceAction) -> DeviceState:
        match action.action:
            case StandardAction.TURN_ON:
                await self._do_turn_on()
            case StandardAction.TURN_OFF:
                await self._do_turn_off()
            case StandardAction.TOGGLE:
                await self._do_toggle()
            case StandardAction.SET_BRIGHTNESS:
                level = (action.params or {}).get("level")
                if not isinstance(level, int):
                    raise ValueError(
                        "KasaDriver: set_brightness requires params={'level': int}"
                    )
                await self._set_brightness(level)
            case _:
                raise ValueError(
                    f"KasaDriver does not support action {action.action!r}"
                )
        return await self._refresh()

    async def get_capabilities(self) -> list[DeviceCapability]:
        if self._kind == "bulb":
            return [DeviceCapability.TOGGLE, DeviceCapability.DIMMER]
        return [DeviceCapability.TOGGLE]

    async def close(self) -> None:
        """Disconnect every underlying Kasa client."""

        if self._devices is None:
            return
        for d in self._devices:
            disconnect = getattr(d, "disconnect", None)
            if disconnect is None:
                continue
            try:
                result = disconnect()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "KasaDriver(%s): disconnect failed: %r", self._id, exc
                )
        self._devices = None

    # -- internal action helpers ---------------------------------------

    async def _do_turn_on(self) -> None:
        if self._mock:
            self._mock_power = True
            return
        await self._fanout(_call_turn_on, label="turn_on")

    async def _do_turn_off(self) -> None:
        if self._mock:
            self._mock_power = False
            return
        await self._fanout(_call_turn_off, label="turn_off")

    async def _do_toggle(self) -> None:
        # Read first so we know which way to flip — important if some other
        # source toggled the device(s) since our last update.
        state = await self._refresh()
        if state.power:
            await self._do_turn_off()
        else:
            await self._do_turn_on()


# --- bare async wrappers for use with _fanout ----------------------------------
# `_fanout` calls op(device, *args), so the simplest device methods need a
# matching shape. These wrappers exist just to provide that shape without a
# lambda in every call site.

async def _call_turn_on(device: Any) -> None:
    await device.turn_on()


async def _call_turn_off(device: Any) -> None:
    await device.turn_off()
