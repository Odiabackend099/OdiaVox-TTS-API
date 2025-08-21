#!/usr/bin/env bash
set -euo pipefail
KEY="${1:-}"; [[ -z "$KEY" ]] && { echo "Usage: ./scripts/smoke.sh <x-api-key>"; exit 1; }
curl -sSf "http://127.0.0.1:5000/speak?text=Hello%20Naija" -H "x-api-key: $KEY" -o /tmp/odiadev_smoke.wav
( command -v open >/dev/null && open /tmp/odiadev_smoke.wav ) || ( command -v xdg-open >/dev/null && xdg-open /tmp/odiadev_smoke.wav ) || true
