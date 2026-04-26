"""Event schemas for the in-process pub/sub bus.

Events are how decoupled components talk: the device manager publishes
``DEVICE_STATE_CHANGED`` without caring who listens; the WebSocket manager
and state store subscribe without caring what triggered the event.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    """Discriminator for events on the bus.

    Values:
        DEVICE_STATE_CHANGED: A device's state was updated (by any source).
            Payload: ``{"state": <DeviceState dict>}``, ``device_id`` set.
        SCENE_EXECUTED: A scene finished executing.
            Payload: ``{"scene_id": str, "results": [<DeviceState>, ...]}``.
        SCHEDULE_TRIGGERED: A schedule's time matched and it fired.
            Payload: ``{"schedule_id": str, "scene_id": str}``.
        DEVICE_REGISTERED: A new driver was registered with the registry.
            Payload: ``{"info": <DeviceInfo dict>}``.
        DEVICE_ERROR: A driver call failed.
            Payload: ``{"action": str, "error": str}``.
    """

    DEVICE_STATE_CHANGED = "device_state_changed"
    SCENE_EXECUTED = "scene_executed"
    SCHEDULE_TRIGGERED = "schedule_triggered"
    DEVICE_REGISTERED = "device_registered"
    DEVICE_ERROR = "device_error"


class Event(BaseModel):
    """An event published on the bus.

    Fields:
        type: Discriminator, see :class:`EventType`.
        device_id: ID of the device the event refers to, if any. Required for
            DEVICE_STATE_CHANGED and DEVICE_ERROR; optional otherwise.
        data: Payload dict; see :class:`EventType` for per-type contents.
        timestamp: When the event was created. Defaults to the current UTC
            time as a timezone-aware ``datetime`` at instantiation.
        source: Free-form string identifying the trigger origin
            (e.g. ``"api"``, ``"scheduler"``, ``"voice"``, ``"scene:bedtime"``).
            Used for diagnostics and to disambiguate cascading effects.
    """

    type: EventType
    device_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    source: str

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "type": "device_state_changed",
                    "device_id": "kasa-living-room",
                    "data": {"state": {"power": True, "attributes": {}}},
                    "timestamp": "2026-04-25T17:00:00Z",
                    "source": "api",
                },
                {
                    "type": "scene_executed",
                    "device_id": None,
                    "data": {
                        "scene_id": "bedtime",
                        "results": [{"power": False, "attributes": {}}],
                    },
                    "timestamp": "2026-04-25T23:00:00Z",
                    "source": "scheduler",
                },
            ]
        },
    )
