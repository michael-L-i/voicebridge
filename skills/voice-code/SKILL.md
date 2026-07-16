---
name: voice-code
description: Start and run an explicit, interactive VoiceBridge conversation with Codex using fully local speech input and output. Use only when the user explicitly invokes $voice-code or asks to start a VoiceBridge voice conversation.
---

# Voice Code

Run a deliberate voice loop through the `mcp__voicebridge__voice_start`,
`mcp__voicebridge__voice_speak`, `mcp__voicebridge__voice_listen`, and
`mcp__voicebridge__voice_stop` tools. VoiceBridge only performs speech input and
output. Codex controls the conversation and authors every word sent to speech.

Maintain two outputs for completed work:

- Keep useful technical detail in the normal written Codex response.
- Compose a separate short, conversational summary for `voice_speak`. Never
  read code, file paths, bullet lists, or the full written response aloud.

1. Call `voice_start` and wait for the audio preflight and local speech models.
   Do not call any VoiceBridge audio tool before this explicit skill invocation.
   If it returns `ok: false`, show the error and end without retrying.
2. Verify the result includes `version`, `host`, `capture`, and `preflight`, and
   that `host` is `codex`. If not, the MCP process is stale or misconfigured:
   call `voice_stop`, ask the user to start a new Codex session after updating
   or reinstalling the plugin, and end.
3. Speak a brief one-sentence greeting with `listen_after: true`, then call
   `voice_listen` immediately. VoiceBridge opens the mic as soon as playback
   finishes and the listen call collects that queued capture. Do not add filler
   or perform other work between those tool calls.
4. Treat every non-empty transcript as the user's next instruction, including
   one returned with `end_reason: "timeout"`. Use normal Codex tools to do the
   work silently, without spoken command-by-command narration.
5. For noticeably long work, first acknowledge it with one natural sentence
   and keep `listen_after` false for that progress update. When finished, call
   `voice_speak` first with `listen_after: true` and a separately composed
   concise summary. As soon as it returns, stream the complete written result
   while the summary is still playing so text appears as the user listens.
   VoiceBridge opens the mic immediately when playback ends even if writing is
   still in progress; call `voice_listen` after the written result to collect
   that capture.
6. When a decision is needed, show detailed options in writing and speak only
   the concise question and most important tradeoff, with `listen_after: true`.
7. After presenting each written result, call `voice_listen` to collect the
   capture queued by the preceding end-of-turn speech. A valid transcript
   resets the consecutive no-speech timeout count.
8. VoiceBridge internally discards noise segments that transcribe to no words.
   After one remaining no-speech timeout, check in once. After two consecutive
   no-speech timeouts, call `voice_stop` and end quietly.
9. On `end_reason: "device_error"`, explain the microphone problem briefly when
   speech still works, call `voice_stop`, and end.
10. If the user says stop, goodbye, or equivalent, speak a short goodbye with
    `listen_after` false, call `voice_stop`, and do not listen again.
11. If `voice_speak` or `voice_listen` returns `ok: false`, show the error, call
    `voice_stop`, and end instead of retrying indefinitely.

After `voice_start` succeeds, call `voice_stop` exactly once at the end and
never between turns. Keep speech brief unless the user explicitly requests a
spoken walkthrough.
