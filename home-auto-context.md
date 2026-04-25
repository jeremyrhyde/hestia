# Home automation system — architecture context

## Project goal

Build an extensible home automation system running on a Raspberry Pi that controls various devices (relay switches, Kasa smart plugs/switches, Spotify Connect) through multiple interfaces (touchscreen UI, voice commands, scheduler). The system must support adding new devices and new interfaces over time without modifying existing code.

## Hardware environment

All services run on a single Raspberry Pi sitting on a desk.

- **Kasa plugs/switches**: connected wirelessly to the Pi over WiFi, controlled via `python-kasa`
- **Relay switches**: wired directly to the Pi's GPIO pins, controlled via `gpiozero` or `RPi.GPIO`
- **Spotify Connect**: running locally on the Pi
- **Microphone + speaker**: attached to the Pi, used for voice control pipeline
- **Touchscreen**: 7-inch (or similar) display attached to the Pi (or a second Pi), running a fullscreen Chromium kiosk pointed at `localhost:8000`

Existing Python modules already exist for controlling the relay switches, Kasa devices, and Spotify. These modules will be wrapped by driver adapters — they are not rewritten.

## Core architectural principle

**Decoupling through a central API.** No interface ever talks directly to a device. No device driver ever knows which interface triggered a command. Everything meets in the middle at a FastAPI server with an async event bus.

The dependency rule: `core/` never imports from `drivers/` except through the registry. `drivers/` never imports from `core/`. Both import from `schemas/`. If these import boundaries hold, adding a new driver or a new interface requires zero changes to existing code.

## Architecture layers

### Layer 1: Interfaces (how commands enter the system)

All interfaces are API clients. They consume the Core API over HTTP/WebSocket and have no knowledge of device internals.

- **Touchscreen UI** (`web/index.html`): static single-page app served by FastAPI, runs in fullscreen Chromium on the Pi's touchscreen. Communicates via REST for commands and WebSocket for real-time state updates. This is a client, not a server-side component.
- **Voice control** (`interfaces/voice.py`): a server-side Python process running on the Pi. Chains wake-word detection → speech-to-text (Whisper, running locally) → intent parsing → API calls to `localhost:8000`. Runs as a separate process alongside the core server.
- **Future interfaces**: mobile app, CLI tool, IFTTT webhook, Home Assistant bridge — any HTTP client can join without backend changes.

### Layer 2: Core server (`core/`)

A FastAPI application that owns all orchestration logic. Contains:

- **API router** (`core/api.py`): REST endpoints for devices, scenes, schedules. WebSocket endpoint for real-time state push. This is the single entry point for all interfaces.
- **Event bus** (`core/events.py`): async pub/sub system. Components publish events (like `device_state_changed`) and subscribe to event types. This is the connective tissue that keeps everything in sync without tight coupling.
- **Scene engine** (`core/scenes.py`): executes multi-device action groups. A scene is a named list of device actions (e.g., "Bedtime" = turn off all lights, pause Spotify, keep fan on). Scenes can be triggered by any interface or by the scheduler.
- **Scheduler** (`core/scheduler.py`): an internal service, NOT an external cron job. Reads schedule definitions from SQLite, runs a timer loop, and publishes `schedule_triggered` events to the event bus when schedules fire. Because schedules are database rows exposed through the API, the frontend can display, create, edit, and toggle them with no special glue code.
- **State store** (`core/state.py`): SQLite database for persisting device states, scene definitions, and schedules. Also maintains an in-memory cache for fast reads. Subscribes to `device_state_changed` events to persist updates.
- **WebSocket manager** (`core/websocket.py`): maintains persistent connections to all frontends. Subscribes to `device_state_changed` events and pushes state updates to connected clients in real time.

### Layer 3: Device manager and drivers (`drivers/`)

- **Abstract base class** (`drivers/base.py`): defines the contract every driver must implement: `get_info()`, `get_state()`, `execute(action)`, `get_capabilities()`.
- **Driver registry** (`drivers/registry.py`): on startup, reads config and instantiates each driver. Maintains a `device_id → driver_instance` mapping. The device manager in `core/` dispatches through this registry.
- **Concrete drivers**: `kasa_driver.py`, `relay_driver.py`, `spotify_driver.py` — each wraps an existing Python module in the `DeviceDriver` interface. New drivers are added as new files with no changes to existing code.

### Layer 4: Shared vocabulary (`schemas/`)

Pydantic models that define the data contracts between all layers. Named `schemas/` (not `models/`) to avoid collision with Python's `types` module and to clearly communicate purpose: these are data shape definitions, not database ORM models or ML models.

## Key architectural decisions

### Scheduler lives inside the core, not as an external interface

The scheduler is a core service, not a cron job or separate process. This was a deliberate decision driven by the requirement to surface schedules in the touchscreen UI. Because the scheduler reads from the same SQLite database exposed by the REST API, the frontend can show a "Schedules" panel with toggle switches and editing — no separate integration needed. When a schedule fires, it publishes a `schedule_triggered` event to the bus, the scene engine picks it up, and execution follows the same path as any manual trigger.

