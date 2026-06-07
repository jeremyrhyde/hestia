#!/usr/bin/env bash
# Shared setup + helpers for the Hestia Pi install scripts.
#
# This file is meant to be *sourced*, not executed:
#   source "$(dirname "$0")/_pi-common.sh"
#
# It resolves paths, locates `uv`, and defines render_unit /
# ensure_apt_packages / detect_mode used by both install-server-on-pi.sh
# and install-kiosk-on-pi.sh. Sourcing it keeps the two scripts in sync
# without duplicating this logic.

# --- paths -----------------------------------------------------------------

# $1 is the calling script's path ($0); derive HESTIA_HOME from it.
HESTIA_HOME="$(cd "$(dirname "${BASH_SOURCE[1]}")/.." && pwd)"
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
  # Echoes "desktop" or "headless". Honors a caller-set $MODE override
  # (anything other than "auto"); otherwise auto-detects.
  if [[ "${MODE:-auto}" != "auto" ]]; then
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
