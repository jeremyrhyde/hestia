# Home automation — agentic build plan

## How to use this document

This plan is for a team of AI coding agents building a home automation system on a Raspberry Pi. Each phase has a clear entry condition, tasks assigned to a specific agent, and a checkpoint with testable deliverables. The human operator checks in at each checkpoint to verify the deliverable before green-lighting the next phase.

Every phase produces a README in its directory documenting what was built, how to test it, and what the next agent needs to know to build on it.

This document should be read alongside `home-auto-context.md`, which contains the full architectural specification: project goals, hardware environment, folder structure, type system, API surface, UI design, and all architectural decisions with rationale.

---

## Agent roster

| Agent | Name | Scope | Owns |
|-------|------|-------|------|
| **F** | Foundation | Project scaffolding, schemas, abstract base class, config | `schemas/`, `drivers/base.py`, `drivers/registry.py`, `config.py`, root `README.md` |
| **D** | Drivers | Device driver wrapper implementations | `drivers/kasa_driver.py`, `drivers/relay_driver.py`, `drivers/spotify_driver.py` |
| **C** | Core | Internal services: event bus, state store, scene engine, scheduler | `core/events.py`, `core/state.py`, `core/scenes.py`, `core/scheduler.py` |
| **A** | API | FastAPI routes, WebSocket manager, application entry point | `core/api.py`, `core/websocket.py`, `main.py` |
| **I** | Interfaces | Touchscreen UI (first), then voice pipeline (second) | `web/`, `interfaces/voice.py` |

---

## Dependency graph

```
Phase 1:   [F: Foundation + scaffolding]
                    |
            ┌───────┴───────┐
Phase 2:    [D: Drivers]    [C: Core services]
            └───────┬───────┘
                    |
Phase 3:   [A: API + WebSocket]
                    |
Phase 4a:  [I: Touchscreen UI]
                    |  ← checkpoint + integration test
Phase 4b:  [I: Voice pipeline]
                    |  ← checkpoint + integration test
Phase 5:   [Full system integration]
```

Phases 2D and 2C run in parallel. All other phases are sequential. Agent I works on UI first, pauses for integration testing, then builds voice.

---

## Schema ownership and evolution

`schemas/` is the shared vocabulary that every agent imports from. Agent F creates the initial definitions. During Phase 2, both Agent D and Agent C may discover that a schema needs adjustment (a missing field, a type that should be optional, a new enum value). Either agent may modify schemas as needed — the types should evolve to match real implementation needs. Agent A should verify schema consistency across all modules when wiring the layers together in Phase 3.

---

## Phase 1 — Foundation

**Agent**: F
**Dependencies**: none
**Entry condition**: `home-auto-context.md` has been read and understood
**Delivers**: project skeleton, all schemas, driver base class, config, project README

### Tasks

#### 1.1 — Repository and environment setup

- Initialize the project directory structure matching the folder layout in `home-auto-context.md`
- Create `.gitignore` for Python (include `__pycache__/`, `*.db`, `.env`, `venv/`, `*.pyc`)
- Create `requirements.txt` with initial dependencies: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `aiosqlite`, `python-kasa`, `gpiozero`, `websockets`
- Create all `__init__.py` files for packages: `core/`, `schemas/`, `drivers/`, `interfaces/`
- Create `config.py` with a Pydantic `Settings` class that loads from environment or `.env` file
  - Fields: `HOST` (default `0.0.0.0`), `PORT` (default `8000`), `DB_PATH` (default `./home-auto.db`), `LOG_LEVEL` (default `info`), `WEB_DIR` (default `./web`)

#### 1.2 — Schema definitions

Implement all Pydantic models as specified in `home-auto-context.md`:

- `schemas/device.py` — `DeviceType` enum, `DeviceCapability` enum, `DeviceState`, `DeviceInfo`, `DeviceAction`
- `schemas/scene.py` — `SceneAction`, `Scene`
- `schemas/schedule.py` — `Schedule`
- `schemas/events.py` — `EventType` enum, `Event`