### Scenes are the grouping abstraction

The "tap one button on my way to bed" use case requires a concept of named action groups. A scene called "Bedtime" bundles: Kasa living room off, Kasa kitchen off, relays off, Spotify pause. Scenes are stored in SQLite, exposed through the API, and can be triggered three ways: tap a scene card on the touchscreen, say "bedtime" as a voice command, or have the scheduler fire it at 11pm. All three call the same endpoint: `POST /scenes/{name}/execute`.

### Individual device control coexists with scenes

Scenes do not replace individual control — they sit on top of it. Every device has its own API endpoint (`POST /devices/{id}/action`). Scenes simply iterate through a list of those same individual actions. The system is stateless about intent: a device does not track why it is in a given state. If the scheduler fires "Bedtime" and turns everything off, a user can immediately tap a single device back on from the touchscreen. There is no conflict because the override is just another API call.

### The event bus is the connective tissue

The event bus decouples publishers from subscribers. The device manager publishes `device_state_changed` without knowing who listens. The WebSocket manager and state store subscribe to that event without knowing what triggered it. This means adding a new subscriber (e.g., a logging service, a notification system) requires zero changes to existing components.

Event flow for a typical command:
1. Interface sends `POST /scenes/bedtime/execute`
2. API router looks up scene, passes to scene engine
3. Scene engine iterates actions, calls `device_manager.execute_action()` for each
4. Device manager dispatches to the correct driver via the registry
5. Driver calls the underlying Python module (e.g., `python-kasa`)
6. On success, device manager publishes `device_state_changed` to event bus with `source="scene:bedtime"`
7. State store subscriber persists new state to SQLite
8. WebSocket manager subscriber pushes state to all connected frontends
9. Touchscreen receives WebSocket message, updates toggle states

The scheduler enters the same flow from a different door: timer fires → publishes `schedule_triggered` → scene engine subscribes and executes → same flow from step 3 onward.

## Folder structure

```
home-auto/
├── main.py                  # entry point, starts FastAPI + scheduler
├── config.py                # configuration loading
├── requirements.txt
│
├── core/                    # orchestration, never touches hardware
│   ├── api.py               # FastAPI routes + WebSocket endpoint
│   ├── websocket.py         # connection manager, broadcasts state
│   ├── events.py            # async pub/sub event bus
│   ├── scheduler.py         # timer loop, reads DB schedules
│   ├── scenes.py            # executes scene action lists
│   └── state.py             # SQLite read/write, state cache
│
├── schemas/                 # shared data contracts (Pydantic)
│   ├── device.py            # DeviceInfo, DeviceState, DeviceAction
│   ├── scene.py             # Scene, SceneAction
│   ├── schedule.py          # Schedule
│   └── events.py            # Event, EventType
│
├── drivers/                 # hardware-specific, never knows about HTTP
│   ├── base.py              # abstract DeviceDriver base class
│   ├── registry.py          # discovers + registers driver instances
│   ├── kasa_driver.py       # wraps existing Kasa Python module
│   ├── relay_driver.py      # wraps existing GPIO Python module
│   └── spotify_driver.py    # wraps existing Spotify Python module
│
├── interfaces/              # server-side API consumers on the Pi
│   └── voice.py             # wake word → STT → intent → API call
│
└── web/                     # static client assets served by FastAPI
    └── index.html           # touchscreen SPA
```

## Type system (schemas/)

### schemas/device.py

