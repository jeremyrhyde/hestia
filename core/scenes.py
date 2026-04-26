"""Scene execution engine.

A scene is an ordered list of device actions. The :class:`SceneEngine`
walks that list, dispatches each action through the
:class:`drivers.registry.DriverRegistry`, optionally inserts a
``delay_ms`` pause before an action, and publishes a single
``SCENE_EXECUTED`` event when the loop finishes.

This module never imports concrete driver classes — it only knows about
the registry interface. That keeps the dependency rule clean: ``core/``
is allowed to talk to ``drivers/`` only through the registry handle it
receives by injection.

Per-action errors are caught and folded into the result list rather than
aborting the entire scene, matching the spec ("if one device action
fails, log it and continue to the next action").

Per-step ``DEVICE_STATE_CHANGED`` events are published by the
:class:`drivers.registry.DriverRegistry` itself (Phase 3 reconciliation),
so the scene engine no longer publishes them — that keeps the firing
uniform regardless of whether the caller is the API, this engine, or
the scheduler.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from core.events import EventBus
from drivers.registry import DriverRegistry
from schemas.device import DeviceAction, DeviceState
from schemas.events import Event, EventType
from schemas.scene import Scene, SceneAction

logger = logging.getLogger(__name__)


class SceneEngine:
    """Execute scene action lists against a driver registry."""

    def __init__(
        self,
        registry: DriverRegistry,
        event_bus: EventBus,
    ) -> None:
        self._registry = registry
        self._bus = event_bus

    async def execute_scene(self, scene: Scene) -> list[dict[str, Any]]:
        """Run every action in *scene* in order, return per-action results.

        Each result dict has the shape::

            {
                "device_id": str,
                "success": bool,
                "state": DeviceState | None,
                "error": str | None,
            }

        After all actions finish (regardless of individual success), a
        single ``SCENE_EXECUTED`` event is published with the full result
        list and ``source="scene:{scene.id}"``.
        """

        source = f"scene:{scene.id}"
        results: list[dict[str, Any]] = []

        for step in scene.actions:
            result = await self._run_step(step, source)
            results.append(result)

        await self._bus.publish(
            Event(
                type=EventType.SCENE_EXECUTED,
                source=source,
                data={
                    "scene_id": scene.id,
                    "results": [_serialize_result(r) for r in results],
                },
            )
        )
        return results

    async def _run_step(
        self, step: SceneAction, source: str
    ) -> dict[str, Any]:
        if step.delay_ms:
            await asyncio.sleep(step.delay_ms / 1000)

        action = DeviceAction(action=step.action, params=step.params)

        try:
            new_state = await self._registry.execute_action(
                step.device_id, action, source=source
            )
        except Exception as exc:
            if isinstance(exc, KeyError):
                logger.warning(
                    "scene action skipped: device=%s not registered (action=%s)",
                    step.device_id,
                    step.action,
                )
            else:
                logger.exception(
                    "scene action failed: device=%s action=%s",
                    step.device_id,
                    step.action,
                )
            # Best-effort error event so dashboards see the failure.
            try:
                await self._bus.publish(
                    Event(
                        type=EventType.DEVICE_ERROR,
                        source=source,
                        device_id=step.device_id,
                        data={"action": step.action, "error": str(exc)},
                    )
                )
            except Exception:  # pragma: no cover - defensive
                logger.exception("failed to publish DEVICE_ERROR")
            return {
                "device_id": step.device_id,
                "success": False,
                "state": None,
                "error": str(exc),
            }

        # Successful dispatch — registry has already published
        # DEVICE_STATE_CHANGED on our behalf, so we don't double-fire here.
        return {
            "device_id": step.device_id,
            "success": True,
            "state": new_state,
            "error": None,
        }


def _serialize_result(result: dict[str, Any]) -> dict[str, Any]:
    """Render a result dict into JSON-friendly primitives for the event payload."""

    state = result["state"]
    return {
        "device_id": result["device_id"],
        "success": result["success"],
        "state": state.model_dump(mode="json")
        if isinstance(state, DeviceState)
        else state,
        "error": result["error"],
    }
