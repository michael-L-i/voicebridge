# Claude Code Guide

## Project Summary

`voicebridge` gives Claude Code a fully local voice interface on Apple Silicon.
The plugin's stdio MCP process owns Kokoro TTS and Parakeet STT directly for an
active conversation; there is no HTTP daemon or local summarization model.
Both speech models run through MLX Audio. MLX is not used to generate or
rewrite Claude's response.

There is one integration surface: `/voicebridge:voice-code`. It loops between
speaking and listening through `voice_start`, `voice_speak`, `voice_listen`, and
`voice_stop`. Claude Code supplies the exact text spoken by TTS. There is no
passive narration.

Read `AGENTS.md` for the shared project map, commands, development principles,
and Git workflow. Claude-specific notes below override only when they conflict.

## Claude-Specific Flow

- Claude Code installs and wires the plugin through its normal plugin mechanism;
  the plugin manifest starts the lightweight stdio MCP server without manual
  MCP setup.
- `voice_start` acquires the machine-wide voice-session lock and loads TTS and
  STT. The first call may wait for model downloads; later turns reuse them.
- `commands/voice-code.md` drives the conversation. Claude acknowledges longer
  tasks briefly and performs the actual work silently. Detailed results remain
  visible in Claude Code, while `voice_speak` receives a separately composed,
  concise result or question based on the current task. Summary requests should
  answer the requested subject, not explain the voice machinery.
- `voice_stop` drops both model providers, clears the MLX cache, and releases the
  session lock. Process exit is the safety net, so no shutdown hook is needed.

## Working Expectations

- Keep changes concise and organized.
- Make incremental commits for coherent work units when commits are requested.
- Prefer small, reviewable patches over broad rewrites.
- Verify with the narrowest relevant command after code changes.
- Do not add passive narration, a detached daemon, or a second language model.
- Keep spoken text short, conversational, and free of code blocks, bullet lists,
  and long file paths.
