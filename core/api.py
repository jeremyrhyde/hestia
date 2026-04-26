"""FastAPI application factory.

Wires the device, scene, schedule, and WebSocket endpoints onto a single
:class:`fastapi.FastAPI` instance. Construction is a factory rather than
a module-level singleton so ``main.py`` can inject the registry, state
store, scene engine, scheduler, and WebSocket manager — and so tests can
build a hermetic app with mock components.

Dependency-injection pattern
----------------------------

Endpoints use ``fastapi.Request.app.state`` to retrieve the wired
components. Storing them on ``app.state`` keeps the handler signatures
clean (no ``Depends`` boilerplate) and matches FastAPI's idiomatic
"per-app dependencies" approach.

URL layout
----------

API routes live at the root (``/devices/...``, ``/scenes/...``,
``/schedules/...``, ``/ws``) per the spec in ``home-auto-context.md``.
Static frontend assets, if present, are mounted under ``/ui/`` so they
cannot collide with API paths. The mount is optional — if
``settings.WEB_DIR`` does not exist yet (e.g. before Phase 4a) the app
still boots and a warning is logged.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import (
    APIRouter,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.staticfiles import StaticFiles

from schemas.device import DeviceAction, DeviceInfo, DeviceState
from schemas.scene import Scene
from schemas.schedule import Schedule

if TYPE_CHECKING:  # pragma: no cover
    from config import Settings
    from core.scenes import SceneEngine
    from core.scheduler import Scheduler
    from core.state import StateStore
    from core.websocket import WebSocketManager
    from drivers.registry import DriverRegistry

logger = logging.getLogger(__name__)


UI_MOUNT_PATH = "/ui"
"""Where static frontend assets are mounted.

Phase 4a (Touchscreen UI) builds the SPA into ``settings.WEB_DIR`` and
the user opens ``http://<pi>:8000/ui/`` in Chromium kiosk mode. Mounted
under a sub-path to avoid any chance of shadowing API routes.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _registry(request: Request) -> "DriverRegistry":
    return request.app.state.registry  # type: ignore[no-any-return]


def _store(request: Request) -> "StateStore":
    return request.app.state.state_store  # type: ignore[no-any-return]


def _engine(request: Request) -> "SceneEngine":
    return request.app.state.scene_engine  # type: ignore[no-any-return]


def _scheduler(request: Request) -> "Scheduler":
    return request.app.state.scheduler  # type: ignore[no-any-return]


def _ws_manager(app_or_ws: Any) -> "WebSocketManager":
    # Accepts either a Request or a WebSocket — both expose ``.app``.
    return app_or_ws.app.state.ws_manager  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------


def _build_devices_router() -> APIRouter:
    router = APIRouter(prefix="/devices", tags=["devices"])

    @router.get("/", response_model=list[DeviceInfo])
    async def list_devices(request: Request) -> list[DeviceInfo]:
        return await _registry(request).list_devices()

    @router.get("/{device_id}", response_model=DeviceInfo)
    async def get_device(device_id: str, request: Request) -> DeviceInfo:
        try:
            driver = _registry(request).get(device_id)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"device {device_id!r} not found",
            ) from None
        return await driver.get_info()

    @router.post("/{device_id}/action", response_model=DeviceState)
    async def execute_device_action(
        device_id: str, action: DeviceAction, request: Request
    ) -> DeviceState:
        try:
            return await _registry(request).execute_action(
                device_id, action, source="api"
            )
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"device {device_id!r} not found",
            ) from None

    return router


def _build_scenes_router() -> APIRouter:
    router = APIRouter(prefix="/scenes", tags=["scenes"])

    @router.get("/", response_model=list[Scene])
    async def list_scenes(request: Request) -> list[Scene]:
        return await _store(request).list_scenes()

    @router.get("/{scene_id}", response_model=Scene)
    async def get_scene(scene_id: str, request: Request) -> Scene:
        scene = await _store(request).get_scene(scene_id)
        if scene is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"scene {scene_id!r} not found",
            )
        return scene

    @router.post("/", response_model=Scene)
    async def create_scene(scene: Scene, request: Request) -> Scene:
        await _store(request).upsert_scene(scene)
        return scene

    @router.put("/{scene_id}", response_model=Scene)
    async def update_scene(
        scene_id: str, scene: Scene, request: Request
    ) -> Scene:
        if scene.id != scene_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"path scene_id ({scene_id!r}) does not match body id "
                    f"({scene.id!r})"
                ),
            )
        await _store(request).upsert_scene(scene)
        return scene

    @router.delete("/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_scene(scene_id: str, request: Request) -> None:
        await _store(request).delete_scene(scene_id)

    @router.post("/{scene_id}/execute")
    async def execute_scene(
        scene_id: str, request: Request
    ) -> list[dict[str, Any]]:
        scene = await _store(request).get_scene(scene_id)
        if scene is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"scene {scene_id!r} not found",
            )
        results = await _engine(request).execute_scene(scene)
        # The result list contains DeviceState objects which Pydantic will
        # serialize, but FastAPI default serialization handles that for us
        # (BaseModel objects are recognised). We return the list as-is.
        return results

    return router


