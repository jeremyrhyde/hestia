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

# Flag notes (RAM-constrained Pi 4 kiosk):
#  - We intentionally do NOT pass --disable-gpu: on the Pi it forces slow
#    software rendering, hurting the "snappier UI" goal. Let Chromium use
#    the VideoCore GPU.
#  - --disk-cache-size bounds Chromium's on-disk cache (bytes); it does not
#    cap RAM directly but stops unbounded cache growth on a long-lived kiosk.
#  - --disable-features=TranslateUI and --disable-session-crashed-bubble
#    suppress popups that would otherwise overlay the kiosk UI after a
#    crash/restart. These are the flags the documented Pi-kiosk reference
#    implementations (FullPageOS, reelyactive) converge on.
exec "${CHROMIUM_BIN}" \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --disable-restore-session-state \
  --disable-session-crashed-bubble \
  --disable-pinch \
  --disable-features=TranslateUI \
  --disable-component-update \
  --overscroll-history-navigation=0 \
  --check-for-update-interval=31536000 \
  --autoplay-policy=no-user-gesture-required \
  --disk-cache-size=52428800 \
  "${UI_URL}"
