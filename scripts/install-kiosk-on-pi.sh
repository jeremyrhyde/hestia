#!/usr/bin/env bash
# Install the Hestia *kiosk* (fullscreen Chromium display) on a Raspberry Pi.
#
# Installs Chromium + unclutter, the hestia-kiosk.service user unit, and —
# on a headless base (Pi OS Lite / Ubuntu Server) — a minimal X stack plus
# tty1 auto-login so the kiosk launches at boot. Run install-server-on-pi.sh
# first; the kiosk points Chromium at the local server.
#
# RECOMMENDED BASE OS: Raspberry Pi OS Lite (headless, no desktop). It ships
# no display system, so --headless mode adds only a bare X stack + Chromium
# — far lighter on a 2-4GB Pi 4 than a full desktop. Ubuntu Server also
# works via the same --headless path.
#
# Usage:
#   ./scripts/install-kiosk-on-pi.sh             # auto-detect mode
#   ./scripts/install-kiosk-on-pi.sh --desktop   # force desktop-session mode
#   ./scripts/install-kiosk-on-pi.sh --headless  # force headless (Pi OS Lite / Ubuntu Server)
#   ./scripts/install-kiosk-on-pi.sh --uninstall # remove the kiosk unit
#
# Idempotent — running it twice is safe.

set -euo pipefail

# --- args ------------------------------------------------------------------

MODE="auto"
ACTION="install"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --desktop)   MODE="desktop"; shift ;;
    --headless)  MODE="headless"; shift ;;
    --uninstall) ACTION="uninstall"; shift ;;
    -h|--help)   sed -n '3,19p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

source "$(dirname "$0")/_pi-common.sh"

echo "Hestia kiosk install"
echo "  HESTIA_HOME = $HESTIA_HOME"
echo "  USER        = $USER_NAME"
echo "  UV_BIN      = $UV_BIN"

# --- uninstall -------------------------------------------------------------

if [[ "$ACTION" == "uninstall" ]]; then
  echo "Uninstalling Hestia kiosk unit..."
  systemctl --user disable --now hestia-kiosk.service 2>/dev/null || true
  rm -f "$SYSTEMD_USER_DIR/hestia-kiosk.service"
  systemctl --user daemon-reload || true
  echo "Done. X stack / tty1 auto-login / .bash_profile changes left in place"
  echo "— remove manually if desired."
  exit 0
fi

# --- install ---------------------------------------------------------------

mkdir -p "$SYSTEMD_USER_DIR"

# Warn (don't fail) if the server unit isn't installed — the kiosk points
# Chromium at the local server, so it's near-useless without it.
if [[ ! -f "$SYSTEMD_USER_DIR/hestia.service" ]]; then
  echo "  NOTE: hestia.service not found — run ./scripts/install-server-on-pi.sh"
  echo "        first, or the kiosk will load a server that isn't running."
fi

# 1. Install hestia-kiosk.service.
echo
echo "[1/4] writing hestia-kiosk.service..."
render_unit "$HESTIA_HOME/web/kiosk/hestia-kiosk.service" \
            "$SYSTEMD_USER_DIR/hestia-kiosk.service"
chmod +x "$HESTIA_HOME/web/kiosk/start-kiosk.sh"

# 2. Install kiosk dependencies (chromium + unclutter, plus X stack if headless).
echo
echo "[2/4] installing kiosk dependencies..."
KIOSK_PKGS=(unclutter)
# Chromium package name varies: Pi OS Bullseye uses `chromium-browser`,
# while Bookworm/Trixie-based Pi OS and Ubuntu provide `chromium`. Only add
# a package if no chromium binary is already present, and pick whichever
# name apt can actually resolve a candidate for (avoids the
# "package chromium-browser has no installation candidate" failure).
if ! command -v chromium-browser >/dev/null 2>&1 \
     && ! command -v chromium >/dev/null 2>&1; then
  chromium_pkg=""
  for cand in chromium-browser chromium; do
    if apt-cache policy "$cand" 2>/dev/null \
         | grep -q 'Candidate: [^(]'; then
      chromium_pkg="$cand"
      break
    fi
  done
  if [[ -z "$chromium_pkg" ]]; then
    echo "  WARNING: no chromium package candidate found (tried" \
         "chromium-browser, chromium). Run 'sudo apt-get update' and" \
         "check 'apt-cache policy chromium'." >&2
  else
    echo "  using chromium package: $chromium_pkg"
    KIOSK_PKGS+=("$chromium_pkg")
  fi
fi
ensure_apt_packages "${KIOSK_PKGS[@]}"

resolved_mode="$(detect_mode)"
echo "  detected mode: $resolved_mode"
if [[ "$resolved_mode" == "headless" ]]; then
  echo "  installing minimal X stack (xserver-xorg, matchbox-window-manager, xinit)..."
  # --no-recommends keeps this a bare display stack on Pi OS Lite — no
  # desktop bloat. matchbox-window-manager is a tiny, kiosk-oriented WM
  # (smaller than openbox) that reliably gives Chromium a fullscreen
  # surface to attach to.
  ensure_apt_packages --no-recommends \
    xserver-xorg xinit x11-xserver-utils matchbox-window-manager
  render_unit "$HESTIA_HOME/deploy/xinitrc.kiosk" "$USER_HOME/.xinitrc"
  chmod +x "$USER_HOME/.xinitrc"

  # Append the startx-on-tty1 hook to ~/.bash_profile if not already there.
  BPROFILE="$USER_HOME/.bash_profile"
  touch "$BPROFILE"
  if ! grep -q 'exec startx -- -nocursor' "$BPROFILE"; then
    echo "" >> "$BPROFILE"
    cat "$HESTIA_HOME/deploy/bash_profile.kiosk" >> "$BPROFILE"
    echo "  appended startx hook to $BPROFILE"
  fi

  # Auto-login on tty1 so the bash_profile path runs at boot.
  GETTY_DIR="/etc/systemd/system/getty@tty1.service.d"
  GETTY_FILE="$GETTY_DIR/override.conf"
  if [[ ! -f "$GETTY_FILE" ]]; then
    echo "  enabling tty1 auto-login (sudo required)..."
    sudo mkdir -p "$GETTY_DIR"
    sudo tee "$GETTY_FILE" >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty -o '-p -f -- \\u' --noclear --autologin $USER_NAME %I \$TERM
EOF
    sudo systemctl daemon-reload
  fi
fi

# 3. Reload + enable.
echo
echo "[3/4] enabling hestia-kiosk.service..."
systemctl --user daemon-reload
systemctl --user enable hestia-kiosk.service || true

# 4. Status
echo
echo "[4/4] status"
echo
systemctl --user status hestia-kiosk.service --no-pager -l || true

echo
echo "Kiosk install complete."
if [[ "$resolved_mode" == "headless" ]]; then
  echo
  echo "  HEADLESS MODE: reboot to see the kiosk start on the attached display."
  echo "  After reboot, the Pi will auto-login on tty1 and launch X + Chromium."
else
  echo
  echo "  DESKTOP MODE: log out and log back in (or reboot) to start the kiosk."
fi
