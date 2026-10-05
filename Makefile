# Hestia — home automation system
#
# Common workflows wrapped as `make` targets. Run `make help` for the list.
# Most targets shell out to `uv` — install it first: https://docs.astral.sh/uv/

# Resolve `uv`: prefer one already on PATH, else the location the official
# installer drops it (~/.local/bin). Override with `make UV=/path/to/uv ...`.
UV ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.local/bin/uv)
PYTHON := $(UV) run python
PYTEST := $(UV) run pytest
NPM ?= npm
FRONTEND := frontend

# Hardware-test environment overrides (export these or pass on the command line):
#   make kasa-test KASA_HOST=192.168.1.42
#   make spotify-test SPOTIFY_CLIENT_ID=... SPOTIFY_CLIENT_SECRET=...
KASA_HOST ?=
KASA_KIND ?= plug
SPOTIFY_CLIENT_ID ?=
SPOTIFY_CLIENT_SECRET ?=
SPOTIFY_REDIRECT_URI ?= http://127.0.0.1:8888/callback
SPOTIFY_TARGET_DEVICE ?=

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help:
	@echo "Hestia — make targets"
	@echo ""
	@echo "Pipeline (Linux + macOS):"
	@echo "  make setup          Ensure uv and Node 22.12+ (or 20.19+) are installed"
	@echo "  make build          Sync deps, byte-compile, build the frontend"
	@echo "  make check          Type-check the frontend (svelte-check + tsc)"
	@echo "  make run            Start the server in the foreground"
	@echo "  -> full bootstrap:  make setup build run"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Alias for build"
	@echo "  make lock           Re-lock dependencies (regenerate uv.lock)"
	@echo "  make clean          Remove caches, dev DB, frontend/dist"
	@echo "  make distclean      clean + remove .venv, uv.lock, node_modules"
	@echo ""
	@echo "Tests — software only (no hardware needed):"
	@echo "  make test           pytest, then vitest + svelte-check"
	@echo "  make test-schemas   pytest tests/test_schemas.py"
	@echo "  make test-core      pytest tests/test_core.py"
	@echo "  make test-api       pytest tests/test_api.py (Phase 3 API)"
	@echo "  make test-integration   Core integration micro-test"
	@echo "  make test-mock      All driver tests in --mock mode"
	@echo "  make ws-test        Run the WebSocket smoke client"
	@echo ""
	@echo "Tests — hardware (run on the Pi with real devices):"
	@echo "  make relay-test     Real GPIO relay test (relay must be wired)"
	@echo "  make kasa-test      Real Kasa device test (set KASA_HOST=<ip>)"
	@echo "  make kasa-discover  Scan LAN for Kasa devices and list IPs"
	@echo "  make spotify-test   Real Spotify test (needs SPOTIFY_* env vars)"
	@echo "  make hardware-test  All three hardware tests (relay+kasa+spotify)"
	@echo ""
	@echo "Run:"
	@echo "  make run            Start the FastAPI server (Phase 3+)"
	@echo "  make run-dev        API with auto-reload + Vite dev server on :5173"
	@echo ""
	@echo "Pi deployment (run ON the Pi after cloning the repo):"
	@echo "  make install-pi             Auto-detect desktop vs headless, install systemd units + kiosk"
	@echo "  make install-pi-kiosk-headless  Force headless kiosk (Ubuntu Server) — installs minimal X stack"
	@echo "  make install-pi-server    Server only, skip the kiosk"
	@echo "  make uninstall-pi           Remove installed systemd units"
	@echo "  make pi-status              Show status of hestia.service + hestia-kiosk.service"
	@echo "  make pi-logs                Tail the server's journal"
	@echo "  make pi-restart             Restart hestia.service"
	@echo "  make service-install        Same as install-pi-server (Pantheon's name)"
	@echo "  make service-uninstall      Remove the server unit"
	@echo "  make service-status         Show status of hestia.service"
	@echo "  make service-restart        Same as pi-restart"
	@echo "  make service-logs           Same as pi-logs"
	@echo ""
	@echo "Scenes & schedules (server must be running):"
	@echo "  make seed                  Upsert default wakeup + bedtime scenes/schedules"
	@echo "  make scene-wakeup          Upsert just the wakeup scene"
	@echo "  make scene-bedtime         Upsert just the bedtime scene"
	@echo "  make schedule-wakeup       Upsert wakeup schedule (07:00 weekdays)"
	@echo "  make schedule-bedtime      Upsert bedtime schedule (23:00 daily)"
	@echo "  make scenes-list           List all scenes"
	@echo "  make scene-show ID=...     Show one scene"
	@echo "  make scene-run ID=...      Trigger scene execution"
	@echo "  make scene-delete ID=...   Delete a scene"
	@echo "  make schedules-list        List all schedules"
	@echo "  make schedule-show ID=...  Show one schedule"
	@echo "  make schedule-toggle ID=... Toggle enabled flag"
	@echo "  make schedule-delete ID=... Delete a schedule"
	@echo ""
	@echo "Examples:"
	@echo "  make kasa-test KASA_HOST=192.168.1.42"
	@echo "  make kasa-test KASA_HOST=192.168.1.43 KASA_KIND=bulb"
	@echo "  make spotify-test SPOTIFY_CLIENT_ID=abc SPOTIFY_CLIENT_SECRET=xyz"
	@echo "  make spotify-test SPOTIFY_CLIENT_ID=abc SPOTIFY_CLIENT_SECRET=xyz SPOTIFY_TARGET_DEVICE=RaspberryPi"

