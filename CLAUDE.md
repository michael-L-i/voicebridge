# Claude Code Guide

## Project Summary

`cadence-code` gives Claude Code a fully local voice interface on Apple Silicon.
The plugin's stdio MCP process owns the selected TTS and STT models directly for
an active conversation; there is no HTTP daemon or local summarization model.
Speech models run through MLX Audio. MLX is not used to generate or rewrite
Claude's response.

The main integration surface is `/cadence-code:start-talking`. It loops between
choosing models on a new install, then speaking and listening through
`voice_start`, `voice_speak`, `voice_listen`, and `voice_stop`. After pressing
Escape, `/cadence-code:jump-in` silences current audio and captures added
guidance through `voice_interrupt`. `/cadence-code:wrap-up` ends the
conversation and releases the models. Claude Code supplies the exact text
spoken by TTS. There is no passive narration.

Read `AGENTS.md` for the shared project map, commands, development principles,
and Git workflow. Claude-specific notes below override only when they conflict.

## Claude-Specific Flow

- Claude Code installs and wires the plugin through its normal plugin mechanism;
  the plugin manifest starts the lightweight stdio MCP server without manual
  MCP setup.
- `voice_start` acquires the machine-wide voice-session lock and loads TTS and
  STT. The first call may wait for model downloads; later turns reuse them.
- `commands/start-talking.md` drives the conversation. Claude acknowledges longer
  tasks briefly and performs the actual work silently. Detailed results remain
  visible in Claude Code, while `voice_speak` receives a separately composed,
  concise result or question based on the current task. Summary requests should
  answer the requested subject, not explain the voice machinery.
- `voice_stop` normally cancels active audio, drops both model providers, clears
  the MLX cache, and releases the session lock. Wrap Up can let a short final
  message finish first. Normal MCP process exit runs the same cleanup;
  operating-system process teardown remains the final safety net.

## Working Expectations

- Keep changes concise and organized.
- Make incremental commits for coherent work units when commits are requested.
- Prefer small, reviewable patches over broad rewrites.
- Verify with the narrowest relevant command after code changes.
- Do not add passive narration, a detached daemon, or a second language model.
- Keep spoken text short, conversational, and free of code blocks, bullet lists,
  and long file paths.
