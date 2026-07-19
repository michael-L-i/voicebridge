---
description: Choose VoiceBridge speech models
---

Open VoiceBridge Settings. This command changes local TTS and STT model
selection only; it does not start a voice conversation, request microphone
access, or download models.

1. Call `mcp__voicebridge__voice_status`.
2. If `ready` is true, explain that changing models ends the active Voice Code
   session. Ask for confirmation using Claude Code's structured question UI. If
   the user confirms, call `mcp__voicebridge__voice_stop`; otherwise end without
   changing settings.
3. Call `mcp__voicebridge__voice_models`. Present separate TTS and STT
   single-choice selectors using Claude Code's structured question UI. The
   structured UI starts on the first listed option, so list the ID from
   `current` first with "(Current)" appended to its label — or the matching
   `defaults` entry when an existing custom model is not in the catalog — then
   the remaining options lightest to heaviest, appending "(Recommended)" to
   the `defaults` entry when it is not the current one. Each choice must show
   its tier, download size, and short description.
4. If the user cancels either selector, end without changing settings.
   Otherwise call `mcp__voicebridge__voice_configure` with the chosen TTS and
   STT IDs.
5. Report the selected labels and say the models download when Voice Code next
   starts. Do not call `mcp__voicebridge__voice_start`, `voice_speak`, or
   `voice_listen` from settings. Remind the user that changing models keeps old
   cached weights until they remove them through the Hugging Face cache tools.
