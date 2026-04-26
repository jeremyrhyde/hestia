"""Shared Pydantic schemas — the data contracts between every layer.

Re-exports the public types so callers can write::

    from schemas import DeviceInfo, DeviceState, Scene, Event
"""

from schemas.config import DeviceConfig, DevicesConfig
from schemas.device import (
    DeviceAction,
    DeviceCapability,
    DeviceInfo,
    DeviceState,
    DeviceType,
    StandardAction,
)
from schemas.events import Event, EventType
from schemas.scene import Scene, SceneAction
from schemas.schedule import Schedule

__all__ = [
    "DeviceAction",
    "DeviceCapability",
    "DeviceConfig",
    "DeviceInfo",
    "DeviceState",
    "DeviceType",
    "DevicesConfig",
    "Event",
    "EventType",
    "Scene",
    "SceneAction",
    "Schedule",
    "StandardAction",
]
