# Shared helpers for scene/schedule scripts. Source this from sibling scripts.
#
# Usage in a sibling script:
#
#   #!/usr/bin/env bash
#   set -euo pipefail
#   source "$(dirname "$0")/_lib.sh"
#   upsert_scene '{ "id": "wakeup", "name": "Wakeup", ... }'

# Override with HESTIA_HOST=http://hera:8000 etc.
HESTIA_HOST="${HESTIA_HOST:-http://localhost:8000}"

_log() {
  printf '%s\n' "$*" >&2
}

_curl() {
  # quiet curl that fails the script on non-2xx responses and prints the
  # body on stdout. Use for both writes (POST/PUT/PATCH) and reads (GET).
  local out status
  out=$(mktemp)
  status=$(curl -sS -o "$out" -w '%{http_code}' "$@") || {
    _log "curl failed: $*"
    rm -f "$out"
    return 1
  }
  cat "$out"
  rm -f "$out"
  if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
    _log "HTTP $status from $*"
    return 1
  fi
}

# ---- scenes ---------------------------------------------------------------

upsert_scene() {
  # Create if missing, replace if it exists. Takes one JSON arg.
  local body="$1"
  local id
  id=$(printf '%s' "$body" | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')
  if _curl -o /dev/null "${HESTIA_HOST}/scenes/${id}" >/dev/null 2>&1; then
    _log "updating scene ${id}"
    _curl -X PUT "${HESTIA_HOST}/scenes/${id}" \
      -H 'Content-Type: application/json' -d "$body"
  else
    _log "creating scene ${id}"
    _curl -X POST "${HESTIA_HOST}/scenes/" \
      -H 'Content-Type: application/json' -d "$body"
  fi
  echo
}

delete_scene() {
  local id="$1"
  _log "deleting scene ${id}"
  _curl -X DELETE "${HESTIA_HOST}/scenes/${id}"
}

execute_scene() {
  local id="$1"
  _log "executing scene ${id}"
  _curl -X POST "${HESTIA_HOST}/scenes/${id}/execute"
  echo
}

list_scenes() {
  _curl "${HESTIA_HOST}/scenes/"
  echo
}

# ---- schedules ------------------------------------------------------------

upsert_schedule() {
  local body="$1"
  local id
  id=$(printf '%s' "$body" | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')
  # PATCH is the documented update path for schedules; POST creates.
  if _curl -o /dev/null -X GET "${HESTIA_HOST}/schedules/" 2>/dev/null \
       | python3 -c "import json,sys; ids={s['id'] for s in json.load(sys.stdin)}; sys.exit(0 if '${id}' in ids else 1)"; then
    _log "updating schedule ${id}"
    _curl -X PATCH "${HESTIA_HOST}/schedules/${id}" \
      -H 'Content-Type: application/json' -d "$body"
  else
    _log "creating schedule ${id}"
    _curl -X POST "${HESTIA_HOST}/schedules/" \
      -H 'Content-Type: application/json' -d "$body"
  fi
  echo
}

delete_schedule() {
  local id="$1"
  _log "deleting schedule ${id}"
  _curl -X DELETE "${HESTIA_HOST}/schedules/${id}"
}

list_schedules() {
  _curl "${HESTIA_HOST}/schedules/"
  echo
}
