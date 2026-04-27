#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

upsert_scene '{
  "id": "bedtime",
  "name": "Bedtime",
  "description": "Turn off lights",
  "actions": [
    { "device_id": "ceiling-light",       "action": "turn_off"},
    { "device_id": "upstairs-light",       "action": "turn_off", "delay_ms": 500},
    { "device_id": "living-room-light",   "action": "turn_off", "delay_ms": 500},
    { "device_id": "kitchen-light",       "action": "turn_off", "delay_ms": 500}
  ]
}'
