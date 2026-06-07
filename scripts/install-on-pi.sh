#!/usr/bin/env bash
# Install Hestia on a Raspberry Pi.
#
# Detects whether the system has a graphical session, installs the
# appropriate systemd user services, optionally bootstraps a minimal X
# stack for headless installs, and starts everything.
#
# RECOMMENDED BASE OS: Raspberry Pi OS Lite (headless, no desktop). It ships
# no display system, so --headless mode adds only a bare X stack + Chromium
# — far lighter on a 2-4GB Pi 4 than a full desktop. Ubuntu Server also
# works via the same --headless path.
#
# Usage:
#   ./scripts/install-on-pi.sh                  # auto-detect mode
#   ./scripts/install-on-pi.sh --desktop        # force desktop-session mode
#   ./scripts/install-on-pi.sh --headless       # force headless (Pi OS Lite / Ubuntu Server)
#   ./scripts/install-on-pi.sh --no-kiosk       # only install the server, skip the kiosk
#   ./scripts/install-on-pi.sh --uninstall      # remove all installed units
#
# Idempotent — running it twice is safe.

set -euo pipefail

# --- args ------------------------------------------------------------------

MODE="auto"
INSTALL_KIOSK=1
ACTION="install"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --desktop)   MODE="desktop"; shift ;;
    --headless)  MODE="headless"; shift ;;
    --no-kiosk)  INSTALL_KIOSK=0; shift ;;
    --uninstall) ACTION="uninstall"; shift ;;
    -h|--help)   sed -n '3,15p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# --- paths -----------------------------------------------------------------

HESTIA_HOME="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
USER_HOME="$HOME"
SYSTEMD_USER_DIR="$USER_HOME/.config/systemd/user"

# Find uv (we don't assume it's in PATH for systemd, which has minimal env).
UV_BIN="$(command -v uv || true)"
if [[ -z "$UV_BIN" ]]; then
  if [[ -x "$USER_HOME/.local/bin/uv" ]]; then
    UV_BIN="$USER_HOME/.local/bin/uv"
  elif [[ -x "$USER_HOME/.cargo/bin/uv" ]]; then
    UV_BIN="$USER_HOME/.cargo/bin/uv"
  else
    echo "ERROR: 'uv' not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
  fi
fi

echo "Hestia install"
echo "  HESTIA_HOME = $HESTIA_HOME"
echo "  USER        = $USER_NAME"
echo "  UV_BIN      = $UV_BIN"

# --- helpers ---------------------------------------------------------------

render_unit() {
  # render_unit <src> <dest>  →  copy with @HESTIA_HOME@/@UV_BIN@ rewritten.
  local src="$1" dest="$2"
  sed \
    -e "s|@HESTIA_HOME@|$HESTIA_HOME|g" \
    -e "s|@UV_BIN@|$UV_BIN|g" \
    "$src" > "$dest"
}

ensure_apt_packages() {
  # ensure_apt_packages [--no-recommends] <pkg>...
  #
  # On a RAM-constrained kiosk Pi we install the X stack with
  # --no-install-recommends so apt does NOT pull in the dozens of
  # "recommended" desktop packages (fonts, GTK themes, printing,
  # accessibility daemons) that a bare xserver-xorg would otherwise drag
  # in. This is the single biggest disk/RAM win on Raspberry Pi OS Lite.
  local apt_opts=()
  if [[ "${1:-}" == "--no-recommends" ]]; then
    apt_opts+=(--no-install-recommends)
    shift
  fi
  local pkgs=("$@")
  local missing=()
  for p in "${pkgs[@]}"; do
    if ! dpkg -s "$p" >/dev/null 2>&1; then
      missing+=("$p")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "  installing apt packages: ${missing[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y "${apt_opts[@]}" "${missing[@]}"
  fi
}

# --- mode detection --------------------------------------------------------

