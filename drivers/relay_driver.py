"""GPIO relay driver.

Wraps a single GPIO pin connected to a relay board (e.g. a 5V mechanical
relay HAT) and exposes it through the :class:`DeviceDriver` interface.

The underlying library, ``gpiozero``, is *synchronous*. Per the design note
in :mod:`drivers.base`, blocking calls are wrapped in
:func:`asyncio.to_thread` so the driver is safe to call from async code
without blocking the event loop.

Active-high vs active-low
-------------------------

Relay boards vary. Some are "active-high" (pulling the signal pin HIGH closes
the relay) and some are "active-low" (HIGH opens the relay). The
``active_high`` constructor argument is forwarded to ``gpiozero.OutputDevice``
which handles the inversion internally — callers of this driver always think
in terms of "on" / "off", never voltage levels.

Mock fallback
-------------

If ``gpiozero`` cannot be imported (e.g. running on macOS during development)
or pin initialisation fails (no Pi hardware, wrong pin factory, etc.) the
driver falls back to a software-only state where ``on`` / ``off`` / ``toggle``
just flip an internal boolean. ``self._mock`` is set so callers can detect
this. A warning is logged at construction time.
"""

from __future__ import annotations

import asyncio
import logging

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

# `gpiozero` is Linux/Pi-only. We import it defensively so the driver module
# itself loads anywhere — the registry can still build a mock instance when
# we're developing on macOS.
try:  # pragma: no cover - exercised on Pi only
    from gpiozero import OutputDevice  # type: ignore[import-not-found]

    _GPIOZERO_AVAILABLE = True
except Exception as exc:  # pragma: no cover - macOS path
    OutputDevice = None  # type: ignore[assignment, misc]
    _GPIOZERO_AVAILABLE = False
    logger.debug("gpiozero unavailable at import time: %r", exc)


class RelayDriver(DeviceDriver):
    """Driver for a single GPIO-connected relay.

    Args:
        device_id: Stable slug for the device (e.g. ``"relay-desk"``).
        name: Human-readable label.
        pin: BCM pin number wired to the relay's signal line.
        active_high: ``True`` if the relay closes when the pin is HIGH.
            Set to ``False`` for active-low boards. Defaults to ``True``.

    Attributes:
        _mock: ``True`` if no real hardware was successfully initialised and
            the driver is operating in software-only mode.
    """

    def __init__(
        self,
        device_id: str,
        name: str,
        pin: int,
        active_high: bool = True,
    ) -> None:
        self._id = device_id
        self._name = name
        self._pin = pin
        self._active_high = active_high
        self._device: OutputDevice | None = None  # type: ignore[valid-type]
        self._mock = False
        self._mock_state = False

        if not _GPIOZERO_AVAILABLE:
            logger.warning(
                "RelayDriver(%s): gpiozero not available — running in MOCK mode",
                device_id,
            )
            self._mock = True
            return

        try:  # pragma: no cover - real hardware path
            self._device = OutputDevice(  # type: ignore[misc]
                pin=pin, active_high=active_high, initial_value=False
            )
        except Exception as exc:  # pragma: no cover
            # BadPinFactory means gpiozero couldn't find a backend (typical
            # on macOS dev machines that have gpiozero installed but no Pi
            # hardware) — fall back to mock so the API server still runs.
            # Any other init failure (pin in use, invalid pin, etc.) on a
            # real Pi is a config error and should be surfaced.
            if type(exc).__name__ == "BadPinFactory":
                logger.warning(
                    "RelayDriver(%s): no GPIO backend available (%r) — running in MOCK mode",
                    device_id,
                    exc,
                )
                self._mock = True
                self._device = None
            else:
                logger.error(
                    "RelayDriver(%s): failed to initialise pin %d (%r)",
                    device_id,
                    pin,
                    exc,
                )
                raise

    # -- helpers --------------------------------------------------------

    def _read_power(self) -> bool:
        if self._mock or self._device is None:
            return self._mock_state
        # OutputDevice.is_active reflects logical on/off (already inverted
        # for active_low boards).
        return bool(self._device.is_active)

    async def _set_on(self) -> None:
        if self._mock or self._device is None:
            self._mock_state = True
            return
        await asyncio.to_thread(self._device.on)

    async def _set_off(self) -> None:
        if self._mock or self._device is None:
            self._mock_state = False
            return
        await asyncio.to_thread(self._device.off)

    async def _toggle(self) -> None:
        if self._mock or self._device is None:
            self._mock_state = not self._mock_state
            return
        await asyncio.to_thread(self._device.toggle)

    # -- DeviceDriver contract -----------------------------------------

    async def get_info(self) -> DeviceInfo:
        return DeviceInfo(
            id=self._id,
            name=self._name,
            device_type=DeviceType.RELAY,
            driver_name="RelayDriver",
            capabilities=await self.get_capabilities(),
            state=await self.get_state(),
        )

    async def get_state(self) -> DeviceState:
        return DeviceState(
            power=self._read_power(),
            attributes={
                "pin": self._pin,
                "active_high": self._active_high,
                "mock": self._mock,
            },
        )

    async def execute(self, action: DeviceAction) -> DeviceState:
        match action.action:
            case StandardAction.TURN_ON:
                await self._set_on()
            case StandardAction.TURN_OFF:
                await self._set_off()
            case StandardAction.TOGGLE:
                await self._toggle()
            case _:
                raise ValueError(
                    f"RelayDriver does not support action {action.action!r}"
                )
        return await self.get_state()

    async def get_capabilities(self) -> list[DeviceCapability]:
        return [DeviceCapability.TOGGLE]

    async def close(self) -> None:
        """Release the GPIO pin. Optional lifecycle hook."""

        if self._device is not None:
            try:  # pragma: no cover - real hardware path
                await asyncio.to_thread(self._device.close)
            except Exception as exc:  # pragma: no cover
                logger.warning("RelayDriver(%s): close failed: %r", self._id, exc)
        self._device = None
