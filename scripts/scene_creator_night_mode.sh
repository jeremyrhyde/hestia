#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

# Dim living-room bulbs to 20%, kill the kitchen, leave bedroom alone.
#
# `set_brightness` is a StandardAction. It requires a `params.level` from
# 0-100. The Kasa driver advertises this through the `dimmer` capability,
# which `kitchen-light`, `living-room-light-1`, and `living-room-light-2`
# all have (`bedroom-light` is a plug — toggle only, no dimming).
upsert_scene '{
  "id": "night-mode",
  "name": "Night Mode",
  "description": "Ultra-dim setting",
  "actions": [
     { "device_id": "living-room-light",       "action": "set_brightness", "params": { "level": 20 } },
    { "device_id": "kitchen-light",       "action": "set_brightness", "params": { "level": 20 } }
  ]
}'
