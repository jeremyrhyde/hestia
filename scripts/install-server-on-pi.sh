#!/usr/bin/env bash
# Install the Hestia *server* on a Raspberry Pi.
#
# Builds the venv, installs the hestia.service systemd user unit, enables
# linger (so it starts at boot without a login), and starts it. This is
# the only piece needed on a headless server with no attached display.
#
# For the touchscreen / kiosk display, run install-kiosk-on-pi.sh after
# this (it assumes the server is already installed).
#
# Usage:
#   ./scripts/install-server-on-pi.sh             # install + start the server
#   ./scripts/install-server-on-pi.sh --uninstall # remove the server unit
#
# Idempotent — running it twice is safe.

set -euo pipefail

# --- args ------------------------------------------------------------------

ACTION="install"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --uninstall) ACTION="uninstall"; shift ;;
    -h|--help)   sed -n '3,13p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

source "$(dirname "$0")/_pi-common.sh"

echo "Hestia server install"
echo "  HESTIA_HOME = $HESTIA_HOME"
echo "  USER        = $USER_NAME"
echo "  UV_BIN      = $UV_BIN"

# --- uninstall -------------------------------------------------------------

if [[ "$ACTION" == "uninstall" ]]; then
  echo "Uninstalling Hestia server unit..."
  systemctl --user disable --now hestia.service 2>/dev/null || true
  rm -f "$SYSTEMD_USER_DIR/hestia.service"
  systemctl --user daemon-reload || true
  echo "Done. Linger left in place — remove with 'sudo loginctl disable-linger $USER_NAME' if desired."
  exit 0
fi

# --- install ---------------------------------------------------------------

mkdir -p "$SYSTEMD_USER_DIR"

# 1. uv sync — make sure the venv is built.
echo
echo "[1/4] uv sync..."
( cd "$HESTIA_HOME" && "$UV_BIN" sync )

# 2. Install hestia.service.
echo
echo "[2/4] writing hestia.service..."
render_unit "$HESTIA_HOME/deploy/hestia.service" \
            "$SYSTEMD_USER_DIR/hestia.service"

# 3. Reload + enable + start.
echo
echo "[3/4] enabling hestia.service..."
systemctl --user daemon-reload
systemctl --user enable --now hestia.service

# Linger so the server starts at boot without an interactive login.
if ! loginctl show-user "$USER_NAME" 2>/dev/null | grep -q '^Linger=yes'; then
  echo "  enabling linger (sudo required)..."
  sudo loginctl enable-linger "$USER_NAME"
fi

# 4. Status
echo
echo "[4/4] status"
echo
systemctl --user status hestia.service --no-pager -l || true

echo
echo "Server install complete."
echo "  Server: http://$(hostname -I | awk '{print $1}'):8000/ui/"
echo "  Logs:   journalctl --user -u hestia.service -f"
echo
echo "  For the kiosk display, run: ./scripts/install-kiosk-on-pi.sh"
