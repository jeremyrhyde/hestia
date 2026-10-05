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

Pantheon module contract: API routes live under ``/api`` (``/api/devices/...``,
``/api/scenes/...``, ``/api/schedules/...``, ``/api/ws``); ``/health`` stays
at the root; the static UI is served at ``/`` by :func:`mount_ui`, which
must be the last thing registered. The mount is optional — if
``settings.WEB_DIR`` does not exist the app still boots and a warning is
logged.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
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

from core.scheduler import next_occurrence
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


UI_MOUNT_PATH = "/"
"""Where static frontend assets are mounted (the Pantheon contract: UI at ``/``)."""


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


class _UIFiles(StaticFiles):
    """Static UI at "/". Vite's hashed files under assets/ never change, so
    they cache forever; everything else (index.html, the manifest, icons) is
    revalidated on every load so a rebuild is picked up — the kiosk never
    gets a hard refresh. It also receives WebSocket connects that match no
    route (e.g. an old cached page retrying /ws); close those cleanly instead
    of letting StaticFiles assert on a non-HTTP scope."""

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "websocket":
            await WebSocket(scope, receive, send).close()
            return
        await super().__call__(scope, receive, send)

    def file_response(
        self, full_path: Any, stat_result: Any, scope: Any, status_code: int = 200
    ) -> Any:
        response = super().file_response(full_path, stat_result, scope, status_code)
        relative = Path(full_path).resolve().relative_to(
            Path(self.directory).resolve()
        )
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
            if relative.parts[0] == "assets"
            else "no-cache"
        )
        return response


def mount_ui(app: FastAPI, settings: "Settings") -> None:
    """Serve the static UI at ``/``.

    Call this last: a mount at ``/`` matches every path, so any route
    registered after it is unreachable.
    """

    web_dir = Path(settings.WEB_DIR)
    if not web_dir.is_dir():
        logger.warning(
            "Static UI directory %s does not exist; skipping mount "
            "— run `make build` to build the frontend.",
            web_dir,
        )
        return
    app.mount(
        UI_MOUNT_PATH, _UIFiles(directory=str(web_dir), html=True), name="ui"
    )
    logger.info("Static UI mounted at %s -> %s", UI_MOUNT_PATH, web_dir)


def _build_status_router() -> APIRouter:
    """GET /api/status — the optional Pantheon module-status contract."""

    router = APIRouter(tags=["status"])

    @router.get("/status")
    async def module_status(request: Request) -> dict[str, Any]:
        state = request.app.state
        registered = getattr(state, "devices_registered", 0)
        failed = getattr(state, "devices_failed", [])
        stats: list[dict[str, Any]] = [
            {"label": "Devices registered", "value": registered, "kind": "count"},
            {
                "label": "Devices failed",
                "value": len(failed),
                "kind": "count",
                "warn": bool(failed),
            },
        ]
        summary = None
        schedules = await _store(request).list_schedules()
        upcoming = next_occurrence(schedules, datetime.now().astimezone())
        if upcoming is not None:
            schedule, at = upcoming
            stats.append({
                "label": "Next schedule",
                "value": at.astimezone(timezone.utc).isoformat(),
                "kind": "time",
            })
            summary = f"Next: {schedule.name} at {schedule.time}"
        return {
            "state": "degraded" if failed else "ok",
            "summary": summary,
            "stats": stats,
        }

    return router


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

    api = APIRouter(prefix="/api")
    for build in (
        _build_devices_router,
        _build_scenes_router,
        _build_schedules_router,
        _build_ws_router,
        _build_status_router,
    ):
        api.include_router(build())
    app.include_router(api)

    if mount_static and settings is not None:
        mount_ui(app, settings)

    return app
