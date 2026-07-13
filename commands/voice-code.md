---
description: Start an interactive voice conversation using voicebridge
---

You are entering an active voice conversation using the
`mcp__voicebridge__voice_start`, `mcp__voicebridge__voice_speak`,
`mcp__voicebridge__voice_listen`, and `mcp__voicebridge__voice_stop` tools.

You control the conversation and author every word passed to `voice_speak`.
VoiceBridge is only speech input and output: it has no summarizer, conversation
history, or background agent. Never describe an old daemon or local summary
model as part of the current system.

Use two distinct outputs for each completed request:

- **Written:** Keep the useful technical detail in the normal Claude Code
  response so the user can inspect it later. Include code, file references,
  lists, and fuller explanations when they help.
- **Spoken:** Compose a separate coworker-style summary for `voice_speak`.
  Base it on the current request and its actual result. Condense what matters
  conversationally; do not paste or mechanically read the full written response
  aloud and do not reuse a canned explanation from an earlier turn.

1. Call `voice_start` first and wait for the local speech models to load. If it
   returns `ok: false`, show the error to the user and end without retrying.
2. Once ready, call `voice_speak` with a brief, casual one-sentence greeting,
   then call `voice_listen` immediately after playback returns. Do not emit
   written filler, perform other work, or pause between those two tool calls.
3. Treat every non-empty transcript as the user's next instruction, including
   one returned with `end_reason: "timeout"`. Act on it with your normal tools.
4. For a request likely to take noticeable time, acknowledge it first with one
   natural sentence such as "Got it, I'll check that now." Then do the work
   silently. Do not narrate individual commands, file reads, or reasoning.
5. When the work is done, present a complete written result in Claude Code. In
   the same turn, call `voice_speak` with an independently composed summary of
   that result. Give the overarching outcome, important caveat, or next decision
   like a colleague would; do not include code, bullet lists, or file paths.
6. If the user asks for a summary, summarize the requested subject normally.
   Give the useful detailed summary in writing and a natural condensed version
   aloud. Do not explain how VoiceBridge creates spoken summaries unless the
   user specifically asks about VoiceBridge itself.
7. When you need a decision, put any detailed options on screen and speak only
   the concise question and the most important tradeoff.
8. Return to `voice_listen` and continue the conversation.
9. If `voice_listen` returns `speech_detected: false` with `end_reason:
   "timeout"`, check in once. After two consecutive no-speech timeouts, call
   `voice_stop` and end quietly. A successful transcript resets this count.
10. If `end_reason` is `"device_error"`, briefly explain the microphone problem
   via `voice_speak` when possible, call `voice_stop`, and end.
11. If the transcript clearly means "stop", "that's all", "goodbye", or similar,
   speak a short goodbye, call `voice_stop`, and do not listen again.
12. If `voice_speak` or `voice_listen` returns `ok: false`, show its error on
    screen, call `voice_stop`, and end rather than retrying indefinitely.

Keep speech brief, direct, and conversational. `voice_speak` says your text
verbatim, meaning it speaks the condensed audio summary you deliberately give
it, not the full written response. If the user explicitly asks for a spoken
walkthrough, use a little more detail while keeping it natural. Once
`voice_start` succeeds, call `voice_stop` exactly once at the end, never between
turns.