detect_mode() {
  if [[ "$MODE" != "auto" ]]; then
    echo "$MODE"; return
  fi
  # If a graphical target exists and is the default, treat as desktop.
  if systemctl get-default 2>/dev/null | grep -q graphical; then
    echo "desktop"
  elif [[ -n "${DISPLAY:-}" ]]; then
    echo "desktop"
  else
    echo "headless"
  fi
}

# --- uninstall -------------------------------------------------------------

if [[ "$ACTION" == "uninstall" ]]; then
  echo "Uninstalling Hestia user services..."
  systemctl --user disable --now hestia.service 2>/dev/null || true
  systemctl --user disable --now hestia-kiosk.service 2>/dev/null || true
  rm -f "$SYSTEMD_USER_DIR/hestia.service" \
        "$SYSTEMD_USER_DIR/hestia-kiosk.service"
  systemctl --user daemon-reload || true
  echo "Done. Linger / .bash_profile changes left in place — remove manually if desired."
  exit 0
fi

# --- install ---------------------------------------------------------------

mkdir -p "$SYSTEMD_USER_DIR"

# 1. uv sync — make sure the venv is built.
echo
echo "[1/6] uv sync..."
( cd "$HESTIA_HOME" && "$UV_BIN" sync )

# 2. Install hestia.service.
echo
echo "[2/6] writing hestia.service..."
render_unit "$HESTIA_HOME/deploy/hestia.service" \
            "$SYSTEMD_USER_DIR/hestia.service"

# 3. Install kiosk if requested.
if [[ "$INSTALL_KIOSK" -eq 1 ]]; then
  echo
  echo "[3/6] writing hestia-kiosk.service..."
  render_unit "$HESTIA_HOME/web/kiosk/hestia-kiosk.service" \
              "$SYSTEMD_USER_DIR/hestia-kiosk.service"
  chmod +x "$HESTIA_HOME/web/kiosk/start-kiosk.sh"
else
  echo
  echo "[3/6] skipping kiosk (--no-kiosk)"
fi

# 4. Install kiosk dependencies (chromium + unclutter, plus X stack if headless).
if [[ "$INSTALL_KIOSK" -eq 1 ]]; then
  echo
  echo "[4/6] installing kiosk dependencies..."
  KIOSK_PKGS=(unclutter)
  # Chromium package name varies: Pi OS Bullseye uses `chromium-browser`,
  # while Bookworm-based Pi OS and Ubuntu provide `chromium`. Only add a
  # package if no chromium binary is already present, and pick whichever
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
fi

# 5. Reload + enable.
echo
echo "[5/6] enabling services..."
systemctl --user daemon-reload
systemctl --user enable --now hestia.service
if [[ "$INSTALL_KIOSK" -eq 1 ]]; then
  systemctl --user enable hestia-kiosk.service || true
fi

# Linger so the server starts at boot without an interactive login.
if ! loginctl show-user "$USER_NAME" 2>/dev/null | grep -q '^Linger=yes'; then
  echo "  enabling linger (sudo required)..."
  sudo loginctl enable-linger "$USER_NAME"
fi

# 6. Status
echo
echo "[6/6] status"
echo
systemctl --user status hestia.service --no-pager -l || true
if [[ "$INSTALL_KIOSK" -eq 1 ]]; then
  echo
  systemctl --user status hestia-kiosk.service --no-pager -l || true
fi

echo
echo "Install complete."
echo "  Server: http://$(hostname -I | awk '{print $1}'):8000/ui/"
echo "  Logs:   journalctl --user -u hestia.service -f"
if [[ "$INSTALL_KIOSK" -eq 1 ]]; then
  resolved_mode="$(detect_mode)"
  if [[ "$resolved_mode" == "headless" ]]; then
    echo
    echo "  HEADLESS MODE: reboot to see the kiosk start on the attached display."
    echo "  After reboot, the Pi will auto-login on tty1 and launch X + Chromium."
  else
    echo
    echo "  DESKTOP MODE: log out and log back in (or reboot) to start the kiosk."
  fi
fi
