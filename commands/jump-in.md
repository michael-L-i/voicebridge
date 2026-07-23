---
description: Jump In and add spoken guidance
---

Interrupt the current Cadence Code audio and collect one fresh spoken
instruction with `mcp__cadence-code__voice_interrupt`. This command is intended
to be invoked after the user presses Escape to stop the current Claude Code
turn.

1. Call `mcp__cadence-code__voice_interrupt` immediately. Do not call
   `voice_start`, `voice_speak`, or ordinary `voice_listen` first.
2. If it returns `ok: false`, show the error. If Cadence Code is inactive, tell
   the user to run `/cadence-code:start-talking`; do not start it implicitly.
3. Treat every non-empty transcript as added guidance for the interrupted task,
   including one returned with `end_reason: "timeout"`. Continue from current
   conversation and repository state without asking whether to resume. If the
   guidance redirects or replaces the work, follow it normally.
4. If no speech is detected, leave the interrupted task stopped, report that no
   guidance was captured, and do not listen again automatically.
5. On `end_reason: "device_error"`, show the microphone problem and leave
   Cadence Code active so the user can retry or run `/cadence-code:wrap-up`.
6. If the transcript clearly asks to end Cadence Code entirely, call
   `mcp__cadence-code__voice_stop` and do not resume the task.

After accepting the guidance, continue the normal Cadence Code workflow: work
silently, then provide the concise spoken result and detailed written result
before listening for the next turn.
