"""Scene-related schemas.

A *scene* is a named, ordered list of device actions executed together. Scenes
are stored in SQLite, exposed through the API, and triggered by interfaces or
by the scheduler — all paths funnel into the same ``execute_scene`` call.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SceneAction(BaseModel):
    """One step inside a :class:`Scene`.

    Fields:
        device_id: ID of the target device (matches :attr:`DeviceInfo.id`).
        action: Verb to execute on the device (matches
            :attr:`DeviceAction.action`).
        params: Optional dict of action-specific parameters.
        delay_ms: Optional delay (in milliseconds) inserted *before* this
            action runs. Lets you stagger multi-device sequences (e.g. bedroom
            lamp dims 5 seconds after the rest of the room turns off).

    Example:
        >>> SceneAction(device_id="relay-fan", action="turn_off",
        ...             delay_ms=5000).model_dump()
        {'device_id': 'relay-fan', 'action': 'turn_off', 'params': None, 'delay_ms': 5000}
    """

    device_id: str
    action: str
    params: dict[str, Any] | None = None
    delay_ms: int | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {"device_id": "kasa-living-room", "action": "turn_off"},
                {
                    "device_id": "spotify",
                    "action": "set_volume",
                    "params": {"level": 30},
                    "delay_ms": 2000,
                },
            ]
        },
    )


class Scene(BaseModel):
    """A named group of device actions.

    Fields:
        id: Stable slug, e.g. ``"bedtime"``. Used as the path parameter for
            ``/scenes/{id}/...`` endpoints.
        name: Human-readable label, e.g. ``"Bedtime"``.
        description: Optional one-line subtitle for the UI card.
        actions: Ordered list of :class:`SceneAction` to execute.
    """

    id: str
    name: str
    description: str | None = None
    actions: list[SceneAction] = Field(default_factory=list)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "bedtime",
                    "name": "Bedtime",
                    "description": "All off, fan on",
                    "actions": [
                        {"device_id": "kasa-living-room", "action": "turn_off"},
                        {"device_id": "kasa-kitchen", "action": "turn_off"},
                        {"device_id": "relay-fan", "action": "turn_on"},
                        {"device_id": "spotify", "action": "pause"},
                    ],
                }
            ]
        },
    )
