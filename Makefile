# Hestia — home automation system
#
# Common workflows wrapped as `make` targets. Run `make help` for the list.
# Most targets shell out to `uv` — install it first: https://docs.astral.sh/uv/

UV ?= uv
PYTHON := $(UV) run python
PYTEST := $(UV) run pytest

# Hardware-test environment overrides (export these or pass on the command line):
#   make kasa-test KASA_HOST=192.168.1.42
#   make spotify-test SPOTIFY_CLIENT_ID=... SPOTIFY_CLIENT_SECRET=...
KASA_HOST ?=
KASA_KIND ?= plug
SPOTIFY_CLIENT_ID ?=
SPOTIFY_CLIENT_SECRET ?=
SPOTIFY_REDIRECT_URI ?= http://127.0.0.1:8888/callback

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help:
	@echo "Hestia — make targets"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install/sync deps via uv (creates .venv)"
	@echo "  make lock           Re-lock dependencies (regenerate uv.lock)"
	@echo "  make clean          Remove caches, build artefacts, *.pyc"
	@echo "  make distclean      clean + remove .venv and uv.lock"
	@echo ""
	@echo "Tests — software only (no hardware needed):"
	@echo "  make test           Run the pytest suite (schemas + core)"
	@echo "  make test-schemas   pytest tests/test_schemas.py"
	@echo "  make test-core      pytest tests/test_core.py"
	@echo "  make test-integration   Core integration micro-test"
	@echo "  make test-mock      All driver tests in --mock mode"
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
	@echo "  make run-dev        Start with auto-reload"
	@echo ""
	@echo "Examples:"
	@echo "  make kasa-test KASA_HOST=192.168.1.42"
	@echo "  make kasa-test KASA_HOST=192.168.1.43 KASA_KIND=bulb"
	@echo "  make spotify-test SPOTIFY_CLIENT_ID=abc SPOTIFY_CLIENT_SECRET=xyz"

# ---------------------------------------------------------------------------
# Setup / build
# ---------------------------------------------------------------------------

.PHONY: install
install:
	$(UV) sync

.PHONY: lock
lock:
	$(UV) lock

.PHONY: clean
clean:
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name '*.egg-info' -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@rm -f home-auto.db home-auto.db-journal
	@echo "Cleaned caches and dev DB."

.PHONY: distclean
distclean: clean
	@rm -rf .venv
	@rm -f uv.lock
	@echo "Removed .venv and uv.lock. Run 'make install' to rebuild."

# ---------------------------------------------------------------------------
# Software-only tests
# ---------------------------------------------------------------------------

.PHONY: test
test:
	$(PYTEST) -v

.PHONY: test-schemas
test-schemas:
	$(PYTEST) tests/test_schemas.py -v

.PHONY: test-core
test-core:
	$(PYTEST) tests/test_core.py -v

.PHONY: test-integration
test-integration:
	$(PYTHON) tests/test_core_integration.py

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
	SPOTIFY_CLIENT_ID=$(SPOTIFY_CLIENT_ID) \
	SPOTIFY_CLIENT_SECRET=$(SPOTIFY_CLIENT_SECRET) \
	SPOTIFY_REDIRECT_URI=$(SPOTIFY_REDIRECT_URI) \
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
	@if [ ! -f main.py ]; then \
		echo "main.py does not exist yet — created in Phase 3 (Agent A)."; \
		exit 1; \
	fi
	$(PYTHON) main.py

.PHONY: run-dev
run-dev:
	@if [ ! -f main.py ]; then \
		echo "main.py does not exist yet — created in Phase 3 (Agent A)."; \
		exit 1; \
	fi
	$(UV) run uvicorn main:app --reload --host 0.0.0.0 --port 8000