- `DeviceType` — enum: `SWITCH`, `RELAY`, `MEDIA`, `CUSTOM`
- `DeviceCapability` — enum: `TOGGLE`, `DIMMER`, `MEDIA_CONTROL`, `CUSTOM`. Tells the frontend what controls to render for each device.
- `DeviceState` — two fields: `power` (bool, on/off) and `attributes` (dict for device-specific data like Spotify's `track`, `volume`, `is_playing`)
- `DeviceInfo` — the full device record: `id` (string slug like `kasa-living-room`), `name` (human-readable), `device_type`, `driver_name`, `capabilities` (list), `state` (current `DeviceState`)
- `DeviceAction` — what the API receives: `action` (string like `turn_on`, `set_volume`) and `params` (optional dict)

### schemas/scene.py

- `SceneAction` — a single step: `device_id`, `action`, `params` (optional dict), `delay_ms` (optional, for sequencing — e.g., bedroom lamp goes off 5 seconds after everything else)
- `Scene` — the container: `id`, `name`, `description`, `actions` (ordered list of `SceneAction`)

### schemas/schedule.py

- `Schedule` — `id`, `name`, `scene_id` (which scene to fire), `time` (string like `"23:00"`, upgradable to cron expressions later), `days` (optional list like `["mon", "tue", "wed"]`), `enabled` (bool, so schedules can be toggled without deletion)

### schemas/events.py

- `EventType` — enum: `DEVICE_STATE_CHANGED`, `SCENE_EXECUTED`, `SCHEDULE_TRIGGERED`, `DEVICE_REGISTERED`, `DEVICE_ERROR`
- `Event` — `type` (EventType), `device_id` (optional), `data` (dict payload), `timestamp`, `source` (string identifying trigger origin: `"api"`, `"scheduler"`, `"voice"`, `"scene:bedtime"`)

## Driver base class contract (drivers/base.py)

Every driver implements the abstract `DeviceDriver` class:

- `get_info() → DeviceInfo` — returns the device's full metadata and current state
- `get_state() → DeviceState` — returns current state only
- `execute(action: DeviceAction) → DeviceState` — performs the action, returns the new state after execution
- `get_capabilities() → list[DeviceCapability]` — declares what the device can do, used by the frontend to render appropriate controls

Each concrete driver wraps an existing Python module. The driver author never imports from `core/`.

## API surface

### Device endpoints
- `GET /devices/` — list all registered devices with current state
- `GET /devices/{id}` — single device info and state
- `POST /devices/{id}/action` — execute an action on a single device. Body: `DeviceAction`

### Scene endpoints
- `GET /scenes/` — list all scenes
- `GET /scenes/{id}` — single scene definition
- `POST /scenes/{id}/execute` — trigger a scene
- `POST /scenes/` — create a new scene
- `PUT /scenes/{id}` — update a scene
- `DELETE /scenes/{id}` — delete a scene

### Schedule endpoints
- `GET /schedules/` — list all schedules
- `POST /schedules/` — create a schedule
- `PATCH /schedules/{id}` — update a schedule (including toggling `enabled`)
- `DELETE /schedules/{id}` — delete a schedule

### Real-time
- `WS /ws` — WebSocket endpoint. Server pushes `Event` objects whenever device state changes, regardless of trigger source.

## Touchscreen UI design

The touchscreen UI is a single-page dashboard split into two columns, designed for quick tap interactions with large touch targets and minimal scrolling.

**Left column — device panel.** A vertical list of every registered device. Each row shows the device name (e.g., "Living room lights"), a subtitle with the device type (e.g., "Kasa plug", "Relay"), and a toggle switch reflecting live state (green/right for on, gray/left for off). Tapping a toggle fires `POST /devices/{id}/action` and optimistically updates the UI. State stays in sync via the WebSocket connection — if a scene, schedule, or voice command changes a device, the toggle updates automatically.

**Right column, upper section — scenes panel.** A 2×N grid of large tappable cards. Each card shows a small icon, the scene name (e.g., "Bedtime", "Morning", "Movie", "Away"), and a one-line subtitle summarizing actions (e.g., "All off, fan on"). Tapping calls `POST /scenes/{name}/execute`. After execution, left-column toggles update via WebSocket to reflect new states. Scenes are fetched from `GET /scenes/` on load — adding a scene in the database automatically surfaces it.

**Right column, lower section — schedules panel.** A compact list of schedules showing trigger time (e.g., "11:00 PM"), scene name, and an on/off pill badge. Tapping the pill toggles `enabled` via `PATCH /schedules/{id}`. Provides at-a-glance visibility into automation without a separate settings page.

**Real-time sync.** The UI maintains a persistent WebSocket connection to `ws://localhost:8000/ws`. The server pushes state changes regardless of trigger source. If the 11pm Bedtime schedule fires while the user is looking at the screen, all toggles flip without any interaction. Initial state loads from `GET /devices/` on page load, then incremental updates via WebSocket.

**Design constraints.** Flat and minimal aesthetic. No gradients or shadows. Minimum 44px touch target height per row. Green for "on" states, neutral gray for "off." Assumes landscape orientation on a 7-inch Pi touchscreen but the two-column grid stacks to single-column on narrower displays.

## Technology choices

- **Core server**: FastAPI (async, WebSocket support, auto-generated docs, Python-native)
- **Database**: SQLite (no separate server process needed on the Pi)
- **Frontend**: static HTML/JS served by FastAPI, running in fullscreen Chromium kiosk
- **Voice STT**: Whisper running locally on the Pi
- **Wake word**: Porcupine or similar lightweight detector
- **Device libraries**: `python-kasa` for Kasa devices, `gpiozero`/`RPi.GPIO` for relays, existing Spotify module

## Summary of dependency flow

```
interfaces/ & web/  →  (HTTP/WS)  →  core/api.py
                                        ↓
                               core/scenes.py
                               core/scheduler.py
                                        ↓
                               drivers/registry.py  →  drivers/*_driver.py
                                        ↓
                               core/events.py (pub/sub)
                                        ↓
                               core/websocket.py  →  (WS)  →  frontends
                               core/state.py      →  SQLite

All layers import from: schemas/
No layer imports across boundaries except through schemas/ and the driver registry.
```
