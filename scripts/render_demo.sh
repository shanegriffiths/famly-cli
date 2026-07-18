#!/usr/bin/env bash
# Render scripts/demo.gif (and demo.mp4) with vhs.
# Starts the mock backend, waits for it, runs the tape, then stops the server.
# Requires: vhs (brew install vhs), SF Mono, and the project installed in .venv.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

pkill -f demo_server.py 2>/dev/null || true
sleep 0.5
FAMLY_DEMO_LOG="${FAMLY_DEMO_LOG:-}" python3 scripts/demo_server.py >/tmp/famly-demo-server.log 2>&1 &
SRV=$!
trap 'kill "$SRV" 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  curl -sk "https://localhost:8765/" >/dev/null 2>&1 && break
  sleep 0.25
done

vhs scripts/demo.tape
echo "Rendered scripts/demo.gif"
