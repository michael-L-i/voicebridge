# Cadence Code privacy

Cadence Code keeps speech processing on the user's Mac. This document describes
the Cadence Code boundary; Codex, Claude Code, Cursor, and Google Antigravity
remain separate products with their own data handling and privacy policies.

## Microphone and audio

Cadence Code opens the microphone only after the user explicitly starts Voice
Code. `voice_start` briefly opens the configured input for an audio preflight
without retaining samples. Later, `voice_listen` records a turn, and the
explicit interrupt workflow can open a fresh capture. Audible chimes mark the
start and end of capture.

Raw microphone samples and generated speech exist only in process memory while
they are being transcribed or played. Cadence Code does not write recordings or
raw audio to disk, and it does not persist transcripts.

## Local processing and host handoff

The selected STT and TTS models run locally through MLX. Cadence Code has no
cloud speech service, telemetry, local reasoning model, or summarization model.
It speaks exactly the text supplied by the host.

After local transcription, Cadence Code returns the text to Codex, Claude Code,
Cursor, or Antigravity over the local stdio MCP connection. The host may then
send, store, or otherwise process that transcript under its own settings,
terms, and privacy policy:
[OpenAI privacy policy](https://openai.com/policies/privacy-policy/) and
[Anthropic privacy center](https://privacy.anthropic.com/),
[Cursor privacy policy](https://cursor.com/privacy), or
[Google privacy policy](https://policies.google.com/privacy). Host-side
prompts, logs, conversation history, and telemetry are outside Cadence Code's
boundary.

## Local files and downloads

Cadence Code stores configuration and its private Python environment locally.
Codex, Cursor, and Antigravity use `~/.cadence-code`; Claude Code supplies a
persistent per-plugin data directory. Speech-model weights use the normal
shared Hugging Face cache, usually `~/.cache/huggingface/hub`. These locations
contain settings, dependencies, and model weights, not Cadence Code recordings
or transcripts.

Initial setup requires internet access to download locked Python dependencies.
The first voice start also downloads the selected model weights from Hugging
Face. Those package and model hosts receive normal download request metadata
under their own policies. Once dependencies and the selected weights are
cached, speech inference itself is local.
