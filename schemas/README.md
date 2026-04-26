# `schemas/` — shared data contracts

Every layer in Hestia (drivers, core, interfaces) imports from this package.
Adding or changing a type here is the only sanctioned way to evolve the
contract. Per the build plan, Phase 2 agents (Drivers, Core) and the Phase 3
API agent are allowed to extend these schemas if real implementation needs
demand it; the schema-ownership note in `home-auto-build-plan.md` formalizes
that.

All models inherit from Pydantic v2 `BaseModel` and are configured with
`from_attributes=True` so they can be built from ORM / dataclass-shaped
objects.

## Driver method calling convention

Driver methods (`get_info`, `get_state`, `execute`, `get_capabilities`) are
**async**. Schemas themselves are sync values; only the methods that *return*
schemas await. See `drivers/base.py` for the rationale (in short: matches
FastAPI / `aiosqlite` / `python-kasa`).

---

## `schemas/device.py`

### `DeviceType` (enum)

| Value | Meaning |
|-------|---------|
| `switch` | Binary smart switch (e.g. Kasa) |
| `relay` | GPIO-controlled relay |
| `media` | Media player (Spotify Connect) |
| `custom` | Anything else |

### `DeviceCapability` (enum)

| Value | UI hint |
|-------|---------|
| `toggle` | Render a switch |
| `dimmer` | Render a slider |
| `media_control` | Render play/pause/skip + volume |
| `custom` | Render nothing standard |

### `DeviceState`

Current runtime state.

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `power` | `bool` | required | On/off (or "is playing" for media) |
| `attributes` | `dict[str, Any]` | `{}` | Free-form per-device data |

```json
{"power": true, "attributes": {"volume": 80}}
```

### `DeviceInfo`

Full device record.

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `id` | `str` | required | Stable slug (URL path param) |
| `name` | `str` | required | Human-readable label |
| `device_type` | `DeviceType` | required | Coarse category |
| `driver_name` | `str` | required | Driver class name |
| `capabilities` | `list[DeviceCapability]` | required | UI controls |
| `state` | `DeviceState` | required | Current state |

```json
{
  "id": "kasa-living-room",
  "name": "Living room lights",
  "device_type": "switch",
  "driver_name": "KasaDriver",
  "capabilities": ["toggle"],
  "state": {"power": false, "attributes": {}}
}
```

### `DeviceAction`

Body of `POST /devices/{id}/action`.

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `action` | `StandardAction \| str` | required | Verb — see `StandardAction` below |
| `params` | `dict[str, Any] \| None` | `None` | Action-specific args |

```json
{"action": "set_brightness", "params": {"level": 50}}
```

On parse, known verbs are coerced into `StandardAction` enum members; unknown
strings pass through unchanged. JSON wire format is the lowercase string in
both cases — round-tripping is lossless.

### `StandardAction` (enum)

Common action verbs shared across drivers. The rule:

> **If a verb is reused across more than one driver, promote it to
> `StandardAction`.** Driver-specific verbs (used by exactly one driver) stay
> as plain strings.

| Value | Used by | Notes |
|-------|---------|-------|
| `turn_on` | Relay, Kasa | Power on |
| `turn_off` | Relay, Kasa | Power off |
| `toggle` | Relay, Kasa | Flip current power state |
| `set_brightness` | Kasa (dimmable bulbs) | `params.level` 0–100 |
| `play` | Spotify | Resume playback |
| `pause` | Spotify | Pause playback |
| `skip` | Spotify | Next track |
| `previous` | Spotify | Previous track |
| `set_volume` | Spotify | `params.level` 0–100 |

Driver-specific verbs (e.g. Spotify's `shuffle`) flow through as plain
strings without modification:

```python
from schemas import DeviceAction, StandardAction

# Known verb — becomes the enum
DeviceAction(action="turn_on").action          # StandardAction.TURN_ON

# Unknown verb — stays a string
DeviceAction(action="shuffle").action          # "shuffle"

# Passing the enum directly also works
DeviceAction(action=StandardAction.SET_VOLUME, params={"level": 70})
```

The wire format is identical for all three:

```json
{"action": "turn_on", "params": null}
{"action": "shuffle", "params": null}
{"action": "set_volume", "params": {"level": 70}}
```

---

## `schemas/scene.py`

### `SceneAction`

One step inside a `Scene`.

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `device_id` | `str` | required | Target device |
| `action` | `str` | required | Verb |
| `params` | `dict[str, Any] \| None` | `None` | Action args |
| `delay_ms` | `int \| None` | `None` | Delay (ms) inserted *before* this action |

### `Scene`

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `id` | `str` | required | Stable slug |
| `name` | `str` | required | Human label |
| `description` | `str \| None` | `None` | UI subtitle |
| `actions` | `list[SceneAction]` | `[]` | Ordered steps |

```json
{
  "id": "bedtime",
  "name": "Bedtime",
  "description": "All off, fan on",
  "actions": [
    {"device_id": "kasa-living-room", "action": "turn_off"},
    {"device_id": "kasa-kitchen", "action": "turn_off"},
    {"device_id": "relay-fan", "action": "turn_on"},
    {"device_id": "spotify", "action": "pause"}
  ]
}
```

---

## `schemas/schedule.py`

### `Schedule`

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `id` | `str` | required | Stable slug |
| `name` | `str` | required | Human label |
| `scene_id` | `str` | required | Scene to fire |
| `time` | `str` | required | `"HH:MM"` 24h (may upgrade to cron) |
| `days` | `list[str] \| None` | `None` | Weekday codes; `None` = every day |
| `enabled` | `bool` | `True` | Toggleable kill switch |

```json
{
  "id": "weekday-morning",
  "name": "Weekday morning",
  "scene_id": "morning",
  "time": "07:00",
  "days": ["mon", "tue", "wed", "thu", "fri"],
  "enabled": true
}
```

---

## `schemas/events.py`

### `EventType` (enum)

| Value | Trigger | Payload (`data`) |
|-------|---------|------------------|
| `device_state_changed` | A device's state was updated | `{"state": <DeviceState>}` (`device_id` set) |
| `scene_executed` | A scene finished | `{"scene_id": str, "results": [<DeviceState>, ...]}` |
| `schedule_triggered` | A schedule fired | `{"schedule_id": str, "scene_id": str}` |
| `device_registered` | A driver was registered | `{"info": <DeviceInfo>}` |
| `device_error` | A driver call failed | `{"action": str, "error": str}` (`device_id` set) |

### `Event`

| Field | Type | Default | Meaning |
|-------|------|---------|---------|
| `type` | `EventType` | required | Discriminator |
| `device_id` | `str \| None` | `None` | Target device, if any |
| `data` | `dict[str, Any]` | `{}` | Type-specific payload |
| `timestamp` | `datetime` | `datetime.now(timezone.utc)` | When the event was created (timezone-aware UTC) |
| `source` | `str` | required | Trigger origin (`"api"`, `"scheduler"`, `"voice"`, `"scene:bedtime"`, ...) |

```json
{
  "type": "device_state_changed",
  "device_id": "kasa-living-room",
  "data": {"state": {"power": true, "attributes": {}}},
  "timestamp": "2026-04-25T17:00:00Z",
  "source": "api"
}
```

---

## Importing

```python
from schemas import (
    DeviceAction,
    DeviceCapability,
    DeviceInfo,
    DeviceState,
    DeviceType,
    Event,
    EventType,
    Scene,
    SceneAction,
    Schedule,
)
```

Sub-module imports (`from schemas.device import DeviceState`) also work and
are equivalent.
