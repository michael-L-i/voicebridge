#!/bin/bash
# Registered as Claude Code's Stop hook (async: true, so this never blocks the
# agent). Reads the hook payload from stdin, forwards it to the voicebridge
# daemon's /narrate endpoint. Errors are swallowed -- a dead/unreachable
# daemon should never surface as a Claude Code problem.
set -euo pipefail

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""')
CWD=$(echo "$INPUT" | jq -r '.cwd // ""')

curl -s -m 10 -X POST "http://127.0.0.1:8756/narrate" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg session_id "$SESSION_ID" \
    --arg transcript_path "$TRANSCRIPT_PATH" \
    --arg cwd "$CWD" \
    '{session_id: $session_id, event: "Stop", transcript_path: $transcript_path, cwd: $cwd}')" \
  >/dev/null 2>&1 || true
