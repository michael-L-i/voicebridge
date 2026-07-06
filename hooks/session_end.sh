#!/bin/bash
# SessionEnd hook. Safety net for the case where a /voice-code conversation
# ends by just closing the terminal (no "goodbye" -> no voice_stop call) --
# stops the daemon so its several-GB MLX models don't stay resident forever.
# Not -e: a missing pidfile / an already-dead pid is a normal no-op, not an
# error worth failing this hook over.
set -uo pipefail

PID_FILE="${CLAUDE_PLUGIN_DATA}/daemon.pid"
[ -f "$PID_FILE" ] || exit 0

PID=$(cat "$PID_FILE" 2>/dev/null || true)
if [ -z "$PID" ]; then
  rm -f "$PID_FILE"
  exit 0
fi

if kill -0 "$PID" 2>/dev/null; then
  kill -TERM "$PID" 2>/dev/null || true
fi
rm -f "$PID_FILE"
exit 0