Each model must include docstrings explaining the fields. Include `model_config` with `from_attributes = True` for ORM compatibility. Add example values in docstrings or as class-level examples so downstream agents can see the intended shape.

#### 1.3 — Driver base class and registry

- `drivers/base.py` — abstract `DeviceDriver` class using `abc.ABC` with abstract methods: `get_info() → DeviceInfo`, `get_state() → DeviceState`, `execute(action: DeviceAction) → DeviceState`, `get_capabilities() → list[DeviceCapability]`
- `drivers/registry.py` — `DriverRegistry` class that maintains a `dict[str, DeviceDriver]` mapping device IDs to driver instances. Methods: `register(device_id, driver)`, `get(device_id) → DeviceDriver`, `list_devices() → list[DeviceInfo]`, `execute_action(device_id, action) → DeviceState`

#### 1.4 — Test file

Create `tests/test_schemas.py` that verifies all schema classes can be instantiated with sample data, serialized to JSON, and deserialized back. Verify that `DeviceDriver` cannot be instantiated directly (raises `TypeError`). Verify the registry can register, retrieve, and list mock drivers.

#### 1.5 — READMEs

- Root `README.md` — project overview (2-3 sentences), folder structure with one-line descriptions, how to install dependencies, how to run tests
- `schemas/README.md` — documents every type with field descriptions and example JSON payloads. This is the reference document for all downstream agents.

### Checkpoint 1 — Foundation gate

| Test | How to verify | Pass condition |
|------|---------------|----------------|
| Schema imports | `python -c "from schemas.device import DeviceInfo, DeviceState, DeviceAction, DeviceType, DeviceCapability"` | No errors |
| Schema instantiation | `python -c "from schemas.device import *; d = DeviceState(power=True, attributes={'volume': 80}); print(d.model_dump_json())"` | Prints valid JSON |
| Base class guard | `python -c "from drivers.base import DeviceDriver; DeviceDriver()"` | Raises `TypeError` |
| Registry works | Run `tests/test_schemas.py` | All tests pass |
| Config loads | Create `.env` with `PORT=9000`, run `python -c "from config import Settings; s = Settings(); assert s.PORT == 9000"` | No errors |
| Folder structure | `find . -name '*.py' \| head -20` | Matches architecture spec |
| READMEs exist | `cat README.md && cat schemas/README.md` | Both present with content |

**Human check-in**: review the schema definitions for completeness, scan the READMEs, run the test suite. If schemas look right, green-light Phases 2D and 2C to begin in parallel.

---

## Phase 2D — Drivers

**Agent**: D
**Dependencies**: Phase 1 complete
**Entry condition**: all schemas importable, `DeviceDriver` base class and `DriverRegistry` exist
**Delivers**: three working driver files, test scripts, drivers README

### Tasks

#### 2D.1 — Relay driver

- `drivers/relay_driver.py` — wraps the existing relay GPIO Python module
- Constructor takes pin number(s) and device ID/name from config
- `get_state()` reads actual GPIO pin state
- `execute()` handles actions: `turn_on`, `turn_off`, `toggle`
- `get_capabilities()` returns `[DeviceCapability.TOGGLE]`
- Fails gracefully if GPIO is unavailable (e.g., not running on Pi) — logs a warning, returns a mock state

#### 2D.2 — Kasa driver

- `drivers/kasa_driver.py` — wraps the existing Kasa Python module (using `python-kasa`)
- Constructor takes device IP or hostname from config
- `get_state()` queries the actual plug/switch state over WiFi
- `execute()` handles actions: `turn_on`, `turn_off`, `toggle`. If the Kasa device supports dimming, also handle `set_brightness` with a `level` param
- `get_capabilities()` returns `[DeviceCapability.TOGGLE]` (or includes `DIMMER` if supported)
- Handles network timeouts gracefully — returns last known state and logs error

#### 2D.3 — Spotify driver

- `drivers/spotify_driver.py` — wraps the existing Spotify Connect Python module
- `get_state()` returns `DeviceState` with `power` (is playing) and `attributes` containing `track`, `artist`, `volume`, `is_playing`
- `execute()` handles actions: `play`, `pause`, `skip`, `previous`, `set_volume` (with `level` param)
- `get_capabilities()` returns `[DeviceCapability.MEDIA_CONTROL]`

