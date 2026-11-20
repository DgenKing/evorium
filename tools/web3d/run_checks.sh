#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
node tests/world3d.test.mjs
.venv/bin/python -m pytest -q
node tests/map_view.test.cjs
.venv/bin/python tools/smoke_server.py > tools/web3d/raw/smoke.log 2>&1 &
smoke_pid=$!
trap 'kill "$smoke_pid" 2>/dev/null || true' EXIT
for attempt in {1..40}; do
 if curl -fsS http://127.0.0.1:8011/smoke/status > /dev/null 2>&1; then break; fi
 sleep .25
done
node tools/web3d/screenshots.mjs "$@"
python3 tools/web3d/check_screens.py
