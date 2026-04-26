"""Device driver registry.

The registry is a flat ``device_id -> DeviceDriver`` map. The core API
dispatches every device-targeted call through this layer; ``core/`` is not
permitted to import concrete driver classes directly.

All accessor methods are async because :class:`drivers.base.DeviceDriver` is
async — see the design note in ``drivers/base.py``.
"""

from __future__ import annotations

from drivers.base import DeviceDriver
from schemas.device import DeviceAction, DeviceInfo, DeviceState


class DriverRegistry:
    """Holds the active set of drivers keyed by device ID."""

    def __init__(self) -> None:
        self._drivers: dict[str, DeviceDriver] = {}

    def register(self, device_id: str, driver: DeviceDriver) -> None:
        """Add (or replace) the driver for *device_id*.

        Replacing is allowed so the API layer can swap a driver instance
        without restarting (e.g. on config reload).
        """

        self._drivers[device_id] = driver

    def get(self, device_id: str) -> DeviceDriver:
        """Return the driver registered for *device_id*.

        Raises:
            KeyError: if no driver is registered for the given ID.
        """

        if device_id not in self._drivers:
            raise KeyError(f"no driver registered for device_id={device_id!r}")
        return self._drivers[device_id]

    async def list_devices(self) -> list[DeviceInfo]:
        """Return :class:`DeviceInfo` for every registered driver."""

        return [await driver.get_info() for driver in self._drivers.values()]

    async def execute_action(
        self, device_id: str, action: DeviceAction
    ) -> DeviceState:
        """Dispatch *action* to the driver for *device_id* and return the new state.

        Raises:
            KeyError: if the device is not registered.
        """

        driver = self.get(device_id)
        return await driver.execute(action)