#### 2D.4 — Test scripts

Create standalone test scripts that can run on the Pi against real hardware:

- `tests/test_relay_driver.py` — instantiates relay driver, toggles on, verifies state, toggles off, verifies state. Should produce an audible click if relay is connected.
- `tests/test_kasa_driver.py` — instantiates Kasa driver with a real device IP, toggles on/off, verifies state change. The physical plug/switch should visibly toggle.
- `tests/test_spotify_driver.py` — instantiates Spotify driver, calls play/pause, reads state, verifies attributes are populated.

Each test script should also work with mock data when hardware is unavailable, using a `--mock` flag.

#### 2D.5 — README

`drivers/README.md` with three sections:

- **What this does** — one paragraph explaining the driver layer
- **How to test** — exact commands for each driver test, what physical behavior to look for
- **How to add a new driver** — step-by-step guide: create a new file, extend `DeviceDriver`, implement the four methods, register in config. Include a minimal driver template.

### Checkpoint 2D — Drivers gate

| Test | How to verify | Pass condition |
|------|---------------|----------------|
| Relay real-world | Run `tests/test_relay_driver.py` on Pi with relay connected | Relay clicks on and off, state reports correctly |
| Kasa real-world | Run `tests/test_kasa_driver.py` on Pi with Kasa device on network | Plug/switch toggles visibly, state reports correctly |
| Spotify real-world | Run `tests/test_spotify_driver.py` on Pi with Spotify Connect running | Music plays and pauses, track info returned in state |
| Mock fallback | Run each test with `--mock` flag on any machine | All pass without hardware |
| Type compliance | Each driver's `get_info()` returns a valid `DeviceInfo` that passes Pydantic validation | No validation errors |
| README | `cat drivers/README.md` | Contains test commands and new-driver template |

**Human check-in**: run each driver test on the Pi with real devices. Verify physical device responds. Check that state objects returned by each driver are well-formed and contain meaningful data (not placeholder strings).

---

## Phase 2C — Core services

**Agent**: C
**Dependencies**: Phase 1 complete
**Entry condition**: all schemas importable
**Delivers**: four core service modules, test suite, core README

### Tasks

These must be built in order — each depends on the one before it.

#### 2C.1 — Event bus (`core/events.py`)

- Async pub/sub system using `asyncio`
- `EventBus` class with methods: `subscribe(event_type: EventType, callback: Callable)`, `publish(event: Event)`, `unsubscribe(event_type, callback)`
- Callbacks are async functions that receive an `Event` object
- Multiple subscribers per event type
- Publishing is fire-and-forget — one subscriber's failure does not block others (catch and log exceptions)
- Singleton pattern or dependency injection — downstream agents need to get the same bus instance

#### 2C.2 — State store (`core/state.py`)

- Async SQLite interface using `aiosqlite`
- Database tables: `devices` (stores latest `DeviceInfo` JSON), `scenes` (stores `Scene` JSON), `schedules` (stores `Schedule` JSON), `event_log` (append-only log of `Event` JSON with timestamp)
- `StateStore` class with async methods for CRUD on each table: `get_device(id)`, `upsert_device(info)`, `list_devices()`, `get_scene(id)`, `upsert_scene(scene)`, `list_scenes()`, `delete_scene(id)`, `get_schedule(id)`, `upsert_schedule(schedule)`, `list_schedules()`, `delete_schedule(id)`, `log_event(event)`
- On initialization, creates tables if they don't exist
- Subscribes to `DEVICE_STATE_CHANGED` on the event bus and persists the new state automatically

#### 2C.3 — Scene engine (`core/scenes.py`)

