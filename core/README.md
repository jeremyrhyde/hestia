# `core/` — orchestration services

The `core/` package owns everything between the API layer and the device
drivers. Hardware is reached only through the
`drivers.registry.DriverRegistry` handle that gets injected into
`SceneEngine`; nothing in `core/` imports concrete driver classes.

## What this does

| Module | Class | Purpose |
|--------|-------|---------|
| `core/events.py` | `EventBus` | In-process async pub/sub. Subscribers are async callables; failures in one subscriber are logged and isolated. |
| `core/state.py` | `StateStore` | `aiosqlite` persistence layer. Stores `DeviceInfo`, `Scene`, `Schedule` JSON; appends every published `Event` to `event_log`. Subscribes to `DEVICE_STATE_CHANGED` to auto-update the `devices` table. |
| `core/scenes.py` | `SceneEngine` | Walks `Scene.actions` in order, dispatches each through the registry, respects `delay_ms`, publishes `DEVICE_STATE_CHANGED` per step plus one `SCENE_EXECUTED` at the end. |
| `core/scheduler.py` | `Scheduler` | Async loop (default 30s tick). Reads enabled `Schedule` rows from the state store, fires the matching scene at its `HH:MM`, prevents duplicate fires within the same day. |

The four services are wired together by Phase 3 (`core/api.py`,
`main.py`). They are independent enough to test in isolation but stitch
into a single linear flow at runtime:

```
   publish ────────────────────────┐
                                   ▼
  caller → SceneEngine ─────► EventBus ─────► StateStore (persist + log)
              │                    │
              └─── execute_action ─┴───► WebSocketManager (Phase 3)
                       │
                       ▼
                 DriverRegistry ──► DeviceDriver
```

## Initialization order

Wire the components in this order — each step depends on the ones above:

```python
from core.events import EventBus
from core.scenes import SceneEngine
from core.scheduler import Scheduler
from core.state import StateStore
from drivers.registry import DriverRegistry

bus = EventBus()                               # 1. bus first
store = StateStore("./home-auto.db", bus)      # 2. construct (no I/O yet)
await store.start()                            # 3. opens DB, subscribes to bus

registry = DriverRegistry()                    # 4. registry
# ... register drivers from config ...

engine = SceneEngine(registry, bus)            # 5. scene engine
scheduler = Scheduler(store, engine, bus)      # 6. scheduler
await scheduler.start()                        # 7. spawns loop task
```

Shutdown is the reverse:

```python
await scheduler.stop()  # cancels loop
await store.close()     # closes connection, unsubscribes
# the bus is just a Python object — no close needed
```

## Event types

| Type (string) | Published by | `data` payload | Typical subscribers |
|---------------|--------------|----------------|---------------------|
| `device_state_changed` | `SceneEngine` after each action; Phase 3 `core/api.py` after direct `POST /devices/{id}/action` | `{"state": <DeviceState>}` (with `device_id` set) | `StateStore` (auto-persist), `WebSocketManager` (broadcast to UI) |
| `scene_executed` | `SceneEngine` once after the action loop | `{"scene_id": str, "results": [{"device_id", "success", "state", "error"}, ...]}` | `WebSocketManager`, future analytics |
| `schedule_triggered` | `Scheduler` when a schedule's `HH:MM` matches | `{"schedule_id": str, "scene_id": str}` | Diagnostics / logging |
| `device_registered` | Phase 3 `main.py` / driver registry on startup | `{"info": <DeviceInfo>}` | `StateStore` (event log) |
| `device_error` | `SceneEngine` on per-action failure; drivers may emit too | `{"action": str, "error": str}` (with `device_id` set) | `StateStore` (event log), Phase 3 alerting |

`StateStore` also subscribes to **every** `EventType` and writes a row
into `event_log` for auditability — you don't need to manually log
events yourself.

## How to test

```bash
# Unit tests: event bus, state store, scene engine, scheduler
uv run pytest tests/test_core.py -v

# End-to-end micro-integration (no API layer required)
uv run python tests/test_core_integration.py

# Schemas regression — must stay green
uv run pytest tests/test_schemas.py -v
```

## How to use in your code

Subscribe to an event:

```python
from core.events import EventBus
from schemas.events import Event, EventType

bus = EventBus()

async def on_state_change(event: Event) -> None:
    print(f"{event.device_id} -> {event.data['state']}")

bus.subscribe(EventType.DEVICE_STATE_CHANGED, on_state_change)
```

Execute a scene:

```python
from core.scenes import SceneEngine

engine = SceneEngine(registry, bus)
results = await engine.execute_scene(scene)
# results is list[dict]: device_id, success, state, error
```

Reload schedules after a CRUD change (Phase 3 must call this):

```python
await scheduler.reload()
```

## Concurrency notes

- All public methods on every class are `async`.
- `EventBus.publish` `await`s on every subscriber via `asyncio.gather` — a
  slow subscriber will hold up the publisher. Heavy work in a subscriber
  should `asyncio.create_task(...)` to detach.
- `StateStore` serializes through a single `aiosqlite.Connection`. SQLite
  itself is fine with concurrent reads on a single connection but for
  high-write workloads we'd add a per-table lock or a write queue.
- `Scheduler` runs in its own task; `start()` is idempotent, `stop()`
  cancels and awaits the task.
