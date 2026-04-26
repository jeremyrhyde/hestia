#!/usr/bin/env bash
# Generic CLI for inspecting and editing scenes & schedules without
# writing per-action shell scripts. For one-off operations like
# "what's there?", "delete this old scene", "fire bedtime now".
#
# Usage:
#   ./scripts/automation.sh scenes list
#   ./scripts/automation.sh scenes show <id>
#   ./scripts/automation.sh scenes delete <id>
#   ./scripts/automation.sh scenes run <id>
#   ./scripts/automation.sh schedules list
#   ./scripts/automation.sh schedules show <id>
#   ./scripts/automation.sh schedules delete <id>
#   ./scripts/automation.sh schedules toggle <id>          # flip enabled
#   ./scripts/automation.sh schedules enable <id>
#   ./scripts/automation.sh schedules disable <id>
#
# All output is JSON (piped through `python3 -m json.tool` if available
# for readability). Override the host with HESTIA_HOST=...

set -euo pipefail
source "$(dirname "$0")/_lib.sh"

_pretty() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -m json.tool 2>/dev/null || cat
  else
    cat
  fi
}

usage() {
  sed -n '3,21p' "$0" | sed 's/^# \?//'
  exit 1
}

set_schedule_enabled() {
  local id="$1" enabled="$2"
  _curl -X PATCH "${HESTIA_HOST}/schedules/${id}" \
    -H 'Content-Type: application/json' \
    -d "{\"enabled\": ${enabled}}"
  echo
}

main() {
  local resource="${1:-}" verb="${2:-}" id="${3:-}"
  [[ -z "$resource" || -z "$verb" ]] && usage

  case "$resource:$verb" in
    scenes:list)       list_scenes | _pretty ;;
    scenes:show)       [[ -z "$id" ]] && usage
                       _curl "${HESTIA_HOST}/scenes/${id}" | _pretty ;;
    scenes:delete)     [[ -z "$id" ]] && usage
                       delete_scene "$id" ;;
    scenes:run|scenes:execute)
                       [[ -z "$id" ]] && usage
                       execute_scene "$id" | _pretty ;;
    schedules:list)    list_schedules | _pretty ;;
    schedules:show)    [[ -z "$id" ]] && usage
                       # No GET /schedules/{id} endpoint; filter list.
                       list_schedules \
                         | python3 -c "import json,sys;[print(json.dumps(s,indent=2)) for s in json.load(sys.stdin) if s['id']=='${id}']" ;;
    schedules:delete)  [[ -z "$id" ]] && usage
                       delete_schedule "$id" ;;
    schedules:enable)  [[ -z "$id" ]] && usage
                       set_schedule_enabled "$id" true | _pretty ;;
    schedules:disable) [[ -z "$id" ]] && usage
                       set_schedule_enabled "$id" false | _pretty ;;
    schedules:toggle)  [[ -z "$id" ]] && usage
                       current=$(list_schedules \
                         | python3 -c "import json,sys;print([s['enabled'] for s in json.load(sys.stdin) if s['id']=='${id}'][0])")
                       new=$([[ "$current" == "True" ]] && echo false || echo true)
                       set_schedule_enabled "$id" "$new" | _pretty ;;
    *) usage ;;
  esac
}

main "$@"
