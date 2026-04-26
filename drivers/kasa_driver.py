"""Kasa smart-plug / smart-bulb driver.

Wraps a single TP-Link Kasa device addressed by IP/hostname using
``python-kasa`` 0.10+. The new factory API (``Device.connect(host=...)``) is
used so this driver supports both the original IOT protocol family and the
newer SMART devices without code changes.

Plugs vs bulbs
--------------

The ``kind`` constructor argument is informational and decides which
capabilities the driver advertises:

- ``"plug"`` → ``[TOGGLE]``
- ``"bulb"`` → ``[TOGGLE, DIMMER]`` and accepts ``set_brightness``.

The actual underlying object returned by ``Device.connect`` is whichever
``kasa`` thinks is appropriate for the host. We don't subclass that — we just
talk to it through the public ``Device`` / ``Light`` interfaces.

Network resilience
------------------

``await device.update()`` is what triggers I/O. Any
:class:`kasa.KasaException` raised during update / execute is logged and the
driver returns the last known state — this keeps a momentary WiFi blip from
killing a scene execution. ``self._last_state`` always holds the most recent
*successful* read.

Mock fallback
-------------

If the very first connect attempt fails (common during macOS development
without a Kasa device on the LAN), the driver flips into ``self._mock = True``
mode. In mock mode, ``power`` is just an internal boolean and brightness is
an internal int — no network calls are issued.
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


class KasaDriver(DeviceDriver):
    """Driver for a Kasa smart plug or smart bulb.

    Args:
        device_id: Stable slug for the device.
        name: Human-readable label.
        host: IP address or hostname of the Kasa device on the LAN.
        kind: Either ``"plug"`` or ``"bulb"``. Determines advertised
            capabilities (bulbs add ``DIMMER``).

    Construction is non-blocking — the actual ``Device.connect`` happens
    lazily on the first call so the registry can build the driver dictionary
    at import time without doing network I/O.
    """

    def __init__(
        self,
        device_id: str,
        name: str,
        host: str,
        kind: Literal["plug", "bulb"] = "plug",
    ) -> None:
        if kind not in ("plug", "bulb"):
            raise ValueError(f"KasaDriver: kind must be 'plug' or 'bulb', got {kind!r}")

        self._id = device_id
        self._name = name
        self._host = host
        self._kind = kind
        self._device: Any = None
        self._mock = not _KASA_AVAILABLE
        self._mock_power = False
        self._mock_brightness = 100
        self._last_state = DeviceState(
            power=False,
            attributes={"host": host, "kind": kind, "mock": self._mock},
        )

    # -- helpers --------------------------------------------------------

    async def _ensure_device(self) -> Any:
        """Connect on first use; subsequent calls reuse the same handle."""

        if self._mock:
            return None
        if self._device is not None:
            return self._device

        try:
            self._device = await Device.connect(host=self._host)
            return self._device
        except (KasaException, Exception) as exc:
            # Construction-time connection failures used to silently flip into
            # mock mode, which masked config errors (wrong IP, device offline)
            # behind a fake-success boot. We now surface the failure so the
            # operator sees it in /health and the registry doesn't pretend to
            # have a working device. Test scripts that need mock behavior set
            # ``driver._mock = True`` explicitly.
            logger.error(
                "KasaDriver(%s): connect to %s failed (%r)",
                self._id,
                self._host,
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

        device = await self._ensure_device()
        if device is None:
            return self._last_state

        try:
            await device.update()
        except KasaException as exc:
            logger.warning(
                "KasaDriver(%s): update failed (%r) — returning last known state",
                self._id,
                exc,
            )
            return self._last_state

        attrs: dict[str, Any] = {
            "host": self._host,
            "kind": self._kind,
            "mock": False,
        }
        if self._kind == "bulb":
            # python-kasa 0.10 exposes brightness via the Light module if the
            # device supports it. Stay defensive: not every "bulb" has a
            # dimmer (e.g. on/off-only smart bulbs).
            brightness = getattr(device, "brightness", None)
            if brightness is None:
                light_module = None
                try:
                    light_module = device.modules.get("Light") if hasattr(device, "modules") else None
                except Exception:  # noqa: BLE001
                    light_module = None
                if light_module is not None:
                    brightness = getattr(light_module, "brightness", None)
            if brightness is not None:
                attrs["brightness"] = int(brightness)

        self._last_state = DeviceState(
            power=bool(device.is_on),
            attributes=attrs,
        )
        return self._last_state

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

        device = await self._ensure_device()
        if device is None:
            self._mock_brightness = level
            self._mock_power = level > 0
            return

        try:
            # python-kasa 0.10 prefers the Light module interface.
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
        except KasaException as exc:
            logger.warning(
                "KasaDriver(%s): set_brightness failed (%r)", self._id, exc
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
        """Disconnect the underlying Kasa client. Optional lifecycle hook."""

        if self._device is not None:
            disconnect = getattr(self._device, "disconnect", None)
            if disconnect is not None:
                try:
                    result = disconnect()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "KasaDriver(%s): disconnect failed: %r", self._id, exc
                    )
        self._device = None

    # -- internal action helpers ---------------------------------------

    async def _do_turn_on(self) -> None:
        if self._mock:
            self._mock_power = True
            return
        device = await self._ensure_device()
        if device is None:
            self._mock_power = True
            return
        try:
            await device.turn_on()
        except KasaException as exc:
            logger.warning("KasaDriver(%s): turn_on failed (%r)", self._id, exc)

    async def _do_turn_off(self) -> None:
        if self._mock:
            self._mock_power = False
            return
        device = await self._ensure_device()
        if device is None:
            self._mock_power = False
            return
        try:
            await device.turn_off()
        except KasaException as exc:
            logger.warning("KasaDriver(%s): turn_off failed (%r)", self._id, exc)

    async def _do_toggle(self) -> None:
        # Read first so we know which way to flip — important if some other
        # source toggled the device since our last update.
        state = await self._refresh()
        if state.power:
            await self._do_turn_off()
        else:
            await self._do_turn_on()
