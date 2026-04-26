# Followups — deferred work

Items consciously deferred during the Phase 1–5 build. Each entry: what, why deferred, when to revisit.

## Open phase work

### Spotify driver — full integration (blocked on `spotifyd` audio path)
- **What:** The `SpotifyDriver` itself is verified working at the API layer — OAuth completes, `transfer_playback` correctly hands control to the targeted Connect endpoint, state reads return accurate metadata, and `target_device_name` substring matching resolves the right device. What's NOT working end-to-end is audio actually coming out of the Pi via the local `spotifyd` daemon. During Checkpoint 3 hardware integration, after the driver successfully transferred playback to `RaspberryPi`, `spotifyd` reported `Track should be available, but no alternatives found` and `404 NotFound` for music tracks despite an active Premium account. We confirmed the driver-side handoff works (the `device_name` in state read flips from `iPhone` to `RaspberryPi`, and the phone loses control), so the failure is downstream — almost certainly a `spotifyd` / `librespot` configuration issue, not a Hestia bug.
- **Why deferred:** integration testing parked while we moved past Checkpoint 3 with the rest of the system working. Driver code requires no further changes to ship Spotify in production.
- **How to apply:** debug `spotifyd` itself, not the driver. Investigation order:
  1. Check `spotifyd --version` — old librespot bundled in spotifyd <0.3.5 has known issues with post-2024 Spotify API changes. Upgrade if needed.
  2. Wipe `~/.cache/spotifyd/` and re-authenticate via zeroconf (open Spotify on phone → speakers → tap RaspberryPi → play a track).
  3. Confirm `aplay -l` shows a working ALSA card; if needed, pin `device = "plughw:N"` in `spotifyd.conf` to the right card.
  4. Verify the spotipy app account ID matches what spotifyd is logged in as (we proved this matched in Phase 3 — recheck if anything changed).
  5. Disable autoplay (`autoplay = false`) so an empty queue doesn't pull in podcast episodes. See [Spotify podcast/episode playback](#spotify-podcastepisode-playback) for the librespot-doesn't-support-episodes story.
