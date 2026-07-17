---
description: Start an interactive voice conversation using voicebridge
---

You are entering an active voice conversation using the
`mcp__voicebridge__voice_status`, `mcp__voicebridge__voice_models`,
`mcp__voicebridge__voice_configure`, `mcp__voicebridge__voice_start`,
`mcp__voicebridge__voice_speak`, `mcp__voicebridge__voice_listen`, and
`mcp__voicebridge__voice_stop` tools.

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

1. Call `voice_status`. If `first_run` is true, call `voice_models` before any
   audio tool or model download. Present separate TTS and STT single-choice
   selectors using Claude Code's structured question UI when available, with a
   numbered conversational fallback. Preserve the lightest-to-heaviest order,
   show each option's tier and download size, and preselect the returned
   defaults (Qwen TTS and Whisper STT). If the user cancels, end without calling
   `voice_start`. Otherwise call `voice_configure` with both selected IDs.
   Existing users with `first_run: false` skip this onboarding choice.
2. Call `voice_start` and wait for the audio preflight and local speech
   models to load. If it returns `ok: false`, show the error to the user and end
   without retrying. A current runtime returns `version`, `host`, `capture`, and
   `preflight`, with `host: "claude-code"`. If a field is absent or the host is
   wrong, the MCP process survived a plugin update or is misconfigured: call
   `voice_stop`, tell the user to fully exit every Claude Code session using
   VoiceBridge and relaunch Claude Code, then end without starting a voice loop.
3. Once ready, call `voice_speak` with `listen_after: true` and a brief, casual
   one-sentence greeting, then call `voice_listen` immediately. VoiceBridge
   opens the mic as soon as playback finishes and the listen call collects that
   queued capture. Do not emit written filler, perform other work, or pause
   between those two tool calls.
4. Treat every non-empty transcript as the user's next instruction, including
   one returned with `end_reason: "timeout"`. Act on it with your normal tools.
5. For a request likely to take noticeable time, acknowledge it first with one
   natural sentence such as "Got it, I'll check that now." Keep `listen_after`
   false for this progress update, then do the work silently. Do not narrate
   individual commands, file reads, or reasoning.
6. When the work is done, call `voice_speak` first with `listen_after: true` and
   an independently composed summary. As soon as it returns, present the
   complete written result while that summary is still playing so text appears
   as the user listens. VoiceBridge will open the mic immediately when playback
   ends even if the written result is still streaming; call `voice_listen`
   after the written result to collect that capture. Give the overarching
   outcome, important caveat, or next decision like a colleague would; do not
   include code, bullet lists, or file paths.
7. If the user asks for a summary, compose both versions, call `voice_speak`
   with `listen_after: true` and the natural condensed version first, then
   immediately stream the useful detailed written summary while it plays. Do
   not explain how VoiceBridge creates spoken summaries unless the user
   specifically asks about VoiceBridge itself.
8. When you need a decision, put any detailed options on screen and speak only
   the concise question and the most important tradeoff, with `listen_after:
   true`.
9. After presenting any written result, call `voice_listen` to collect the
   capture queued by the preceding end-of-turn speech and continue the
   conversation.
10. VoiceBridge internally discards noise segments that transcribe to no words.
   If `voice_listen` still returns `speech_detected: false` with `end_reason:
   "timeout"`, check in once. After two consecutive no-speech timeouts, call
   `voice_stop` and end quietly. A successful transcript resets this count.
11. If `end_reason` is `"device_error"`, briefly explain the microphone problem
   via `voice_speak` when possible, call `voice_stop`, and end.
12. If the transcript clearly means "stop", "that's all", "goodbye", or similar,
   speak a short goodbye with `listen_after` false, call `voice_stop`, and do
   not listen again.
13. If `voice_speak` or `voice_listen` returns `ok: false`, show its error on
    screen, call `voice_stop`, and end rather than retrying indefinitely.

Keep speech brief, direct, and conversational. `voice_speak` says your text
verbatim, meaning it speaks the condensed audio summary you deliberately give
it, not the full written response. If the user explicitly asks for a spoken
walkthrough, use a little more detail while keeping it natural. Once
`voice_start` succeeds, call `voice_stop` exactly once at the end, never between
turns.
