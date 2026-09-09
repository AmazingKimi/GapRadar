#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DOCS="$ROOT/docs"
PORT="${GAPRADAR_PORT:-8000}"
URL="http://localhost:${PORT}/?v=$(date +%s)"

if [ ! -f "$DOCS/index.html" ]; then
  echo "GapRadar UI file is missing: $DOCS/index.html"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required only to serve the already-built static UI."
  exit 1
fi

# Stop only an existing listener on the selected port. This avoids stale pages
# and does not depend on GapRadar's Python package or virtual environment.
if command -v lsof >/dev/null 2>&1; then
  OLD_PIDS="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$OLD_PIDS" ]; then
    kill $OLD_PIDS 2>/dev/null || true
    sleep 1
  fi
else
  pkill -f "http.server $PORT" 2>/dev/null || true
fi

LOG="${TMPDIR:-/tmp}/gapradar-ui-${PORT}.log"
nohup python3 -m http.server "$PORT" --directory "$DOCS" >"$LOG" 2>&1 &
SERVER_PID=$!

READY=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    READY=1
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    break
  fi
  sleep 0.3
done

if [ "$READY" -ne 1 ]; then
  echo "GapRadar UI server failed to start. Log: $LOG"
  cat "$LOG" 2>/dev/null || true
  exit 1
fi

if [ "${GAPRADAR_NO_OPEN:-0}" != "1" ]; then
  if command -v open >/dev/null 2>&1; then
    open "$URL"
  else
    echo "$URL"
  fi
fi

echo "GapRadar UI is running: $URL"
echo "Server PID: $SERVER_PID"
echo "This launcher does not require Python 3.11, pip, or the .venv."
