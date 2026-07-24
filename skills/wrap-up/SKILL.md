---
name: wrap-up
description: End an active Cadence Code conversation cleanly and release its local speech models. Use only when the user explicitly invokes $wrap-up, /wrap-up, or asks to wrap up the voice conversation.
disable-model-invocation: true
---

# Wrap Up

Use `mcp__cadence-code__voice_status`,
`mcp__cadence-code__voice_speak`, and
`mcp__cadence-code__voice_stop` to end the current conversation.
Cursor and Antigravity may display these as the corresponding `voice_status`,
`voice_speak`, and `voice_stop` tools under the `cadence-code` MCP server.

1. Call `mcp__cadence-code__voice_status`.
2. If `ready` is false, say there is no active Cadence Code conversation to
   wrap up. Do not call `voice_start`, `voice_speak`, `voice_listen`, or
   `voice_stop`.
3. If `ready` is true, call `mcp__cadence-code__voice_speak` with a brief,
   natural goodbye and `listen_after: false`.
4. Call `mcp__cadence-code__voice_stop` exactly once with
   `wait_for_speech: true`. Do not listen again.
5. Confirm briefly that the conversation ended and its local speech models were
   released. If the goodbye fails, still call `voice_stop` once to clean up,
   then show the error.

Do not start a new conversation, ask for confirmation, or do additional task
work from this skill.
