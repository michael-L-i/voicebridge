#!/bin/bash
# Registered as Claude Code's SubagentStop hook (async: true). Same as
# on_stop.sh, but also forwards agent_id and narrates from the subagent's own
# transcript when available -- SubagentStop always narrates regardless of an
# active /voice-code session, since background subagents can't call
# voice_speak themselves.
set -euo pipefail

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')
AGENT_ID=$(echo "$INPUT" | jq -r '.agent_id // ""')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.agent_transcript_path // .transcript_path // ""')
CWD=$(echo "$INPUT" | jq -r '.cwd // ""')

curl -s -m 10 -X POST "http://127.0.0.1:8756/narrate" \
  -H "Content-Type: application/json" \
  -d "$(jq -n \
    --arg session_id "$SESSION_ID" \
    --arg agent_id "$AGENT_ID" \
    --arg transcript_path "$TRANSCRIPT_PATH" \
    --arg cwd "$CWD" \
    '{session_id: $session_id, event: "SubagentStop", agent_id: $agent_id, transcript_path: $transcript_path, cwd: $cwd}')" \
  >/dev/null 2>&1 || true
