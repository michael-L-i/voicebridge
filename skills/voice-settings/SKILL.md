---
name: voice-settings
description: Choose VoiceBridge's local speech and transcription models from the Codex UI. Use only when the user explicitly invokes $voice-settings or asks to open VoiceBridge settings.
---

# VoiceBridge Settings

Use `mcp__voicebridge__voice_status`, `mcp__voicebridge__voice_models`,
`mcp__voicebridge__voice_configure`, and `mcp__voicebridge__voice_stop` to
change the saved speech-model pair. This workflow is configuration only: do not
start a voice conversation or use the microphone.

1. Call `mcp__voicebridge__voice_status`.
2. If `ready` is true, explain that a model change ends the current Voice Code
   session. Ask for confirmation with Codex's structured question UI. If the
   user confirms, call `mcp__voicebridge__voice_stop`; otherwise end without
   changing settings.
3. Call `mcp__voicebridge__voice_models`. Present separate TTS and STT
   single-choice selectors using Codex's structured question UI. The
   structured UI starts on the first listed option, so list `current.tts` and
   `current.stt` first with "(Current)" appended to their labels — or the
   matching first-run `defaults` entry when an existing custom model is not in
   the catalog — then the remaining options lightest to heaviest, appending
   "(Recommended)" to the `defaults` entry when it is not the current one.
   Show every option's tier, download size, and short description.
4. If the user cancels either selector, end without changing settings.
   Otherwise call `mcp__voicebridge__voice_configure` with both chosen IDs.
5. Confirm the selected labels and say the models download when the next
   `$voice-code` session starts. Do not call `mcp__voicebridge__voice_start`,
   `mcp__voicebridge__voice_speak`, or `mcp__voicebridge__voice_listen` here.
   Explain that unused model weights remain in the Hugging Face cache until the
   user removes them.
