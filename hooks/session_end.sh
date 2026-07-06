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
  # Escalate to SIGKILL if it's still alive after a short grace period. A
  # daemon wedged inside a blocking mic read (e.g. the Mac went to sleep
  # mid-listen) won't respond to SIGTERM at all -- observed running for
  # hours in practice -- since uvicorn's graceful shutdown waits for
  # in-flight requests to finish before exiting. Without this escalation
  # this hook is not actually a reliable safety net.
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.2
  done
  kill -0 "$PID" 2>/dev/null && kill -KILL "$PID" 2>/dev/null || true
fi
rm -f "$PID_FILE"
exit 0