# ---------------------------------------------------------------------------
# Setup / build
# ---------------------------------------------------------------------------

# Exit 0 only for a Node the frontend toolchain supports (vite 8 / vitest 5):
# >=22.12, or 20.19 to <21.
NODE_VERSION_OK = node -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a>22||(a===22&&b>=12)||(a===20&&b>=19)?0:1)'

# setup — ensure uv and Node 22.12+ (or 20.19+) exist. Idempotent; uses the official
# installer only when uv is missing, preferring curl and falling back to wget.
.PHONY: setup
setup:
	@if [ -x "$(UV)" ] || command -v uv >/dev/null 2>&1; then \
		echo "uv already present: $$($(UV) --version 2>/dev/null || echo $(UV))"; \
	else \
		echo "Installing uv (Linux/macOS)..."; \
		if command -v curl >/dev/null 2>&1; then \
			curl -LsSf https://astral.sh/uv/install.sh | sh; \
		elif command -v wget >/dev/null 2>&1; then \
			wget -qO- https://astral.sh/uv/install.sh | sh; \
		else \
			echo "ERROR: need curl or wget to install uv. See https://docs.astral.sh/uv/"; \
			exit 1; \
		fi; \
		echo "uv installed to $(HOME)/.local/bin — ensure it is on your PATH."; \
	fi
	@if command -v node >/dev/null 2>&1 && $(NODE_VERSION_OK); then \
		echo "node present: $$(node --version)"; \
	else \
		echo "Node.js 22.12+ (or 20.19+) not found — installing (needed to build the UI)..."; \
		if [ "$$(uname)" = "Darwin" ]; then \
			command -v brew >/dev/null 2>&1 || { echo "ERROR: Homebrew required. Install from https://brew.sh, then re-run 'make setup'."; exit 1; }; \
			brew install node; \
		elif command -v apt-get >/dev/null 2>&1; then \
			command -v curl >/dev/null 2>&1 || { echo "ERROR: need curl to install Node. Install curl, then re-run 'make setup'."; exit 1; }; \
			SUDO=""; [ "$$(id -u)" -ne 0 ] && SUDO="sudo"; \
			if [ -n "$$SUDO" ] && ! sudo -n true 2>/dev/null; then echo "  (installing Node system-wide — you may be prompted for your sudo password)"; fi; \
			curl -fsSL https://deb.nodesource.com/setup_22.x -o /tmp/nodesource_setup.sh && \
			$$SUDO bash /tmp/nodesource_setup.sh && \
			$$SUDO apt-get install -y nodejs && \
			rm -f /tmp/nodesource_setup.sh; \
		else \
			echo "ERROR: cannot auto-install Node 22.12+ (or 20.19+) on this OS."; \
			echo "  Install Node 22.12+ (or 20.19+) from https://nodejs.org/en/download, then re-run 'make setup'."; \
			exit 1; \
		fi; \
		if command -v node >/dev/null 2>&1 && $(NODE_VERSION_OK); then \
			echo "node installed: $$(node --version)"; \
		else \
			echo "ERROR: Node install did not produce Node 22.12+ (or 20.19+) on PATH. See https://nodejs.org/en/download"; \
			exit 1; \
		fi; \
	fi

