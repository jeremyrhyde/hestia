#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

upsert_scene '{
  "id": "bedtime",
  "name": "Bedtime",
  "description": "Turn off lights",
  "actions": [
    { "device_id": "kitchen-light",       "action": "turn_off" },
    { "device_id": "living-room-light-1", "action": "turn_off", "delay_ms": 2000 },
    { "device_id": "living-room-light-2", "action": "turn_off" },
    { "device_id": "bedroom-light",       "action": "turn_off", "delay_ms": 2000 }
  ]
}'
