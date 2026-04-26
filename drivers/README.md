# `drivers/` — device driver layer

## What this does

The driver layer is the only part of Hestia that talks to hardware. Every
driver subclasses :class:`drivers.base.DeviceDriver` and exposes the same
four async methods (`get_info`, `get_state`, `execute`, `get_capabilities`)
no matter what physical thing sits behind it. That uniformity is what lets
the core API, scene engine, scheduler, and frontends stay completely
hardware-agnostic — they only ever speak in the shared `schemas/` types.

The drivers live behind a `DriverRegistry` (a flat `device_id ->
DeviceDriver` map). Construction reads `devices.yaml`, which is validated by
`schemas.DevicesConfig`, and instantiates one driver per entry.

Three concrete drivers ship today:

| Driver | Underlying lib | Capabilities | Notes |
|--------|----------------|--------------|-------|
| `RelayDriver` | `gpiozero` | `TOGGLE` | Mock fallback if gpiozero / pin init fails (macOS dev). |
| `KasaDriver` | `python-kasa` ≥0.10 | `TOGGLE` (plug), `TOGGLE`+`DIMMER` (bulb) | Returns last-known state on transient network errors. |
| `SpotifyDriver` | `spotipy` | `MEDIA_CONTROL` | Requires one-time OAuth consent; see below. |

## How to test

All test scripts default to **live mode** and accept `--mock` to skip
hardware. Run from the repo root.

### Driver test commands

```bash
# Relay
uv run python tests/test_relay_driver.py --mock          # software-only
uv run python tests/test_relay_driver.py --pin 17        # live, pin BCM 17

# Kasa
KASA_HOST=192.168.1.42 uv run python tests/test_kasa_driver.py
uv run python tests/test_kasa_driver.py --mock

# Kasa bulb (gains the DIMMER capability + set_brightness verb)
uv run python tests/test_kasa_driver.py --host 192.168.1.43 --kind bulb

# Spotify
SPOTIFY_CLIENT_ID=... \
SPOTIFY_CLIENT_SECRET=... \
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback \
SPOTIFY_TARGET_DEVICE=librespot \
uv run python tests/test_spotify_driver.py
uv run python tests/test_spotify_driver.py --mock
```

Each script pretty-prints `DeviceState` before and after every action and
exits with `PASS` / `FAIL` (return code 0 / 1).

### What to look for on real hardware

| Driver | Physical signal |
|--------|-----------------|
| Relay | Audible click on every `turn_on` / `turn_off` / `toggle`. Visible LED on the relay board. |
| Kasa plug | Click + LED flip on the plug; `state.power` reflects the new state. |
| Kasa bulb | Bulb turns on/off / dims to `set_brightness` value. |
| Spotify | Music plays/pauses through the targeted Connect endpoint; `state.attributes.track` populated. |

### Config you need to provide for hardware tests

| Driver | Where set | Required values |
|--------|-----------|-----------------|
| Relay | CLI flag `--pin` (or `devices.yaml` `params.pin`) | BCM pin number wired to the relay signal |
| Kasa | env `KASA_HOST` / CLI `--host` (or `devices.yaml` `params.host`) | LAN IP or hostname of the Kasa device |
| Kasa bulb | env `KASA_KIND=bulb` / CLI `--kind bulb` (or `params.kind: bulb`) | "bulb" |
| Spotify | env `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`, `SPOTIFY_TARGET_DEVICE` (or `devices.yaml` `params.*`) | Spotify Web API credentials, registered redirect URI, name of Connect endpoint |

Create `devices.yaml` from `devices.yaml.example` at the repo root and fill
in your real values. The API entry point (Phase 3) will read it at startup.

### Spotify OAuth — first-run setup

The Spotify driver needs an OAuth token to talk to the Web API. The first
time a process runs with a given `cache_path` (default `.spotify_cache`),
`spotipy` performs an interactive auth dance:

1. The driver prints an `accounts.spotify.com` URL.
2. Open that URL in any browser, sign in, and accept.
3. Spotify redirects to `redirect_uri` (which can be a non-running local
   server — the URL itself contains the `?code=...` you need).
4. Paste the redirected URL back into the terminal where the driver is
   waiting.
5. `spotipy` writes the refresh token to `.spotify_cache`.

**On a headless Pi** you cannot easily do step 2. Recommended flow:

1. Run `tests/test_spotify_driver.py` once on your laptop (same creds).
2. Confirm `PASS`. A `.spotify_cache` file is now in your repo root.
3. `scp .spotify_cache pi@<pi>:/path/to/hestia/`.
4. The Pi can now run non-interactively forever (the refresh token survives
   indefinitely as long as you don't revoke the app).

If auth fails for any reason at runtime, the driver logs a warning and flips
into mock mode rather than crashing.

## How to add a new driver

1. **Create the file**: `drivers/<thing>_driver.py`.
2. **Extend `DeviceDriver`** and implement the four async methods. Use the
   `match` statement on `action.action`, branching on
   `StandardAction.<VERB>` for known verbs and `case _:` raising
   `ValueError` for unknown ones. If your driver introduces a verb that
   another driver also uses, promote it to `schemas.StandardAction` and
   update `schemas/README.md`.
3. **Register the driver name** in `schemas.config.DeviceConfig.driver` —
   add your slug to the `Literal[...]` so YAML validation accepts it.
4. **Document it** in this README's table and add a `devices.yaml.example`
   entry showing required `params`.
5. **Write a test** in `tests/test_<thing>_driver.py` modeled after the
   existing three: live by default, `--mock` flag, prints `PASS`.

### Minimal driver template

```python
"""Example driver."""

from __future__ import annotations

import asyncio

from drivers.base import DeviceDriver
from schemas.device import (
    DeviceAction,
    DeviceCapability,
    DeviceInfo,
    DeviceState,
    DeviceType,
    StandardAction,
)


class MyDriver(DeviceDriver):
    def __init__(self, device_id: str, name: str, **params) -> None:
        self._id = device_id
        self._name = name
        self._state = DeviceState(power=False)

    async def get_info(self) -> DeviceInfo:
        return DeviceInfo(
            id=self._id,
            name=self._name,
            device_type=DeviceType.CUSTOM,
            driver_name="MyDriver",
            capabilities=await self.get_capabilities(),
            state=await self.get_state(),
        )

    async def get_state(self) -> DeviceState:
        return self._state

    async def execute(self, action: DeviceAction) -> DeviceState:
        match action.action:
            case StandardAction.TURN_ON:
                self._state = DeviceState(power=True)
            case StandardAction.TURN_OFF:
                self._state = DeviceState(power=False)
            case _:
                raise ValueError(f"unsupported action: {action.action!r}")
        return self._state

    async def get_capabilities(self) -> list[DeviceCapability]:
        return [DeviceCapability.TOGGLE]
```

### Driver lifecycle

All shipped drivers expose an optional `async def close(self)` method that
the registry / API layer can call on shutdown to release resources (GPIO
pins, Kasa sockets, OAuth handles). New drivers are encouraged to implement
the same hook even if it's a no-op — this keeps the lifecycle uniform.
`DeviceDriver` does not require it (yet) so existing code that doesn't
override `close` keeps working unchanged.
