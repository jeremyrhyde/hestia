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

## Status

Phase 1 (foundation) is complete: schemas, driver base class, registry,
config loader, and tests are in place. Subsequent phases (drivers, core
services, API, interfaces) build on top — see `home-auto-build-plan.md` for
the full plan.
