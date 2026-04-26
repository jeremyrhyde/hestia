"""Device-related Pydantic schemas.

These types are the shared vocabulary between drivers, the core API, and
interfaces. They describe what a device is (`DeviceInfo`), what it can do
(`DeviceCapability`), what state it's currently in (`DeviceState`), and what
the API receives when a caller wants to act on a device (`DeviceAction`).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DeviceType(str, Enum):
    """Coarse categorization used by the frontend for grouping/filtering.

    Values:
        SWITCH: A binary switch (e.g. a Kasa smart switch).
        RELAY: A GPIO-controlled relay wired to the Pi.
        MEDIA: A media player (e.g. Spotify Connect).
        CUSTOM: Anything that does not fit the above buckets.
    """

    SWITCH = "switch"
    RELAY = "relay"
    MEDIA = "media"
    CUSTOM = "custom"


class DeviceCapability(str, Enum):
    """Declares what a device can do.

    The frontend uses this to decide which controls to render — a TOGGLE-only
    device gets a switch, a DIMMER device gets a slider, a MEDIA_CONTROL device
    gets play/pause/skip buttons.

    Values:
        TOGGLE: Device can be turned on/off.
        DIMMER: Device supports a brightness/level setting.
        MEDIA_CONTROL: Device supports play/pause/skip/volume.
        CUSTOM: Device exposes capabilities outside the standard set.
    """

    TOGGLE = "toggle"
    DIMMER = "dimmer"
    MEDIA_CONTROL = "media_control"
    CUSTOM = "custom"


class StandardAction(str, Enum):
    """Common action verbs shared across drivers.

    Drivers SHOULD use these for standard operations so the API surface stays
    consistent. Drivers MAY accept additional verb strings for device-specific
    operations (e.g. ``"shuffle"`` on Spotify) — :attr:`DeviceAction.action`
    is typed as ``StandardAction | str`` to allow both. If a verb is reused
    across more than one driver, promote it to :class:`StandardAction`.

    Values:
        TURN_ON / TURN_OFF / TOGGLE: power control (relays, Kasa).
        SET_BRIGHTNESS: dimmer control (Kasa bulbs); requires ``params.level``.
        PLAY / PAUSE / SKIP / PREVIOUS: media transport (Spotify).
        SET_VOLUME: media volume; requires ``params.level`` (0-100).
    """

    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    TOGGLE = "toggle"
    SET_BRIGHTNESS = "set_brightness"
    PLAY = "play"
    PAUSE = "pause"
    SKIP = "skip"
    PREVIOUS = "previous"
    SET_VOLUME = "set_volume"


class DeviceState(BaseModel):
    """Current runtime state of a device.

    Fields:
        power: True if the device is on / playing, False otherwise.
        attributes: Free-form bag for device-specific data
            (e.g. ``{"track": "...", "volume": 80, "is_playing": True}``).

    Example:
        >>> DeviceState(power=True, attributes={"volume": 80}).model_dump()
        {'power': True, 'attributes': {'volume': 80}}
    """

    power: bool
    attributes: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {"power": True, "attributes": {}},
                {
                    "power": True,
                    "attributes": {
                        "track": "Heart of the Sunrise",
                        "artist": "Yes",
                        "volume": 80,
                        "is_playing": True,
                    },
                },
            ]
        },
    )


class DeviceInfo(BaseModel):
    """Full device record returned by drivers and the device API.

    Fields:
        id: Stable string slug for the device, e.g. ``"kasa-living-room"``.
            Used as the path parameter for ``/devices/{id}/...`` endpoints.
        name: Human-readable label rendered in the UI.
        device_type: Coarse category (see :class:`DeviceType`).
        driver_name: Name of the driver class implementing the device, useful
            for diagnostics (e.g. ``"KasaDriver"``).
        capabilities: List of declared capabilities; tells the frontend what
            controls to render.
        state: Current :class:`DeviceState`.
    """

    id: str
    name: str
    device_type: DeviceType
    driver_name: str
    capabilities: list[DeviceCapability]
    state: DeviceState

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "kasa-living-room",
                    "name": "Living room lights",
                    "device_type": "switch",
                    "driver_name": "KasaDriver",
                    "capabilities": ["toggle"],
                    "state": {"power": False, "attributes": {}},
                }
            ]
        },
    )


class DeviceAction(BaseModel):
    """Command payload received by ``POST /devices/{id}/action``.

    Fields:
        action: Verb identifying the operation. Typed as
            ``StandardAction | str`` — known verbs are coerced into the
            :class:`StandardAction` enum on parse (e.g. ``"turn_on"`` becomes
            ``StandardAction.TURN_ON``), while arbitrary strings pass through
            unchanged so drivers can accept device-specific verbs (e.g.
            ``"shuffle"`` on Spotify). The wire format is the lowercase string
            in both cases — JSON does not distinguish.
        params: Optional dict of action-specific parameters
            (e.g. ``{"level": 50}`` for ``"set_brightness"``).

    Example:
        >>> DeviceAction(action="turn_on").action
        <StandardAction.TURN_ON: 'turn_on'>
        >>> DeviceAction(action="shuffle").action
        'shuffle'
        >>> DeviceAction(action="set_volume", params={"level": 70}).model_dump_json()
        '{"action":"set_volume","params":{"level":70}}'
    """

    # `union_mode="left_to_right"` makes Pydantic try `StandardAction` first
    # (so ``"turn_on"`` becomes ``StandardAction.TURN_ON``); only unknown verbs
    # fall through to plain ``str``. Default smart-union mode would otherwise
    # leave known verbs as bare strings.
    action: StandardAction | str = Field(union_mode="left_to_right")
    params: dict[str, Any] | None = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {"action": "turn_on"},
                {"action": "set_brightness", "params": {"level": 50}},
                {"action": "set_volume", "params": {"level": 70}},
            ]
        },
    )