- **Related:** [Spotify `target_device_name` matching](#spotify-target_device_name-matching), [Spotify podcast/episode playback](#spotify-podcastepisode-playback), [Media volume slider](#media-volume-slider) (UI feature blocked on this work).
- **Owner:** human (deployment / hardware) once the rest of the system is on the Pi.

### Phase 4b — voice pipeline (entire phase TBD)
- **What:** Phase 4b ships `interfaces/voice.py`, a separate process that runs alongside the Hestia server on the Pi and adds voice control: wake word detection → Whisper STT → intent parsing → API call → TTS confirmation. Spec lives in [`docs/home-auto-build-plan.md`](home-auto-build-plan.md) under "Phase 4b — Voice pipeline" (sections 4b.1–4b.6) and the Checkpoint 4b gate. The architecture is already in place to support it: the voice process is just another HTTP client of the existing `/devices/`, `/scenes/`, `/schedules/` API surface, and any device state changes it triggers fan out to the touchscreen UI via the existing WebSocket — no extra wiring required.
- **Why deferred:** user chose to deploy the touchscreen UI and base system to the Pi first (per "Option A" in the Phase 5 deployment discussion), so day-to-day usage validates the foundation before voice's debugging surface is layered on top.
- **How to apply when ready:** launch Agent I again with the Phase 4b brief. Deliverables include `interfaces/voice.py` (wake word + Whisper + intent + TTS), a `tests/test_voice_intent.py` for offline parsing tests, a systemd unit (`deploy/hestia-voice.service`) that runs the process under the same user as `hestia.service`, and an update to `scripts/install-on-pi.sh` to install the third unit. Hardware prereqs: USB microphone + speaker on the Pi, wake-word engine (Porcupine or similar), local Whisper model. Whisper-tiny / -base are realistic for a Pi 4/5 — `whisper.cpp` will be much faster than the Python `openai-whisper` package.
- **Validation:** Checkpoint 4b's table in `docs/home-auto-build-plan.md` (wake word detection range, fuzzy device-name matching, real-time UI sync via WebSocket while a voice command is in flight, etc.).
- **Owner:** Agent I (Phase 4b track).

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

## Configuration / persistence

### Scenes & schedules as YAML (gitops-style config)
- **What:** Today, scenes and schedules live in `home-auto.db` (SQLite) and are created via `POST /scenes/` / `POST /schedules/` (curl or the future Settings tab). They are *not* configured in a YAML file. The original spec made this deliberate so the touchscreen can edit them without restarting the server or shelling into the Pi.
- **Why deferred:** the runtime UI is the primary editing surface. A version-controllable YAML representation is useful but not essential.
- **How to apply when wanted:** two options that aren't mutually exclusive:
  - **Seed file at boot:** server reads `scenes.yaml` / `schedules.yaml` on startup and upserts into the DB. UI continues to be the live editor; YAML provides defaults and a version-controlled snapshot.
  - **Export/import endpoints:** `GET /scenes/export` → YAML dump; `POST /scenes/import` → load. UI stays the daily driver, but a `git commit` of the export gives you reproducibility.
- **Revisit:** when the user wants their automation in version control, or when scene/schedule definitions get complex enough to warrant code review.

## UI enhancements (deferred from Phase 4a)

### Light theme
- **What:** Dark theme is the only Phase 4a ship. A daytime kitchen-counter Pi may want light.
- **How to apply:** the design tokens live at `:root` in `web/style.css`. A second token block under `[data-theme="light"]` plus a small toggle in the header would do it. Phase 4a explicitly chose to defer.
- **Revisit:** if a user reports glare or readability issues during the day.

### Schedule editing UI
- **What:** Phase 4a surfaces schedules read-only with an enable/disable pill. The API supports full CRUD (`POST/PATCH/DELETE /schedules/`), but creating/editing/deleting schedules is not in the touchscreen UI yet.
- **How to apply:** lives naturally under a future "Settings" tab. The tab-shell pattern in `index.html` already supports adding tabs additively — it's `<button>` + `<section x-show="tab==='settings'">` plus the form components.
- **Revisit:** when the user wants to manage schedules without curl.

### Media volume slider
- **What:** Phase 4a's media controls are play / pause / track-display only. Volume control via `set_volume` is supported by the driver and API but not surfaced.
- **How to apply:** trivial — the dimmer slider pattern in the device row generalizes to volume. Add a slider element bound to `setVolume(dev, level)`.
- **Revisit:** after the Spotify spotifyd audio path is fully working (deferred via the `spotifyd` followup).

## Decisions parked

### Spotify `target_device_name` matching
- **What:** `SpotifyDriver` resolves `target_device_name` via case-insensitive substring match against the user's available Connect endpoints. First hit wins.
- **Why deferred:** good enough for a single Pi running one `librespot` instance. Will only matter if multiple Connect endpoints have overlapping names.
- **Revisit:** if/when the user's Spotify account picks up additional Connect endpoints whose names collide.

### Relay board hardware: 3.3V → 5V level shift required
- **What:** During Phase 3 hardware integration the relay never reliably toggled from API/server commands. The relay would click once at process construction (when the GPIO line first transitioned from input to output-driven), but subsequent commands had no audible effect — neither via the FastAPI server, the standalone `make relay-test`, nor raw `lgpio` writes from a Python REPL. We chased this through gpiozero/lgpio backends, threading concerns, active-high vs active-low config, and direct kernel writes via `gpioset`. Diagnosis: the relay board's optoisolator input expects **5V logic** with an internal current-limiting resistor sized accordingly. The Pi's 3.3V GPIO HIGH signal doesn't drive enough current through that resistor to switch the optoisolator, so the relay coil never sees the trigger.
- **Why deferred:** waiting on parts. User is procuring small-signal NPN transistors (2N2222 / BC547 / similar) to build a 3.3V → 5V level shifter: Pi GPIO drives the transistor base through ~1kΩ; transistor switches the 5V rail onto the relay board's signal input. Standard pattern.
- **How to apply once parts arrive:** wire one transistor per relay channel as a low-side switch on the relay's signal input (or use a dedicated logic-level shifter board). After install, no software change is needed — the existing `RelayDriver` + `devices.yaml` `active_high` setting will work as-is, since the inversion semantics are handled the same way regardless of whether 3.3V or 5V drives the optoisolator.
- **Validation when ready:** run `make relay-test` first (should produce 4 distinct audible clicks: turn_on / turn_off / toggle / construction-release). Then `make run-dev` and the alternating-curl loop:
  ```bash
  for s in on off on off on off; do
    curl -s -X POST http://localhost:8000/devices/relay-desk/action \
      -H 'Content-Type: application/json' -d "{\"action\":\"turn_${s}\"}" >/dev/null
    sleep 1
  done
  ```
  Should produce 6 distinct clicks.

### Spotify podcast/episode playback
- **What:** When `SpotifyDriver` transfers playback to a `spotifyd`/`librespot` instance, podcast episodes (`spotify:episode:...`) fail to play with `404 NotFound` errors in the spotifyd journal. Music tracks work fine.
- **Why deferred:** This is an upstream librespot limitation — librespot historically does not support podcast playback (DRM/encryption differs from music tracks). Not something we can fix in our driver.
- **Workaround:** Disable autoplay in `spotifyd.conf` (`autoplay = false`) so an empty queue doesn't pull in episodes. Voice / scene commands that target specific music tracks or playlists work normally.
- **Revisit:** Watch https://github.com/librespot-org/librespot for episode support, or swap to a different Connect daemon if podcast playback becomes important.

### `python-kasa` 0.10 bulb dimmer path
- **What:** `KasaDriver.execute(SET_BRIGHTNESS)` tries the new `Light` module path first, falls back to legacy `device.set_brightness`. If a bulb supports neither, it raises.
- **Why deferred:** all current Kasa devices in the user's setup are plugs (no DIMMER capability used yet).
- **Revisit:** when the user adds a Kasa bulb. May need a third path or a model-specific branch.
