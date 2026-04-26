#!/usr/bin/env bash
# Annotated curl smoke-tests for the Hestia REST surface.
#
# Each section starts with `# DESCRIPTION` and a curl command. The script
# is meant to be read top-to-bottom while the server is running, but it
# can also be run end-to-end:
#
#   make run                       # in another terminal
#   bash tests/api_curl_tests.sh   # walks through every endpoint
#
# It chains meaningfully: list scenes -> create one -> execute it ->
# delete it. Adjust HOST below if the server is bound elsewhere.

set -euo pipefail

HOST="${HOST:-http://localhost:8000}"
DEVICE_ID="${DEVICE_ID:-dev-a}"   # change to a real ID on the Pi
SCENE_ID="curl-smoke"
SCHEDULE_ID="curl-smoke-sched"

heading() {
    echo ""
    echo "============================================================"
    echo "  $1"
    echo "============================================================"
}

# DESCRIPTION: confirm the server is alive and report device boot status.
heading "GET /health"
curl -fsS "$HOST/health" | jq .

# DESCRIPTION: list every device registered by main.py at startup.
heading "GET /devices/"
curl -fsS "$HOST/devices/" | jq .

# DESCRIPTION: fetch a single device by ID. 404 if unknown.
heading "GET /devices/$DEVICE_ID"
curl -fsS "$HOST/devices/$DEVICE_ID" | jq . || echo "(skipping — set DEVICE_ID to a real device)"

# DESCRIPTION: turn the device on.
heading "POST /devices/$DEVICE_ID/action  (turn_on)"
curl -fsS -X POST "$HOST/devices/$DEVICE_ID/action" \
    -H "Content-Type: application/json" \
    -d '{"action":"turn_on"}' | jq . || echo "(skipping — set DEVICE_ID)"

# DESCRIPTION: turn the device off.
heading "POST /devices/$DEVICE_ID/action  (turn_off)"
curl -fsS -X POST "$HOST/devices/$DEVICE_ID/action" \
    -H "Content-Type: application/json" \
    -d '{"action":"turn_off"}' | jq . || echo "(skipping — set DEVICE_ID)"

# DESCRIPTION: list scenes (probably empty on a fresh DB).
heading "GET /scenes/  (before create)"
curl -fsS "$HOST/scenes/" | jq .

# DESCRIPTION: create a scene that toggles two devices on.
heading "POST /scenes/  (create $SCENE_ID)"
curl -fsS -X POST "$HOST/scenes/" \
    -H "Content-Type: application/json" \
    -d "$(cat <<JSON
{
  "id": "$SCENE_ID",
  "name": "Curl smoke scene",
  "description": "two-device turn_on used by api_curl_tests.sh",
  "actions": [
    {"device_id": "$DEVICE_ID", "action": "turn_on"}
  ]
}
JSON
)" | jq .

# DESCRIPTION: read it back to confirm persistence.
heading "GET /scenes/$SCENE_ID"
curl -fsS "$HOST/scenes/$SCENE_ID" | jq .

# DESCRIPTION: trigger the scene. Returns a per-action result list.
heading "POST /scenes/$SCENE_ID/execute"
curl -fsS -X POST "$HOST/scenes/$SCENE_ID/execute" | jq .

# DESCRIPTION: clean up.
heading "DELETE /scenes/$SCENE_ID"
curl -fsS -X DELETE "$HOST/scenes/$SCENE_ID" -o /dev/null -w "HTTP %{http_code}\n"

# DESCRIPTION: list schedules (empty on fresh DB).
heading "GET /schedules/  (before create)"
curl -fsS "$HOST/schedules/" | jq .

# DESCRIPTION: create a schedule pointing at the (now-deleted) scene —
# good enough for CRUD smoke; the scheduler logs an error when it fires
# referring to a missing scene but does not crash.
heading "POST /schedules/  (create $SCHEDULE_ID)"
curl -fsS -X POST "$HOST/schedules/" \
    -H "Content-Type: application/json" \
    -d "$(cat <<JSON
{
  "id": "$SCHEDULE_ID",
  "name": "Curl smoke schedule",
  "scene_id": "$SCENE_ID",
  "time": "23:59",
  "days": ["mon","tue","wed","thu","fri","sat","sun"],
  "enabled": true
}
JSON
)" | jq .

# DESCRIPTION: PATCH to flip enabled off — primary use case for the touchscreen.
heading "PATCH /schedules/$SCHEDULE_ID  (disable)"
curl -fsS -X PATCH "$HOST/schedules/$SCHEDULE_ID" \
    -H "Content-Type: application/json" \
    -d '{"enabled": false}' | jq .

# DESCRIPTION: clean up.
heading "DELETE /schedules/$SCHEDULE_ID"
curl -fsS -X DELETE "$HOST/schedules/$SCHEDULE_ID" -o /dev/null -w "HTTP %{http_code}\n"

# DESCRIPTION: error path — 404 for unknown device.
heading "GET /devices/does-not-exist  (expect 404)"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "$HOST/devices/does-not-exist"

# DESCRIPTION: error path — 422 for malformed action body.
heading "POST /devices/$DEVICE_ID/action  (bad body, expect 422)"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
    -X POST "$HOST/devices/$DEVICE_ID/action" \
    -H "Content-Type: application/json" \
    -d '{"foo":"bar"}'

heading "Done."
