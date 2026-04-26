#!/usr/bin/env bash
# Hestia kiosk launcher — Chromium fullscreen pointed at the local UI.
#
# Run via the systemd user service in this directory, or invoke directly
# from an X session for testing.
set -euo pipefail

# Disable screen blanking / DPMS so the touchscreen stays on indefinitely.
xset s off
xset -dpms
xset s noblank

# Hide the cursor after 0.5s of idle.
unclutter -idle 0.5 -root &

# Pick whichever Chromium binary is installed (Pi OS ships chromium-browser;
# Ubuntu provides chromium).
CHROMIUM_BIN="$(command -v chromium-browser || command -v chromium || true)"
if [[ -z "${CHROMIUM_BIN}" ]]; then
  echo "start-kiosk: no chromium binary found (apt install chromium-browser)" >&2
  exit 1
fi

UI_URL="${HESTIA_UI_URL:-http://localhost:8000/ui/}"

exec "${CHROMIUM_BIN}" \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --disable-restore-session-state \
  --disable-pinch \
  --overscroll-history-navigation=0 \
  --check-for-update-interval=31536000 \
  --autoplay-policy=no-user-gesture-required \
  "${UI_URL}"