# build — sync locked deps into .venv, byte-compile the sources, and build the
# frontend into frontend/dist (served at / by FastAPI).
.PHONY: build
build:
	$(UV) sync
	$(UV) run python -m compileall -q core drivers interfaces schemas main.py config.py
	cd $(FRONTEND) && $(NPM) ci && $(NPM) run build
	@echo "Build complete."

.PHONY: check
check:
	cd $(FRONTEND) && $(NPM) run check

.PHONY: install
install: build

.PHONY: lock
lock:
	$(UV) lock

.PHONY: clean
clean:
	@find . -path ./$(FRONTEND)/node_modules -prune -o -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name '*.egg-info' -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -path ./$(FRONTEND)/node_modules -prune -o -type f -name '*.pyc' -delete 2>/dev/null || true
	@rm -f home-auto.db home-auto.db-journal
	@rm -rf $(FRONTEND)/dist
	@echo "Cleaned caches, dev DB and frontend/dist."

.PHONY: distclean
distclean: clean
	@rm -rf .venv $(FRONTEND)/node_modules
	@rm -f uv.lock
	@echo "Removed .venv, uv.lock and node_modules. Run 'make build' to rebuild."

# ---------------------------------------------------------------------------
# Software-only tests
# ---------------------------------------------------------------------------

.PHONY: test
test:
	$(PYTEST) -v
	@if [ -d $(FRONTEND)/node_modules ]; then \
		cd $(FRONTEND) && $(NPM) test && $(NPM) run check; \
	else \
		echo "Skipping vitest + svelte-check: $(FRONTEND)/node_modules not found. Run 'make build' first."; \
	fi

.PHONY: test-schemas
test-schemas:
	$(PYTEST) tests/test_schemas.py -v

.PHONY: test-core
test-core:
	$(PYTEST) tests/test_core.py -v

.PHONY: test-api
test-api:
	$(PYTEST) tests/test_api.py -v

.PHONY: test-integration
test-integration:
	$(PYTHON) tests/test_core_integration.py

.PHONY: ws-test
ws-test:
	$(PYTHON) tests/ws_test_client.py

.PHONY: test-mock
test-mock:
	@echo "--- relay (mock) ---"
	$(PYTHON) tests/test_relay_driver.py --mock
	@echo ""
	@echo "--- kasa (mock) ---"
	$(PYTHON) tests/test_kasa_driver.py --mock
	@echo ""
	@echo "--- spotify (mock) ---"
	$(PYTHON) tests/test_spotify_driver.py --mock

# ---------------------------------------------------------------------------
# Hardware tests — run these on the Pi with real devices connected
# ---------------------------------------------------------------------------

.PHONY: relay-test
relay-test:
	@echo "Running real GPIO relay test. You should hear an audible click."
	$(PYTHON) tests/test_relay_driver.py

