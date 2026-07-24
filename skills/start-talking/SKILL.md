---
name: start-talking
description: Start and run an explicit Cadence Code conversation with Codex, Cursor, or Antigravity using fully local speech input and output. Use only when the user explicitly invokes $start-talking, /start-talking, or asks to start talking with Cadence Code.
disable-model-invocation: true
---

# Start Talking

Run a deliberate voice loop through the `mcp__cadence-code__voice_status`,
`mcp__cadence-code__voice_models`, `mcp__cadence-code__voice_configure`,
`mcp__cadence-code__voice_start`, `mcp__cadence-code__voice_speak`,
`mcp__cadence-code__voice_listen`, and `mcp__cadence-code__voice_stop` tools.
Cursor and Antigravity may display these as the corresponding `voice_status`,
`voice_models`, `voice_configure`, `voice_start`, `voice_speak`,
`voice_listen`, and `voice_stop` tools under the `cadence-code` MCP server.
Cadence Code only performs speech input and output. The host agent controls the
conversation and authors every word sent to speech.

If the Cadence Code MCP tools are unavailable or still connecting, run the
bundled `scripts/setup` skill script and wait for it to finish. Do not
background it or retry it in parallel. On failure, show the error and end. On
success, ask the user to restart the host and invoke `/start-talking` again,
then end without attempting an MCP tool call. This fallback applies to Cursor
and Antigravity, neither of which documents a server startup timeout long
enough to build the private venv on first run. Codex declares
`startup_timeout_sec` and keeps its existing setup flow.

Maintain two outputs for completed work:

- Keep useful technical detail in the normal written host response.
- Compose a separate short, conversational summary for `voice_speak`. Never
  read code, file paths, bullet lists, or the full written response aloud.

1. Call `voice_status`. If `first_run` is true, call `voice_models` before any
   audio tool or model download. Before asking any questions, reproduce this
   fixed onboarding script verbatim in a fenced `text` block. Do not summarize,
   rearrange, restyle, or generate any part of it from the model response.

   ```text
   +-- WELCOME TO CADENCE CODE ----------------------------------------+
   |
   | I want to talk with you. Ask me questions, think out loud,
   | or tell me what to build.
   |
   | YOU TALK -> I WORK -> WE KEEP GOING
   |
   | We take turns. Speak naturally after the chime. I answer aloud
   | with the useful details on screen, then listen for your next turn.
   |
   +-- QUICK CONTROLS -------------------------------------------------+
   | $start-talking /start-talking    Start a conversation.
   | $jump-in       /jump-in          Redirect me by voice.
   | $wrap-up       /wrap-up          End and release the models.
   | $voice-settings /voice-settings  Change speech models.
   | You can also say "stop" or "goodbye" at any time.
   |
   +-- READY TO GO ----------------------------------------------------+
   | Voice              Pocket TTS 100M
   | Speech recognition Parakeet 110M
   | These local defaults load automatically. Change them anytime
   | with $voice-settings or /voice-settings.
   |
   +-- PRIVATE BY DEFAULT ---------------------------------------------+
   | Listening and speaking stay on this Mac. Your transcript becomes
   | a normal coding-agent instruction.
   +------------------------------------------------------------------+
   ```

   Immediately call `voice_configure` with `defaults.tts` and `defaults.stt`
   from `voice_models` (Pocket TTS and Parakeet 110M). Do not present a model
   selector, ask a model-selection question, or wait for confirmation. If
   configuration fails, show the error and end without calling `voice_start`.
   Existing users with `first_run: false` skip the fixed script and automatic
   default configuration silently.
2. Call `voice_start`, then poll `voice_status` until `ready` is true. This is
   the same in every host: `voice_start` returns as soon as the audio preflight
   passes and loads the speech models in the background, so a first-run model
   download can never outlive the host's MCP tool deadline. While `starting` is
   true, wait between polls; do not narrate or start other work. If
   `start_error` is set, show it and end without retrying. Do not call any
   Cadence Code audio tool before this explicit skill invocation, and do not
   call `voice_speak` or `voice_listen` until `ready` is true. If `voice_start`
   or a poll returns `ok: false`, show the error and end without retrying.
3. Verify the completed start result or final status includes `version`, `host`,
   `capture`, and `preflight`.
   The host must be `codex` when invoked from Codex, `cursor` when invoked from
   Cursor, or `antigravity` when invoked from Antigravity. If it does not match,
   the MCP process is stale or misconfigured: call `voice_stop`, ask the user
   to restart the current host after updating or reinstalling the plugin, and
   end.
4. Speak a greeting with `listen_after: true`, then call `voice_listen`
   immediately. If `first_run` was true, use this short introduction verbatim:
   "Welcome to Cadence Code. I want to talk with you about whatever you're
   working on. We'll alternate turns: speak naturally after the chime, and I'll
   answer aloud while keeping the useful details on screen. If you want to
   interrupt me, press Escape and choose Jump In. What would you like to work
   on?"
   Otherwise use an ordinary casual one-sentence greeting. Cadence Code opens
   the mic as soon as playback finishes and the listen call collects that
   queued capture. Do not add filler or perform other work between those tool
   calls.
5. Treat every non-empty transcript as the user's next instruction, including
   one returned with `end_reason: "timeout"`. Use normal host tools to do the
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
    `listen_after` false, call `voice_stop` with `wait_for_speech: true`, and do
    not listen again.
12. If `voice_speak` or `voice_listen` returns `ok: false`, show the error, call
    `voice_stop`, and end instead of retrying indefinitely. In particular,
    `error_code: "session_not_started"` means the required `voice_start` did not
    complete; do not use an audio tool to activate or recover the session.

After `voice_start` succeeds, call `voice_stop` exactly once at the end and
never between turns. Keep speech brief unless the user explicitly requests a
spoken walkthrough.

If the user presses Escape during a turn, they can invoke `$jump-in` in Codex
or `/jump-in` in Cursor or Antigravity to
silence current Cadence Code audio and add spoken guidance without unloading the
models. The separate Jump In skill owns that recovery workflow. The user can
invoke `$wrap-up` or `/wrap-up` to end the conversation directly.
