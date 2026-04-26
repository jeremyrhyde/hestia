"""Abstract base class for device drivers.

Every concrete driver in :mod:`drivers` extends :class:`DeviceDriver` and
implements its four abstract methods. Drivers wrap an underlying Python module
(``python-kasa``, ``gpiozero``, the existing Spotify module, etc.) and expose
a uniform interface to the rest of the system.

Sync vs async
-------------

The four driver methods are declared **async**. Rationale:

- The rest of the stack (FastAPI, ``aiosqlite``, ``python-kasa``) is async.
- Network-bound drivers (Kasa over WiFi, Spotify over HTTP) benefit from
  cooperative concurrency; we don't want one slow Kasa call blocking the
  scene engine while it iterates other actions.
- GPIO/relay drivers can simply ``await`` no I/O — they pay no real cost for
  being declared async.

Concrete drivers wrapping a synchronous library should run blocking calls
through ``asyncio.to_thread`` (or equivalent) inside their async methods.
"""

from __future__ import annotations

import abc

from schemas.device import DeviceAction, DeviceCapability, DeviceInfo, DeviceState


class DeviceDriver(abc.ABC):
    """Contract every device driver must implement.

    Subclasses are expected to be safe to construct without performing I/O —
    network probes and hardware initialization should happen lazily on first
    call, so the registry can build the driver dictionary at import time.
    """

    @abc.abstractmethod
    async def get_info(self) -> DeviceInfo:
        """Return the device's full metadata and current state."""

    @abc.abstractmethod
    async def get_state(self) -> DeviceState:
        """Return the device's current state only."""

    @abc.abstractmethod
    async def execute(self, action: DeviceAction) -> DeviceState:
        """Run *action* on the device and return the resulting state.

        Drivers should raise an exception on failure rather than silently
        returning a stale state — the registry / scene engine will catch and
        report the error. Drivers may, however, swallow transient network
        errors and return last-known state if that is the appropriate
        behavior for the underlying device (this is a per-driver choice and
        should be documented in the driver's docstring).
        """

    @abc.abstractmethod
    async def get_capabilities(self) -> list[DeviceCapability]:
        """Return the device's declared capabilities."""
