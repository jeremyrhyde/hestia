# Followups — deferred work

Items consciously deferred during the Phase 1–5 build. Each entry: what, why deferred, when to revisit.

## Reconciliation already scheduled

### Move `DEVICE_STATE_CHANGED` publish into `DriverRegistry.execute_action`
- **What:** Today, `core/scenes.py` publishes `DEVICE_STATE_CHANGED` after each step. Phase 3 (`core/api.py`) would also need to publish on direct device calls. To keep the firing uniform regardless of caller (API, scene, schedule), move the publish into `DriverRegistry.execute_action` itself. Then strip the publish from `SceneEngine`.
- **Why deferred:** wiring belongs in Phase 3 where the registry, API, and scene engine come together. Doing it in Phase 2 would have meant editing `drivers/registry.py` while Agent D was still using it.
- **Owner:** Agent A in Phase 3.

## Deferred — revisit later

### Schedule timezones
- **What:** `core/scheduler.py` matches `Schedule.time` against `datetime.now()` (system local time). No timezone field on `Schedule`.
- **Why deferred:** single-Pi deployment; local time is fine. No DST or multi-region concerns.
- **Revisit:** when the system is ever deployed across multiple sites, or if DST transitions cause schedules to fire at the wrong wall-clock time. Move to UTC storage with optional per-schedule TZ override.

### `event_log` retention / pruning
- **What:** `StateStore.log_event()` appends every event to the `event_log` table with no upper bound. Over months of uptime the table grows without limit.
- **Why deferred:** not a problem at week-one scale. Adding a retention job before there's a real query pattern would be premature.
- **Revisit:** Phase 5, or whenever the DB hits ~100MB. Likely fix: nightly job that deletes rows older than N days (config knob), keeping a cap on row count. Could also move to a rotating log table or split log to a separate file.

## Decisions parked

### Spotify `target_device_name` matching
- **What:** `SpotifyDriver` resolves `target_device_name` via case-insensitive substring match against the user's available Connect endpoints. First hit wins.
- **Why deferred:** good enough for a single Pi running one `librespot` instance. Will only matter if multiple Connect endpoints have overlapping names.
- **Revisit:** if/when the user's Spotify account picks up additional Connect endpoints whose names collide.

### Spotify podcast/episode playback
- **What:** When `SpotifyDriver` transfers playback to a `spotifyd`/`librespot` instance, podcast episodes (`spotify:episode:...`) fail to play with `404 NotFound` errors in the spotifyd journal. Music tracks work fine.
- **Why deferred:** This is an upstream librespot limitation — librespot historically does not support podcast playback (DRM/encryption differs from music tracks). Not something we can fix in our driver.
- **Workaround:** Disable autoplay in `spotifyd.conf` (`autoplay = false`) so an empty queue doesn't pull in episodes. Voice / scene commands that target specific music tracks or playlists work normally.
- **Revisit:** Watch https://github.com/librespot-org/librespot for episode support, or swap to a different Connect daemon if podcast playback becomes important.

### `python-kasa` 0.10 bulb dimmer path
- **What:** `KasaDriver.execute(SET_BRIGHTNESS)` tries the new `Light` module path first, falls back to legacy `device.set_brightness`. If a bulb supports neither, it raises.
- **Why deferred:** all current Kasa devices in the user's setup are plugs (no DIMMER capability used yet).
- **Revisit:** when the user adds a Kasa bulb. May need a third path or a model-specific branch.