- `SceneEngine` class that takes a reference to the `DriverRegistry` and `EventBus`
- `execute_scene(scene: Scene) → list[DeviceState]` — iterates through scene actions in order, calls `registry.execute_action()` for each, respects `delay_ms` between actions, returns the list of resulting states
- After all actions complete, publishes a `SCENE_EXECUTED` event to the bus
- Error handling: if one device action fails, log it and continue to the next action (don't abort the whole scene). Include the error in the returned results.

#### 2C.4 — Scheduler (`core/scheduler.py`)

- `Scheduler` class that takes a reference to `StateStore`, `SceneEngine`, and `EventBus`
- On start, loads all enabled schedules from the state store
- Runs an async loop that checks every 30 seconds whether any schedule's time matches the current time (and day of week if specified)
- When a schedule fires: publishes `SCHEDULE_TRIGGERED` event, then calls `scene_engine.execute_scene()` with the referenced scene
- Reloads schedules from the database periodically (or exposes a `reload()` method the API can call after schedule CRUD operations)
- Prevents duplicate firing — tracks which schedules have fired today

#### 2C.5 — Test suite

`tests/test_core.py` covering:

- **Event bus**: subscribe to an event type, publish an event, verify the subscriber callback was invoked with the correct data. Test multiple subscribers. Test that a failing subscriber doesn't block others.
- **State store**: create database, write a device state, read it back, update it, verify persistence. Same for scenes and schedules. Test that the event bus subscription auto-persists state changes.
- **Scene engine**: define a scene with three actions and a mock registry. Execute it. Verify all three actions fired in order. Verify `SCENE_EXECUTED` event was published. Test partial failure (one action fails, others still execute).
- **Scheduler**: create a schedule set to fire 2 seconds from now. Start the scheduler loop. Wait 5 seconds. Verify `SCHEDULE_TRIGGERED` was published and the scene was executed. Test that disabled schedules don't fire.

#### 2C.6 — Integration micro-test

`tests/test_core_integration.py` — a small script that wires event bus + state store + scene engine together (without drivers — uses a mock registry). Creates a scene, executes it, and verifies that device states were persisted to SQLite and events were logged. This validates the internal wiring before the API layer exists.

#### 2C.7 — README

`core/README.md` with:

- **What this does** — overview of the four services and how they connect
- **Event types** — table of all `EventType` values, what triggers each, and what data to expect in the payload
- **How to test** — exact commands to run the test suite and the integration micro-test
- **How to use in your code** — import examples, initialization order, how to subscribe to events

### Checkpoint 2C — Core services gate

| Test | How to verify | Pass condition |
|------|---------------|----------------|
| Event bus | `pytest tests/test_core.py -k event_bus` | Pub/sub works, multiple subscribers, failure isolation |
| State store | `pytest tests/test_core.py -k state_store` | CRUD works for all tables, auto-persist on event |
| Scene engine | `pytest tests/test_core.py -k scene_engine` | Actions fire in order, delays respected, partial failure handled |
| Scheduler | `pytest tests/test_core.py -k scheduler` | Schedule fires on time, disabled schedules skip, no duplicate firing |
| Integration wiring | `python tests/test_core_integration.py` | Scene executes → state persisted → event logged in SQLite |
| README | `cat core/README.md` | Event types table, usage examples present |

**Human check-in**: run the full test suite. Check the SQLite database after the integration test to verify data looks correct (`sqlite3 home-auto.db "SELECT * FROM devices;"`). Review the event types table in the README.

---

## Phase 3 — API and WebSocket

**Agent**: A
**Dependencies**: Phases 2D and 2C both complete
**Entry condition**: all drivers work, all core services pass tests
**Delivers**: FastAPI application, WebSocket manager, `main.py` entry point, curl test commands

### Tasks

#### 3.1 — WebSocket manager (`core/websocket.py`)

- `WebSocketManager` class that maintains a set of active WebSocket connections
- `connect(websocket)` — accepts and stores a connection
- `disconnect(websocket)` — removes a connection
- `broadcast(event: Event)` — sends serialized event JSON to all connected clients
- Subscribes to `DEVICE_STATE_CHANGED` and `SCENE_EXECUTED` on the event bus, broadcasts each to all connected frontends
- Handles individual connection failures gracefully (drop the dead connection, don't crash)

#### 3.2 — API routes (`core/api.py`)

Implement all endpoints specified in `home-auto-context.md`:

**Device endpoints:**
- `GET /devices/` — calls `registry.list_devices()`, returns list of `DeviceInfo`
- `GET /devices/{id}` — calls `registry.get(id).get_info()`, returns `DeviceInfo`. 404 if not found.
- `POST /devices/{id}/action` — accepts `DeviceAction` body, calls `registry.execute_action(id, action)`, publishes `DEVICE_STATE_CHANGED` event, returns new `DeviceState`

**Scene endpoints:**
- `GET /scenes/` — reads from state store
- `GET /scenes/{id}` — reads from state store, 404 if not found
- `POST /scenes/` — validates `Scene` body, writes to state store, returns created scene
- `PUT /scenes/{id}` — updates scene in state store
- `DELETE /scenes/{id}` — deletes from state store
- `POST /scenes/{id}/execute` — reads scene from store, passes to scene engine, returns list of resulting device states

**Schedule endpoints:**
- `GET /schedules/` — reads from state store
- `POST /schedules/` — validates `Schedule` body, writes to state store, calls `scheduler.reload()`
- `PATCH /schedules/{id}` — partial update (primarily for toggling `enabled`), calls `scheduler.reload()`
- `DELETE /schedules/{id}` — deletes from state store, calls `scheduler.reload()`

**WebSocket endpoint:**
- `WS /ws` — accepts WebSocket upgrade, registers with the manager, keeps connection alive, removes on disconnect

**Static file serving:**
- Serve contents of `web/` directory at the root path for the frontend

#### 3.3 — Application entry point (`main.py`)

- Creates and wires all components: config → state store → event bus → driver registry (loads drivers from config) → scene engine → scheduler → WebSocket manager → FastAPI app
- Starts the scheduler loop as a background task on FastAPI startup
- Starts uvicorn with host/port from config
- Graceful shutdown: stops scheduler, closes database, disconnects WebSocket clients

#### 3.4 — API test script

`tests/test_api.py` — uses `httpx` or FastAPI's `TestClient`:

- Test each REST endpoint with valid data and verify response shapes
- Test error cases: 404 for missing device, 422 for invalid action body
- Test WebSocket: connect, trigger a device action via REST, verify the WebSocket receives the state change event

#### 3.5 — Manual test commands

`tests/api_curl_tests.sh` — a shell script with annotated curl commands for every endpoint:

```bash
# List all devices
curl http://localhost:8000/devices/

# Toggle a specific device
curl -X POST http://localhost:8000/devices/kasa-living-room/action \
  -H "Content-Type: application/json" \
  -d '{"action": "turn_off"}'

# Execute a scene
curl -X POST http://localhost:8000/scenes/bedtime/execute
```

Include a small Python WebSocket test client in `tests/ws_test_client.py` that connects, prints all received events, and stays alive so the human can trigger actions and watch events flow.

#### 3.6 — README

`core/api_README.md` with:

- **Endpoints** — table of all routes with method, path, request body, and response shape
- **How to start the server** — exact command (`python main.py` or `uvicorn main:app`)
- **How to test with curl** — reference to `tests/api_curl_tests.sh`
- **How to test WebSocket** — reference to `tests/ws_test_client.py`
- **Startup sequence** — documents the initialization order of components so future maintainers understand what depends on what

### Checkpoint 3 — API gate

| Test | How to verify | Pass condition |
|------|---------------|----------------|
| Server starts | `python main.py` | No errors, logs show all drivers registered |
| Device list | `curl http://localhost:8000/devices/` | Returns JSON array of all registered devices with current states |
| Device action (real-world) | `curl -X POST .../devices/relay-desk/action -d '{"action":"toggle"}'` on Pi | Relay clicks, response shows new state |
| Scene execute (real-world) | Create a test scene via `POST /scenes/`, then `POST /scenes/test/execute` | Multiple devices change state, all reflected in response |
| Schedule CRUD | Create, list, patch (toggle enabled), delete a schedule via curl | Correct responses at each step |
| WebSocket sync | Run `python tests/ws_test_client.py` in one terminal, curl a device toggle in another | WebSocket client prints the `DEVICE_STATE_CHANGED` event |
| Scheduler fires (real-world) | Create a schedule 1 minute from now, wait, watch the WebSocket client | Scene fires, WebSocket client shows state changes, physical devices respond |
| Error handling | `curl .../devices/nonexistent/action` | Returns 404, not 500 |
| Auto-docs | Open `http://localhost:8000/docs` in browser | Swagger UI shows all endpoints |
| README | `cat core/api_README.md` | Endpoint table, startup command, curl examples |

**Human check-in**: this is the most important gate. Start the server on the Pi with real devices connected. Run through the curl test script. Open the WebSocket test client and verify events flow. Create a schedule, watch it fire, see physical devices respond. This is the "headless end-to-end" moment — if this works, the rest is interface building.

---

## Phase 4a — Touchscreen UI

**Agent**: I
**Dependencies**: Phase 3 complete
**Entry condition**: API is running and responding, WebSocket is pushing events
**Delivers**: static frontend in `web/`, kiosk setup docs

### Tasks

#### 4a.1 — Page structure and layout

- `web/index.html` — single-page app, no build tools (vanilla HTML/CSS/JS or a lightweight framework loaded via CDN)
- Two-column responsive layout as specified in `home-auto-context.md` UI design section
- Left column: device panel (vertical list of device rows with toggles)
- Right column: scenes panel (2×N card grid) and schedules panel (compact list with toggle pills)

#### 4a.2 — Device panel

- On page load, fetch `GET /devices/` and render a row per device
- Each row shows: device name, device type subtitle, toggle switch reflecting `state.power`
- Tapping a toggle sends `POST /devices/{id}/action` with `{"action": "toggle"}`
- Optimistic UI update: toggle flips immediately, reverts if the API call fails
- Devices with `MEDIA_CONTROL` capability get a different row style showing play/pause and track info from `state.attributes`

#### 4a.3 — Scenes panel

- Fetch `GET /scenes/` and render scene cards in a grid
- Each card shows scene name and a one-line description
- Tapping a card sends `POST /scenes/{id}/execute`
- Visual feedback on tap: brief highlight or scale animation

#### 4a.4 — Schedules panel

- Fetch `GET /schedules/` and render rows
- Each row shows time, scene name, and an on/off pill badge
- Tapping the pill sends `PATCH /schedules/{id}` with `{"enabled": !current}`
- Pill color updates to reflect new state

#### 4a.5 — WebSocket real-time sync

- On page load, open a WebSocket connection to `ws://localhost:8000/ws`
- On receiving a `DEVICE_STATE_CHANGED` event, find the matching device row and update its toggle state
- On receiving a `SCENE_EXECUTED` event, briefly highlight the scene card that was triggered
- Reconnection logic: if the WebSocket drops, retry every 3 seconds with exponential backoff

#### 4a.6 — Kiosk mode setup

Document the Chromium kiosk configuration for the Pi's touchscreen:
- Autostart Chromium in fullscreen pointed at `http://localhost:8000`
- Disable screensaver, cursor hiding, power management
- Include a systemd service file or autostart script

#### 4a.7 — README

`web/README.md` with:

- **What this does** — overview of the touchscreen UI
- **How to test during development** — open `http://<pi-ip>:8000` in any browser
- **Kiosk mode setup** — step-by-step instructions for Pi touchscreen autostart
- **How the UI communicates** — summary of API endpoints and WebSocket events used

### Checkpoint 4a — Touchscreen UI gate

| Test | How to verify | Pass condition |
|------|---------------|----------------|
| Page loads | Open `http://localhost:8000` in browser | Two-column layout renders, devices listed, scenes shown |
| Device toggle (real-world) | Tap a device toggle on the touchscreen | Physical device responds, toggle reflects new state |
| Scene execution (real-world) | Tap "Bedtime" scene card | All target devices turn off, all toggles in device panel update |
| Schedule toggle | Tap a schedule pill from on to off | Pill changes to off state, schedule no longer fires |
| WebSocket sync — cross-tab | Open two browser tabs, toggle a device in one | Other tab updates automatically |
| WebSocket sync — external trigger | Toggle a device via curl while watching the UI | UI updates without any touch interaction |
| WebSocket sync — scheduler | Create a schedule 1 minute from now, watch the UI | Devices toggle on screen when schedule fires |
| Override after scene | Execute Bedtime scene, then tap one device back on | Override works, device stays on, no conflict |
| Reconnection | Stop and restart the server while the UI is open | UI reconnects and re-syncs device states |
| Touch targets | Use on the actual Pi touchscreen | All buttons and toggles are easy to tap without mis-taps |
| README | `cat web/README.md` | Kiosk setup instructions present |

**Human check-in**: use the actual touchscreen on the Pi. Walk through a realistic evening scenario: look at current device states, tap Bedtime, verify everything turns off, override the bedroom lamp back on, check that the schedule panel shows the right times. Test from a phone browser on the same network too.

---

## Phase 4b — Voice pipeline

**Agent**: I
**Dependencies**: Phase 4a complete (UI is the primary interface; voice is secondary)
**Entry condition**: API running, UI working
**Delivers**: voice control process, supported commands doc

### Tasks

#### 4b.1 — Wake word detection

- Select and integrate a lightweight wake word engine (Porcupine, Snowboy, or similar)
- Configure with a custom wake word or use a default (e.g., "hey home" or "computer")
- Continuously listen on the Pi's microphone
- On wake word detection, play a short acknowledgment tone through the speaker

#### 4b.2 — Speech-to-text

- Integrate Whisper (running locally on the Pi) or a lightweight alternative
- After wake word triggers, record audio for up to 5 seconds (or until silence detected)
- Transcribe the audio to text
- Handle errors gracefully: if transcription fails or is empty, play an error tone and return to listening

#### 4b.3 — Intent parsing

- Map transcribed text to API calls. Support these command patterns:
  - Device control: "turn on/off [device name]" → `POST /devices/{id}/action`
  - Scene trigger: "activate [scene name]" / "[scene name]" → `POST /scenes/{id}/execute`
  - Status query: "is the [device name] on?" → `GET /devices/{id}` → spoken response
- Fuzzy matching on device and scene names (the user won't say the exact slug)
- Unrecognized commands get a spoken response: "sorry, I didn't understand that"

#### 4b.4 — Text-to-speech responses

- Use `pyttsx3`, `espeak`, or a similar local TTS engine
- Provide spoken confirmations: "turning off living room lights", "activating bedtime"
- Provide spoken status responses: "the bedroom lamp is currently on"
- Provide spoken error messages for unrecognized commands or device failures

#### 4b.5 — Process management

- `interfaces/voice.py` runs as a standalone process alongside the main server
- Connects to the API at `http://localhost:8000` (configurable)
- Include a systemd service file for auto-starting on boot alongside the main server
- Graceful shutdown on SIGTERM

#### 4b.6 — README

`interfaces/README.md` with:

- **Supported voice commands** — full list with examples
- **How to configure the wake word** — setup steps for the chosen engine
- **How to start the voice process** — exact command, systemd service install
- **How to test** — test commands and expected spoken responses
- **Hardware requirements** — microphone and speaker setup notes

### Checkpoint 4b — Voice gate

| Test | How to verify | Pass condition |
|------|---------------|----------------|
| Wake word triggers | Say the wake word from across the room | Acknowledgment tone plays |
| Device on (real-world) | "Turn on the living room lights" | Kasa plug turns on, UI updates, spoken confirmation |
| Device off (real-world) | "Turn off the desk relay" | Relay clicks off, UI updates, spoken confirmation |
| Scene trigger (real-world) | "Activate bedtime" | All bedtime devices respond, UI updates, spoken confirmation |
| Status query | "Is the bedroom lamp on?" | Spoken response with correct current state |
| Fuzzy matching | "Turn on living room" (partial name) | Correctly matches "Living room lights" device |
| Unknown command | "Do a barrel roll" | Spoken error response, no crash |
| UI sync | Watch the touchscreen while giving a voice command | Touchscreen toggles update in real time via WebSocket |
| Multiple commands | Give three commands in quick succession | All three execute correctly without overlap or crash |
| README | `cat interfaces/README.md` | Command list, wake word config, systemd service present |

**Human check-in**: stand in different spots in the room and test wake word detection range. Give a variety of commands covering device control, scene activation, and status queries. Watch the touchscreen while doing it to verify real-time sync. Test edge cases like speaking too quickly after the wake word, or giving a command while music is playing.

---

## Phase 5 — Full system integration

**Agent**: human-led with agent support as needed
**Dependencies**: all prior phases complete
**Entry condition**: all individual checkpoints passed

### Integration test scenarios

These are end-to-end scenarios that exercise multiple interfaces and services simultaneously. Run each on the actual Pi with real devices.

| # | Scenario | Steps | Pass condition |
|---|----------|-------|----------------|
| 1 | Bedtime via touch | Tap "Bedtime" on touchscreen | All target devices off, UI reflects, physical devices off |
| 2 | Morning via scheduler | Set Morning schedule for 1 min from now, wait | Kitchen lights on, Spotify plays, UI updates, no touch needed |
| 3 | Voice override | After Bedtime fires, say "turn on bedroom lamp" | Lamp turns on, UI shows it on, other devices stay off |
| 4 | Touch override | After scheduler fires, tap one device off on touchscreen | Device turns off, state persists, scheduler doesn't re-enable it |
| 5 | Cross-interface consistency | Toggle via voice, check UI; toggle via UI, ask status via voice | Both interfaces always show the same state |
| 6 | Concurrent commands | Tap a scene on UI while giving a voice command simultaneously | Both complete without error, final state is consistent |
| 7 | Schedule management via UI | Create a new schedule from the API, verify it appears in UI, toggle it off, verify it doesn't fire | Full lifecycle works through the UI |
| 8 | New device hot-add | Add a new driver + config entry, restart server | New device appears in UI and responds to voice commands |
| 9 | Resilience — server restart | Stop server, restart, verify UI reconnects and state is preserved | SQLite state survives restart, UI reconnects, schedules resume |
| 10 | Resilience — network blip | Disconnect and reconnect WiFi (affects Kasa devices) | Kasa commands fail gracefully during outage, resume when network returns |

### Final deliverables

- Updated root `README.md` with complete setup-to-run instructions
- Systemd service files for: main server, voice pipeline
- Chromium kiosk autostart config
- All test scripts collected in `tests/` with a `run_all.sh` script

### Checkpoint 5 — Ship gate

| Test | How to verify | Pass condition |
|------|---------------|----------------|
| Cold start | Reboot the Pi from power-off | Server auto-starts, UI loads on touchscreen, voice pipeline starts, schedules resume |
| All 10 integration scenarios | Run through each scenario above | All pass |
| 24-hour soak test | Leave the system running overnight with schedules active | Morning schedule fires correctly, no crashes, memory usage stable |

**Human check-in**: this is the final sign-off. Run through all 10 integration scenarios on the actual Pi. Leave the system running overnight. Check logs in the morning. If everything holds, the system is live.

---

## README delivery summary

Each phase produces specific documentation. All READMEs follow a consistent structure: "What this does" (2-3 sentences), "How to test" (exact commands with expected output), and "How to use this in your code" (import examples and usage patterns for downstream agents).

| Phase | README | Key contents |
|-------|--------|--------------|
| 1 | `README.md` (root) | Project overview, folder structure, install, run tests |
| 1 | `schemas/README.md` | Every type with field descriptions and example JSON |
| 2D | `drivers/README.md` | Test commands per driver, how to add a new driver |
| 2C | `core/README.md` | Event types table, subscription examples, init order |
| 3 | `core/api_README.md` | Endpoint table, curl examples, WebSocket test client |
| 4a | `web/README.md` | Dev testing, kiosk mode setup for Pi touchscreen |
| 4b | `interfaces/README.md` | Voice command list, wake word config, systemd service |
| 5 | `README.md` (root, updated) | Complete setup-to-run instructions, systemd files, troubleshooting |
