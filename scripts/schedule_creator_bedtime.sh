#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

# Bedtime at 11:00 PM every day.
upsert_schedule '{
  "id": "bedtime-nightly",
  "name": "Bedtime",
  "scene_id": "bedtime",
  "time": "23:59",
  "enabled": true
}'
