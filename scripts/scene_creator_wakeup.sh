#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

# Force bulbs to full brightness in case a prior dim scene (e.g. Movie)
# left them at 20%. `set_brightness` with level=100 both turns the bulb
# on AND sets it to full — no separate turn_on needed.
#
# `bedroom-light` is a Kasa plug (no DIMMER capability), so it only
# accepts toggle verbs — `turn_on` is the right action there.
upsert_scene '{
  "id": "wakeup",
  "name": "Wakeup",
  "description": "Turn on lights at full brightness",
  "actions": [
    { "device_id": "kitchen-light",       "action": "set_brightness", "params": { "level": 100 } },
    { "device_id": "living-room-light", "action": "set_brightness", "params": { "level": 100 }, "delay_ms": 2000 }
  ]
}'
