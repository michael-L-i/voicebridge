---
description: Start an interactive voice conversation using voicebridge
---

You are entering an active voice conversation using the
`mcp__voicebridge__voice_start`, `mcp__voicebridge__voice_speak`,
`mcp__voicebridge__voice_listen`, and `mcp__voicebridge__voice_stop` tools.

1. Call `voice_start` first and wait for the local speech models to load. If it
   returns `ok: false`, show the error to the user and end without retrying.
2. Once ready, call `voice_speak` with a brief, casual one-sentence greeting,
   then call `voice_listen`.
3. Treat every non-empty transcript as the user's next instruction, including
   one returned with `end_reason: "timeout"`. Act on it with your normal tools.
4. For a request likely to take noticeable time, acknowledge it first with one
   natural sentence such as "Got it, I'll check that now." Then do the work
   silently. Do not narrate individual commands, file reads, or reasoning.
5. When the work is done, or when you need a decision, call `voice_speak` with
   the exact short response the user should hear. Give the gist like a colleague,
   not a screen report. Do not include code, bullet lists, or file paths.
6. Return to `voice_listen` and continue the conversation.
7. If `voice_listen` returns `speech_detected: false` with `end_reason:
   "timeout"`, check in once. After two consecutive no-speech timeouts, call
   `voice_stop` and end quietly. A successful transcript resets this count.
8. If `end_reason` is `"device_error"`, briefly explain the microphone problem
   via `voice_speak` when possible, call `voice_stop`, and end.
9. If the transcript clearly means "stop", "that's all", "goodbye", or similar,
   speak a short goodbye, call `voice_stop`, and do not listen again.
10. If `voice_speak` or `voice_listen` returns `ok: false`, show its error on
    screen, call `voice_stop`, and end rather than retrying indefinitely.

Keep speech brief, direct, and conversational. `voice_speak` says your text
verbatim; compose it deliberately. Once `voice_start` succeeds, call
`voice_stop` exactly once at the end, never between turns.
