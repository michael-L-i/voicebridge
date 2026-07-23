---
name: voice-code
description: Start and run an explicit, interactive Cadence Code conversation with Codex using fully local speech input and output. Use only when the user explicitly invokes $voice-code or asks to start a Cadence Code voice conversation.
---

# Voice Code

Run a deliberate voice loop through the `mcp__cadence-code__voice_status`,
`mcp__cadence-code__voice_models`, `mcp__cadence-code__voice_configure`,
`mcp__cadence-code__voice_start`, `mcp__cadence-code__voice_speak`,
`mcp__cadence-code__voice_listen`, and `mcp__cadence-code__voice_stop` tools.
Cadence Code only performs speech input and output. Codex controls the
conversation and authors every word sent to speech.

Maintain two outputs for completed work:

- Keep useful technical detail in the normal written Codex response.
- Compose a separate short, conversational summary for `voice_speak`. Never
  read code, file paths, bullet lists, or the full written response aloud.

1. Call `voice_status`. If `first_run` is true, call `voice_models` before any
   audio tool or model download. Before asking any questions, reproduce this
   fixed onboarding script verbatim in a fenced `text` block. Do not summarize,
   rearrange, restyle, or generate any part of it from the model response.

   ```text
   +-- WELCOME TO CADENCE_CODE -----------------------------------------+
   |
   | Let's talk through whatever you're working on.
   |
   | YOU SPEAK -> I WORK -> SHORT REPLY ALOUD + DETAILS ON SCREEN
   |
   | We alternate turns. After the listening chime, speak naturally.
   | When I finish, the microphone opens again for your next turn.
   |
   +-- CONTROLS -------------------------------------------------------+
   | $voice-code       Start a voice conversation.
   | $voice-settings   Change the local voice or listening model anytime.
   | $voice-interrupt  After pressing Escape, add new guidance.
   | Say "stop" or "goodbye" to finish the conversation.
   |
   +-- PRESET MODELS --------------------------------------------------+
   | Voice (TTS)       Pocket TTS 100M
   | Listening (STT)   Parakeet 110M
   | These recommended models load automatically on your first start.
   | Run $voice-settings anytime to choose another pair.
   |
   +-- PRIVACY --------------------------------------------------------+
   | Speech recognition and synthesis run locally on this Mac.
   | Your transcript becomes a normal Codex instruction.
   +------------------------------------------------------------------+
   ```

   Immediately call `voice_configure` with `defaults.tts` and `defaults.stt`
   from `voice_models` (Pocket TTS and Parakeet 110M). Do not present a model
   selector, ask a model-selection question, or wait for confirmation. If
   configuration fails, show the error and end without calling `voice_start`.
   Existing users with `first_run: false` skip the fixed script and automatic
   default configuration silently.
2. Call `voice_start` and wait for the audio preflight and local speech models.
   Do not call any Cadence Code audio tool before this explicit skill invocation.
   If it returns `ok: false`, show the error and end without retrying.
3. Verify the result includes `version`, `host`, `capture`, and `preflight`, and
   that `host` is `codex`. If not, the MCP process is stale or misconfigured:
   call `voice_stop`, ask the user to start a new Codex session after updating
   or reinstalling the plugin, and end.
4. Speak a greeting with `listen_after: true`, then call `voice_listen`
   immediately. If `first_run` was true, use this short introduction verbatim:
   "Welcome to Cadence Code. We can talk through whatever you're working on:
   after the chime, speak naturally, and I'll reply aloud while keeping the
   useful details on screen. If you want to redirect me, press Escape and choose
   Voice Interrupt; I'm listening, so what would you like to work on?"
   Otherwise use an ordinary casual one-sentence greeting. Cadence Code opens
   the mic as soon as playback finishes and the listen call collects that
   queued capture. Do not add filler or perform other work between those tool
   calls.
5. Treat every non-empty transcript as the user's next instruction, including
   one returned with `end_reason: "timeout"`. Use normal Codex tools to do the
   work silently, without spoken command-by-command narration.
6. For noticeably long work, first acknowledge it with one natural sentence
   and keep `listen_after` false for that progress update. When finished, call
   `voice_speak` first with `listen_after: true` and a separately composed
   concise summary. As soon as it returns, stream the complete written result
   while the summary is still playing so text appears as the user listens.
   Cadence Code opens the mic immediately when playback ends even if writing is
   still in progress; call `voice_listen` after the written result to collect
   that capture.
7. When a decision is needed, show detailed options in writing and speak only
   the concise question and most important tradeoff, with `listen_after: true`.
8. After presenting each written result, call `voice_listen` to collect the
   capture queued by the preceding end-of-turn speech. A valid transcript
   resets the consecutive no-speech timeout count.
9. Cadence Code internally discards noise segments that transcribe to no words.
   After one remaining no-speech timeout, check in once. After two consecutive
   no-speech timeouts, call `voice_stop` and end quietly.
10. On `end_reason: "device_error"`, explain the microphone problem briefly when
   speech still works, call `voice_stop`, and end.
11. If the user says stop, goodbye, or equivalent, speak a short goodbye with
    `listen_after` false, call `voice_stop`, and do not listen again.
12. If `voice_speak` or `voice_listen` returns `ok: false`, show the error, call
    `voice_stop`, and end instead of retrying indefinitely. In particular,
    `error_code: "session_not_started"` means the required `voice_start` did not
    complete; do not use an audio tool to activate or recover the session.

After `voice_start` succeeds, call `voice_stop` exactly once at the end and
never between turns. Keep speech brief unless the user explicitly requests a
spoken walkthrough.

If the user presses Escape during a turn, they can invoke `$voice-interrupt` to
silence current Cadence Code audio and add spoken guidance without unloading the
models. The separate interrupt skill owns that recovery workflow.
