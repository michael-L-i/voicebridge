---
name: jump-in
description: Interrupt an active Cadence Code conversation and add fresh spoken guidance to the current Codex or Antigravity task. Use only when the user explicitly invokes $jump-in or /jump-in after stopping the current host turn.
---

# Jump In

Use `mcp__cadence-code__voice_interrupt` to stop current Cadence Code audio and
capture one fresh spoken instruction. Cadence Code keeps its local speech models
loaded; this does not end the Cadence Code session. Antigravity may display the
tool as `voice_interrupt` under the `cadence-code` MCP server.

1. Call `mcp__cadence-code__voice_interrupt` immediately. Do not call
   `voice_start`, `voice_speak`, or ordinary `voice_listen` first.
2. If it returns `ok: false`, show the error. When there is no active session,
   tell the user to invoke `$start-talking` in Codex or `/start-talking` in
   Antigravity; do not start Cadence Code implicitly.
3. Treat every non-empty transcript as added guidance for the interrupted task,
   including one returned with `end_reason: "timeout"`. Continue from the
   current conversation and repository state without asking whether to resume.
   Follow the guidance normally when it redirects or replaces the earlier work.
4. If no speech is detected, leave the interrupted task stopped and report that
   no guidance was captured. Do not listen again automatically.
5. On `end_reason: "device_error"`, show the microphone problem and leave the
   Cadence Code session active so the user can retry or invoke `$wrap-up` or
   `/wrap-up`.
6. If the transcript clearly asks to end Cadence Code entirely, call
   `mcp__cadence-code__voice_stop` and do not resume the task.

After accepting added guidance, continue the normal Start Talking behavior:
work silently, then provide the concise spoken result and detailed written
result before listening for the next turn.