.PHONY: kasa-discover
kasa-discover:
	@echo "Scanning LAN for Kasa devices (~5s)..."
	$(UV) run kasa discover

.PHONY: kasa-test
kasa-test:
	@if [ -z "$(KASA_HOST)" ]; then \
		echo "ERROR: KASA_HOST is required."; \
		echo "  Find your device IP with: make kasa-discover"; \
		echo "  Then run: make kasa-test KASA_HOST=192.168.x.x"; \
		echo "  For bulbs: add KASA_KIND=bulb"; \
		exit 1; \
	fi
	@echo "Running Kasa hardware test against $(KASA_HOST) ($(KASA_KIND))"
	KASA_HOST=$(KASA_HOST) KASA_KIND=$(KASA_KIND) $(PYTHON) tests/test_kasa_driver.py

.PHONY: spotify-test
spotify-test:
	@if [ -z "$(SPOTIFY_CLIENT_ID)" ] || [ -z "$(SPOTIFY_CLIENT_SECRET)" ]; then \
		echo "ERROR: SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are required."; \
		echo "  Get credentials at https://developer.spotify.com/dashboard"; \
		echo "  Then run: make spotify-test SPOTIFY_CLIENT_ID=... SPOTIFY_CLIENT_SECRET=..."; \
		echo "  First run requires interactive browser OAuth; see drivers/README.md."; \
		exit 1; \
	fi
	@echo "Running Spotify hardware test (first run requires browser OAuth)"
	@if [ -z "$(SPOTIFY_TARGET_DEVICE)" ]; then \
		echo "  (no SPOTIFY_TARGET_DEVICE set — driver will pick the first available device)"; \
	else \
		echo "  Targeting device: $(SPOTIFY_TARGET_DEVICE)"; \
	fi
	SPOTIFY_CLIENT_ID=$(SPOTIFY_CLIENT_ID) \
	SPOTIFY_CLIENT_SECRET=$(SPOTIFY_CLIENT_SECRET) \
	SPOTIFY_REDIRECT_URI=$(SPOTIFY_REDIRECT_URI) \
	SPOTIFY_TARGET_DEVICE=$(SPOTIFY_TARGET_DEVICE) \
	$(PYTHON) tests/test_spotify_driver.py

.PHONY: hardware-test
hardware-test: relay-test kasa-test spotify-test
	@echo ""
	@echo "All three hardware tests passed."

# ---------------------------------------------------------------------------
# Run (Phase 3+ — main.py is created by Agent A)
# ---------------------------------------------------------------------------

.PHONY: run
run:
	$(PYTHON) main.py

.PHONY: run-dev
run-dev:
	@echo "API on :8003 — UI dev server on http://localhost:5173/"
	@trap 'kill 0' INT TERM EXIT; \
	(cd $(FRONTEND) && $(NPM) run dev -- --host) & \
	$(UV) run uvicorn main:app --reload --host 0.0.0.0 --port 8003

# ---------------------------------------------------------------------------
# Pi deployment (run these on the Pi itself, not the dev Mac)
# ---------------------------------------------------------------------------

# Server + kiosk are now separate installers. Run the server one first on
# the Pi, then the kiosk one on whichever Pi has the attached display.
.PHONY: install-pi-server
install-pi-server:
	./scripts/install-server-on-pi.sh

.PHONY: install-pi-kiosk
install-pi-kiosk:
	./scripts/install-kiosk-on-pi.sh

.PHONY: install-pi-kiosk-headless
install-pi-kiosk-headless:
	./scripts/install-kiosk-on-pi.sh --headless

# Convenience: full install (server + kiosk) in one go.
.PHONY: install-pi
install-pi: install-pi-server install-pi-kiosk

.PHONY: uninstall-pi
uninstall-pi:
	./scripts/install-kiosk-on-pi.sh --uninstall
	./scripts/install-server-on-pi.sh --uninstall

