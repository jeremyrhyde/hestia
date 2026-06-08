"""Application entry point.

Wires every layer of Hestia together and starts the FastAPI server.

Initialization order (per ``core/README.md``):

1. :class:`config.Settings`
2. ``devices.yaml`` -> :class:`schemas.config.DevicesConfig`
3. :class:`core.events.EventBus`
4. :class:`core.state.StateStore` -> ``await store.start()``
5. :class:`drivers.registry.DriverRegistry` (event_bus injected)
   + driver factory -> register one driver per device entry
6. :class:`core.scenes.SceneEngine`
7. :class:`core.scheduler.Scheduler` -> ``await scheduler.start()``
8. :class:`core.websocket.WebSocketManager` (subscribed to bus)
9. :func:`core.api.create_app` -> :class:`fastapi.FastAPI`

Shutdown is the reverse of startup:

1. ``await scheduler.stop()``
2. ``await registry.close_all()``
3. ``await state_store.close()``

Usage::

    uv run python main.py
    # or
    uv run uvicorn main:app --host 0.0.0.0 --port 8000

The lifespan context handles startup/shutdown for both invocations.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Type

import uvicorn
from fastapi import FastAPI

from config import Settings, load_devices_config
from core.api import create_app
from core.events import EventBus
from core.reconciler import StateReconciler
from core.scenes import SceneEngine
from core.scheduler import Scheduler
from core.state import StateStore
from core.websocket import WebSocketManager
from drivers.base import DeviceDriver
from drivers.kasa_driver import KasaDriver
from drivers.registry import DriverRegistry
from drivers.relay_driver import RelayDriver
from drivers.spotify_driver import SpotifyDriver
from schemas.config import DeviceConfig
from schemas.events import Event, EventType

logger = logging.getLogger(__name__)


# Driver factory map. Adding a new driver type:
#   1. Implement the driver class in ``drivers/`` extending DeviceDriver.
#   2. Add a Literal value to ``schemas.config.DeviceConfig.driver``.
#   3. Add the entry below.
DRIVER_FACTORY: dict[str, Type[DeviceDriver]] = {
    "relay": RelayDriver,
    "kasa": KasaDriver,
    "spotify": SpotifyDriver,
}


def _build_drivers(
    devices: list[DeviceConfig],
) -> tuple[list[tuple[str, DeviceDriver]], list[dict[str, Any]]]:
    """Construct one driver per ``DeviceConfig`` entry.

    Returns ``(drivers, failures)``. A failure dict has the shape::

        {"id": str, "driver": str, "error": str}

    A bad driver does not abort startup — the rest of the system stays
    usable for editing scenes / schedules.
    """

    drivers: list[tuple[str, DeviceDriver]] = []
    failures: list[dict[str, Any]] = []

    for entry in devices:
        factory = DRIVER_FACTORY.get(entry.driver)
        if factory is None:
            failures.append(
                {
                    "id": entry.id,
                    "driver": entry.driver,
                    "error": f"unknown driver type {entry.driver!r}",
                }
            )
            logger.error(
                "main: unknown driver type %r for device %s",
                entry.driver,
                entry.id,
            )
            continue
        try:
            driver = factory(
                device_id=entry.id, name=entry.name, **entry.params
            )
        except Exception as exc:
            failures.append(
                {
                    "id": entry.id,
                    "driver": entry.driver,
                    "error": str(exc),
                }
            )
            logger.exception(
                "main: failed to construct driver for %s (%s)",
                entry.id,
                entry.driver,
            )
            continue
        drivers.append((entry.id, driver))
        logger.info("main: registered %s (%s)", entry.id, entry.driver)

    return drivers, failures


async def _build_components(
    settings: Settings,
) -> tuple[
    EventBus,
    StateStore,
    DriverRegistry,
    SceneEngine,
    Scheduler,
    WebSocketManager,
    StateReconciler,
    list[dict[str, Any]],
    int,
]:
    """Build and wire every runtime component.

    Returns the components plus a list of driver failures and the count
    of successfully-registered devices (for the ``/health`` endpoint).
    """

    # 1. Load and validate ``devices.yaml`` (empty if missing).
    devices_config = load_devices_config(settings.DEVICES_CONFIG_PATH)
    if not devices_config.devices:
        logger.warning(
            "main: no devices configured (looked at %s). Server will boot "
            "with an empty registry — scene/schedule editing still works.",
            settings.DEVICES_CONFIG_PATH,
        )

    # 2. Event bus.
    bus = EventBus()

    # 3. State store.
    state_store = StateStore(settings.DB_PATH, bus)
    await state_store.start()

    # 4. Driver registry + drivers.
    registry = DriverRegistry(event_bus=bus)
    constructed, failures = _build_drivers(devices_config.devices)
    successfully_registered: list[str] = []
    for device_id, driver in constructed:
        # Probe the driver before fully registering. Drivers like KasaDriver
        # connect lazily on first state read; if that connect fails, the
        # device should land in `failures` (visible at /health) rather than
        # silently degrading to mock.
        try:
            info = await driver.get_info()
        except Exception as exc:
            failures.append(
                {
                    "id": device_id,
                    "driver": type(driver).__name__,
                    "error": f"probe failed: {exc!r}",
                }
            )
            logger.error(
                "main: device %s failed initial probe (%r) — not registered",
                device_id,
                exc,
            )
            # Best-effort: clean up driver resources so we don't leak.
            close = getattr(driver, "close", None)
            if callable(close):
                try:
                    await close()
                except Exception:  # pragma: no cover
                    logger.exception("main: cleanup of %s failed", device_id)
            continue

        registry.register(device_id, driver)
        successfully_registered.append(device_id)
        try:
            await bus.publish(
                Event(
                    type=EventType.DEVICE_REGISTERED,
                    source="startup",
                    device_id=device_id,
                    data={"info": info.model_dump(mode="json")},
                )
            )
            # Seed the state store so subsequent DEVICE_STATE_CHANGED
            # auto-persist hooks have a row to update.
            await state_store.upsert_device(info)
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "main: failed to publish DEVICE_REGISTERED for %s",
                device_id,
            )

    # 5. Scene engine.
    scene_engine = SceneEngine(registry, bus)

    # 6. Scheduler.
    scheduler = Scheduler(state_store, scene_engine, bus)
    await scheduler.start()

    # 7. WebSocket manager.
    ws_manager = WebSocketManager()
    ws_manager.subscribe_to_bus(bus)

    # 8. State reconciler — corrects UI/cache drift caused by out-of-band
    #    changes (vendor app, device-side schedules, physical switches).
    #    Observes only; gated on having a connected WS client.
    reconciler = StateReconciler(
        registry,
        state_store,
        bus,
        ws_manager,
        poll_seconds=settings.RECONCILE_POLL_SECONDS,
    )
    await reconciler.start()

    return (
        bus,
        state_store,
        registry,
        scene_engine,
        scheduler,
        ws_manager,
        reconciler,
        failures,
        len(successfully_registered),
    )


def _make_lifespan(settings: Settings):
    """Build a lifespan context bound to *settings*.

    The lifespan owns the actual component lifecycle so unit tests can
    construct an app without spinning up the real lifespan.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        (
            bus,
            state_store,
            registry,
            scene_engine,
            scheduler,
            ws_manager,
            reconciler,
            failures,
            n_devices,
        ) = await _build_components(settings)

        # Wire components onto app.state so endpoints + /health can read them.
        app.state.event_bus = bus
        app.state.registry = registry
        app.state.state_store = state_store
        app.state.scene_engine = scene_engine
        app.state.scheduler = scheduler
        app.state.ws_manager = ws_manager
        app.state.settings = settings
        app.state.devices_failed = failures
        app.state.devices_registered = n_devices

        logger.info(
            "main: ready — %d device(s) registered, %d failed",
            n_devices,
            len(failures),
        )

        try:
            yield
        finally:
            logger.info("main: shutting down")
            try:
                await reconciler.stop()
            except Exception:  # pragma: no cover
                logger.exception("main: reconciler.stop failed")
            try:
                await scheduler.stop()
            except Exception:  # pragma: no cover
                logger.exception("main: scheduler.stop failed")
            try:
                await registry.close_all()
            except Exception:  # pragma: no cover
                logger.exception("main: registry.close_all failed")
            try:
                await state_store.close()
            except Exception:  # pragma: no cover
                logger.exception("main: state_store.close failed")

    return lifespan