def _build_schedules_router() -> APIRouter:
    router = APIRouter(prefix="/schedules", tags=["schedules"])

    @router.get("/", response_model=list[Schedule])
    async def list_schedules(request: Request) -> list[Schedule]:
        return await _store(request).list_schedules()

    @router.get("/{schedule_id}", response_model=Schedule)
    async def get_schedule(schedule_id: str, request: Request) -> Schedule:
        schedule = await _store(request).get_schedule(schedule_id)
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"schedule {schedule_id!r} not found",
            )
        return schedule

    @router.post("/", response_model=Schedule)
    async def create_schedule(
        schedule: Schedule, request: Request
    ) -> Schedule:
        await _store(request).upsert_schedule(schedule)
        await _scheduler(request).reload()
        return schedule

    @router.patch("/{schedule_id}", response_model=Schedule)
    async def patch_schedule(
        schedule_id: str,
        patch: dict[str, Any],
        request: Request,
    ) -> Schedule:
        existing = await _store(request).get_schedule(schedule_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"schedule {schedule_id!r} not found",
            )
        merged = existing.model_dump()
        merged.update(patch)
        # Force the path id to win — clients can't rename via PATCH.
        merged["id"] = schedule_id
        try:
            updated = Schedule.model_validate(merged)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"invalid schedule patch: {exc}",
            ) from exc
        await _store(request).upsert_schedule(updated)
        await _scheduler(request).reload()
        return updated

    @router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_schedule(schedule_id: str, request: Request) -> None:
        await _store(request).delete_schedule(schedule_id)
        await _scheduler(request).reload()

    return router


def _build_ws_router() -> APIRouter:
    router = APIRouter(tags=["websocket"])

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        manager = _ws_manager(websocket)
        await manager.connect(websocket)
        try:
            # The endpoint never sends data on its own — the manager
            # broadcasts via the event-bus subscription. We just keep the
            # connection alive and wait for client messages (which we
            # currently ignore) or disconnect.
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        except Exception:  # pragma: no cover - defensive
            logger.exception("WebSocket loop raised; closing connection")
        finally:
            await manager.disconnect(websocket)

    return router


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def create_app(
    *,
    registry: "DriverRegistry",
    state_store: "StateStore",
    scene_engine: "SceneEngine",
    scheduler: "Scheduler",
    ws_manager: "WebSocketManager",
    settings: "Settings | None" = None,
    mount_static: bool = True,
) -> FastAPI:
    """Build and wire a :class:`FastAPI` instance.

    Args:
        registry: Driver registry.
        state_store: Started :class:`StateStore` (DB connection open).
        scene_engine: Scene engine wired to the registry + bus.
        scheduler: Scheduler instance (caller is responsible for ``start()``).
        ws_manager: WebSocket manager already subscribed to the event bus.
        settings: Application settings; used to locate ``WEB_DIR`` for the
            static mount. May be ``None`` in tests.
        mount_static: If ``False``, skip the static-file mount entirely.
            Tests pass ``False`` to keep the app hermetic.

    The returned app has the wired components on ``app.state``:
    ``registry``, ``state_store``, ``scene_engine``, ``scheduler``,
    ``ws_manager``, ``settings``.
    """

    app = FastAPI(
        title="Hestia",
        description="Raspberry Pi home automation core.",
        version="0.1.0",
    )

    app.state.registry = registry
    app.state.state_store = state_store
    app.state.scene_engine = scene_engine
    app.state.scheduler = scheduler
    app.state.ws_manager = ws_manager
    app.state.settings = settings

    app.include_router(_build_devices_router())
    app.include_router(_build_scenes_router())
    app.include_router(_build_schedules_router())
    app.include_router(_build_ws_router())

    if mount_static and settings is not None:
        web_dir = Path(settings.WEB_DIR)
        if web_dir.exists() and web_dir.is_dir():
            app.mount(
                UI_MOUNT_PATH,
                StaticFiles(directory=str(web_dir), html=True),
                name="ui",
            )
            logger.info(
                "Static UI mounted at %s -> %s", UI_MOUNT_PATH, web_dir
            )
        else:
            logger.warning(
                "Static UI directory %s does not exist; skipping mount. "
                "Phase 4a will create it.",
                web_dir,
            )

    return app
