# Hestia — Raspberry Pi home automation

A small extensible home automation system that runs on a Raspberry Pi: a
FastAPI core dispatches commands from multiple interfaces (touchscreen kiosk,
voice, scheduler) to device drivers (Kasa plugs/switches over WiFi, GPIO
relays, Spotify Connect). Components communicate through Pydantic schemas and
an async event bus, so adding a new device or interface requires no changes to
existing code.

## Folder structure

```
.
├── main.py                 # entry point (added in Phase 3)
├── config.py               # Pydantic Settings (env / .env loader)
├── requirements.txt
│
├── core/                   # orchestration, never touches hardware
├── schemas/                # shared Pydantic data contracts
├── drivers/                # device-specific adapters + registry
├── interfaces/             # server-side API consumers (e.g. voice)
├── web/                    # static touchscreen frontend
├── tests/                  # pytest suite
│
├── reference/              # archive of pre-existing controller modules
│                           # (NOT imported — kept for reference; will be
│                           # removed after Phase 2)
└── home-auto-context.md    # architecture spec
└── home-auto-build-plan.md # phased agentic build plan
```

## Install

```bash
uv sync
```

This creates `.venv/` and installs runtime + dev dependencies from
`pyproject.toml`. Requires [uv](https://docs.astral.sh/uv/) (`brew install uv`).

Note: `gpiozero` is gated to `sys_platform == "linux"` so it is only installed
on the Pi. On macOS / a dev laptop it is skipped; Phase 2D drivers fall back
to a mock when GPIO is unavailable.

## Run tests

```bash
uv run pytest
# or, just the foundation tests:
uv run pytest tests/test_schemas.py -v
```

## Run the dev server

```bash
make run-dev               # uvicorn on :8000 with --reload
# UI:    http://localhost:8000/ui/
# API:   http://localhost:8000/docs
# Health: http://localhost:8000/health
```

## Pi deployment

After cloning the repo onto the Pi (`git clone ...`) and installing `uv`:

```bash
cd ~/hestia
make install-pi
```

The install script:

- runs `uv sync` to build the venv
- writes `~/.config/systemd/user/hestia.service` (the FastAPI server)
- writes `~/.config/systemd/user/hestia-kiosk.service` (Chromium fullscreen)
- installs `chromium-browser` and `unclutter` via apt if missing
- enables linger (`loginctl enable-linger`) so services start at boot
- on **headless Ubuntu Server**, also installs a minimal X stack
  (`xserver-xorg`, `xinit`, `openbox`), enables tty1 auto-login, and adds
  `~/.bash_profile` hooks so the Pi boots straight into the kiosk

Useful follow-up commands:

```bash
make pi-status      # status of both services
make pi-logs        # tail the server's journal
make pi-restart     # restart hestia.service
make uninstall-pi   # remove the units
```

Force a specific install mode if auto-detection picks the wrong one:

```bash
make install-pi-headless    # Ubuntu Server / no desktop
make install-pi-no-kiosk    # server only (e.g., a headless API host with
                            # the touchscreen on a separate Pi)
```

For full deployment details (boot sequence, kiosk troubleshooting, OS-specific
notes) see `web/README.md`.

## Status

Phases 1–4a complete: foundation, drivers, core services, API + WebSocket,
touchscreen UI. Pi deployment scripts are in place. Phase 4b (voice) and
Phase 5 (final integration / soak) still ahead — see
`docs/home-auto-build-plan.md`.