def _configure_logging(level: str) -> None:
    """Configure the root logger from ``settings.LOG_LEVEL``."""

    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


def build_app(settings: Settings | None = None) -> FastAPI:
    """Construct the public :class:`FastAPI` instance with lifespan wiring.

    The actual driver/store/scheduler initialisation happens inside the
    lifespan context so module import does not perform I/O.
    """

    settings = settings or Settings()
    _configure_logging(settings.LOG_LEVEL)

    # Stub state for the FastAPI factory — the real values are written
    # into app.state inside the lifespan. We pass placeholders that
    # would only be touched if a request landed before lifespan startup
    # finished, which FastAPI's lifespan contract prevents.
    placeholder_registry = DriverRegistry()
    placeholder_state: Any = None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with _make_lifespan(settings)(app):
            yield

    app = create_app(
        registry=placeholder_registry,
        state_store=placeholder_state,
        scene_engine=placeholder_state,
        scheduler=placeholder_state,
        ws_manager=WebSocketManager(),
        settings=settings,
    )
    # FastAPI 0.95+ allows passing lifespan to the constructor, but
    # ``create_app`` doesn't expose it; attach now.
    app.router.lifespan_context = lifespan

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, Any]:
        """Liveness + boot summary.

        Returns the count of registered devices and the failure list so
        operators can confirm what came up at startup without scraping
        the logs.
        """

        return {
            "status": "ok",
            "devices_registered": getattr(
                app.state, "devices_registered", 0
            ),
            "devices_failed": getattr(app.state, "devices_failed", []),
        }

    return app


# ``uvicorn main:app`` resolves this top-level binding.
app = build_app()


if __name__ == "__main__":
    settings = Settings()
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=False,
    )