.PHONY: pi-status
pi-status:
	@echo "--- hestia.service ---"
	@systemctl --user status hestia.service --no-pager -l || true
	@echo ""
	@echo "--- hestia-kiosk.service ---"
	@systemctl --user status hestia-kiosk.service --no-pager -l || true

.PHONY: pi-logs
pi-logs:
	journalctl --user -u hestia.service -f

.PHONY: pi-restart
pi-restart:
	systemctl --user restart hestia.service
	@echo "Restarted hestia.service"

# Pantheon contract names — Pantheon's installer runs
# `make -C modules/hestia service-install`. The install-pi-* names still work.
.PHONY: service-install service-uninstall service-status service-restart service-logs
service-install: install-pi-server

service-uninstall:
	./scripts/install-server-on-pi.sh --uninstall

service-status:
	@systemctl --user status hestia.service --no-pager -l || true

service-restart: pi-restart

service-logs: pi-logs

# ---------------------------------------------------------------------------
# Scenes & schedules — convenience wrappers around scripts/*.sh
#
# Override the API host with HESTIA_HOST (defaults to http://localhost:8003):
#   make scene-bedtime HESTIA_HOST=http://hera:8003
# ---------------------------------------------------------------------------

# Seed scripts: idempotent upserts (running twice is safe).
.PHONY: scene-wakeup
scene-wakeup:
	./scripts/scene_creator_wakeup.sh

.PHONY: scene-bedtime
scene-bedtime:
	./scripts/scene_creator_bedtime.sh

.PHONY: scene-movie
scene-movie:
	./scripts/scene_creator_movie.sh

.PHONY: schedule-wakeup
schedule-wakeup:
	./scripts/schedule_creator_wakeup.sh

.PHONY: schedule-bedtime
schedule-bedtime:
	./scripts/schedule_creator_bedtime.sh

.PHONY: seed
seed: scene-wakeup scene-bedtime schedule-wakeup schedule-bedtime
	@echo ""
	@echo "Seeded default scenes + schedules."

# Generic CRUD via scripts/automation.sh.
#   make scenes-list
#   make scene-show ID=bedtime
#   make scene-delete ID=bedtime
#   make scene-run ID=bedtime
#   make schedules-list
#   make schedule-show ID=bedtime-nightly
#   make schedule-delete ID=bedtime-nightly
#   make schedule-toggle ID=bedtime-nightly
ID ?=

.PHONY: scenes-list
scenes-list:
	@./scripts/automation.sh scenes list

.PHONY: scene-show
scene-show:
	@if [ -z "$(ID)" ]; then echo "ERROR: pass ID=<scene-id>"; exit 1; fi
	@./scripts/automation.sh scenes show $(ID)

.PHONY: scene-delete
scene-delete:
	@if [ -z "$(ID)" ]; then echo "ERROR: pass ID=<scene-id>"; exit 1; fi
	@./scripts/automation.sh scenes delete $(ID)

.PHONY: scene-run
scene-run:
	@if [ -z "$(ID)" ]; then echo "ERROR: pass ID=<scene-id>"; exit 1; fi
	@./scripts/automation.sh scenes run $(ID)

.PHONY: schedules-list
schedules-list:
	@./scripts/automation.sh schedules list

.PHONY: schedule-show
schedule-show:
	@if [ -z "$(ID)" ]; then echo "ERROR: pass ID=<schedule-id>"; exit 1; fi
	@./scripts/automation.sh schedules show $(ID)

.PHONY: schedule-delete
schedule-delete:
	@if [ -z "$(ID)" ]; then echo "ERROR: pass ID=<schedule-id>"; exit 1; fi
	@./scripts/automation.sh schedules delete $(ID)

.PHONY: schedule-toggle
schedule-toggle:
	@if [ -z "$(ID)" ]; then echo "ERROR: pass ID=<schedule-id>"; exit 1; fi
	@./scripts/automation.sh schedules toggle $(ID)
