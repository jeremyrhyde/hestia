# `core/api.py` — REST + WebSocket surface

The Phase 3 API layer is the single entry point for every Hestia
interface (touchscreen, voice, future mobile/CLI/etc.). It is a thin
veneer over the core services — every route just delegates to the
:class:`drivers.registry.DriverRegistry`,
:class:`core.state.StateStore`, :class:`core.scenes.SceneEngine`, or
:class:`core.scheduler.Scheduler` and returns Pydantic models that match
the contracts in `schemas/`.

## Endpoint table

| Method  | Path                              | Body                  | Returns                                  | Errors                                  |
|---------|-----------------------------------|-----------------------|------------------------------------------|-----------------------------------------|
| GET     | `/health`                         | —                     | `{status, devices_registered, devices_failed}` | —                                  |
| GET     | `/devices/`                       | —                     | `list[DeviceInfo]`                       | —                                       |
| GET     | `/devices/{id}`                   | —                     | `DeviceInfo`                             | 404 unknown device                      |
| POST    | `/devices/{id}/action`            | `DeviceAction`        | `DeviceState`                            | 404 unknown, 422 malformed body         |
| GET     | `/scenes/`                        | —                     | `list[Scene]`                            | —                                       |
| GET     | `/scenes/{id}`                    | —                     | `Scene`                                  | 404 unknown                             |
| POST    | `/scenes/`                        | `Scene`               | `Scene`                                  | 422 malformed body                      |
| PUT     | `/scenes/{id}`                    | `Scene`               | `Scene`                                  | 400 path/body id mismatch, 422 malformed |
| DELETE  | `/scenes/{id}`                    | —                     | 204 no content                           | —                                       |
| POST    | `/scenes/{id}/execute`            | —                     | `list[result]` per-action results        | 404 unknown                             |
| GET     | `/schedules/`                     | —                     | `list[Schedule]`                         | —                                       |
| GET     | `/schedules/{id}`                 | —                     | `Schedule`                               | 404 unknown                             |
| POST    | `/schedules/`                     | `Schedule`            | `Schedule` (then `scheduler.reload()`)   | 422 malformed                           |
| PATCH   | `/schedules/{id}`                 | `dict[str, Any]`      | `Schedule` (merged + validated)          | 404 unknown, 422 invalid merge          |
| DELETE  | `/schedules/{id}`                 | —                     | 204 (then `scheduler.reload()`)          | —                                       |
| WS      | `/ws`                             | —                     | streamed `Event` JSON                    | —                                       |

`DeviceAction`, `DeviceInfo`, `DeviceState`, `Scene`, and `Schedule` are
defined in `schemas/`. See `schemas/README.md` for field-level docs and
example payloads.

### Per-action result shape (returned by `POST /scenes/{id}/execute`)

```json
[
  {"device_id": "kasa-living-room", "success": true,  "state": {"power": false, "attributes": {}}, "error": null},
  {"device_id": "spotify-pi",       "success": false, "state": null,                              "error": "..."}
]
```

The list is in the same order as `Scene.actions`. Failures do not abort
subsequent steps.

## Static files / UI path

The single-page touchscreen UI built by Phase 4a is mounted at
**`/ui/`** when `WEB_DIR` (default `./web`) exists. So
`http://<pi>:8000/ui/` serves `web/index.html`. The path is intentionally
under a sub-prefix so it cannot collide with API routes.

If `WEB_DIR` is missing at startup the mount is skipped and a warning
is logged — the API still boots normally so Phase 4a can be developed
in parallel.

The mount path is exported as `core.api.UI_MOUNT_PATH` for downstream
agents.

## How to start the server

From the repo root:

```bash
make run            # python main.py
make run-dev        # uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Both targets honour `Settings()` from `config.py`, which reads `.env` if
present. To override on the command line:

```bash
HOST=127.0.0.1 PORT=8765 make run
```

Pass an explicit YAML location via `DEVICES_CONFIG_PATH=/path/to/devices.yaml`.
If the file does not exist the server starts with an empty registry and
the rest of the system (scenes, schedules, WebSocket) still works.

## How to test with curl

`tests/api_curl_tests.sh` walks every endpoint with annotated `curl`
invocations. Run the server in one terminal, then:

```bash
bash tests/api_curl_tests.sh
# or override the device under test:
DEVICE_ID=kasa-living-room bash tests/api_curl_tests.sh
```

Each section prints a heading and the curl response. The script uses
`set -euo pipefail`, so the first hard failure aborts.

## How to test the WebSocket

`tests/ws_test_client.py` is a small client that connects to `/ws` and
prints every event with a local timestamp:

```bash
make ws-test                 # uv run python tests/ws_test_client.py
HESTIA_WS=ws://pi.local:8000/ws make ws-test
```

Trigger an action via `curl` (or the touchscreen UI, once it's built)
and watch the event stream into the client. The client stays alive
until Ctrl-C.

## Startup sequence

`main.py` builds the runtime via FastAPI's `lifespan` context. Order
matches `core/README.md`:

1. `Settings()` loads from `.env` / environment.
2. `load_devices_config(settings.DEVICES_CONFIG_PATH)` parses
   `devices.yaml` (empty if missing — logged as a warning).
3. `EventBus()`.
4. `StateStore(db_path, bus)` → `await store.start()` (opens SQLite,
   creates tables, subscribes to the bus).
5. `DriverRegistry(event_bus=bus)`. For each `DeviceConfig`, the driver
   factory map (`{"relay": RelayDriver, "kasa": KasaDriver,
   "spotify": SpotifyDriver}`) instantiates one driver. Construction
   failures are caught, logged, and added to `app.state.devices_failed`
   so a single bad driver doesn't kill startup.
6. `SceneEngine(registry, bus)`.
7. `Scheduler(state_store, scene_engine, bus)` → `await scheduler.start()`.
8. `WebSocketManager()` → `manager.subscribe_to_bus(bus)` (subscribes
   to `DEVICE_STATE_CHANGED` and `SCENE_EXECUTED`).
9. `core.api.create_app(...)` wires every component onto `app.state`
   and registers the routers.

Shutdown (lifespan exit) is the reverse:

1. `await scheduler.stop()`
2. `await registry.close_all()` — calls `await driver.close()` on every
   driver that exposes one.
3. `await state_store.close()`

### Where the `DEVICE_STATE_CHANGED` publish lives

Phase 3 reconciliation moved the `DEVICE_STATE_CHANGED` publish from
`SceneEngine` into `DriverRegistry.execute_action`. That means the bus
broadcast is uniform whether the action came from:

- a direct `POST /devices/{id}/action` (source `"api"`),
- a scene execution (source `"scene:{scene.id}"`), or
- the scheduler (source eventually `"scene:{scene.id}"` via the engine).

API handlers therefore never publish events themselves — they just
return the new state and let the registry fire.

## Health endpoint

```http
GET /health
```

```json
{
  "status": "ok",
  "devices_registered": 3,
  "devices_failed": [
    {"id": "spotify-pi", "driver": "spotify", "error": "OAuth not configured"}
  ]
}
```

`devices_registered` is the count of drivers that constructed
successfully and were registered with the registry.
`devices_failed` lists every device whose driver constructor raised
during startup. The server stays up regardless — bad drivers are
diagnosed via this endpoint rather than by tailing logs.

The endpoint is the single source of truth for "did the Pi boot
correctly" checks, used by:

- Operator smoke tests after a deploy.
- The eventual systemd healthcheck in Phase 5.
- The touchscreen UI on initial load (Phase 4a may surface failed
  drivers as a banner).
