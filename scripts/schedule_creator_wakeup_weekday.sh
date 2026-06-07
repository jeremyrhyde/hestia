#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

# Wakeup at 7:00 AM, weekdays only.
# Time format: "HH:MM" 24-hour local time.
# Days: omit for every day, or list lowercase 3-letter abbrevs.
upsert_schedule '{
  "id": "wakeup-weekdays",
  "name": "Wakeup (weekdays)",
  "scene_id": "wakeup",
  "time": "07:45",
  "days": ["mon", "tue", "wed", "thu", "fri"],
  "enabled": true
}'
