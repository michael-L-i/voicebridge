# Claude Code Guide

## Project Summary

`voicebridge` gives Claude Code a local voice interface on Apple Silicon,
distributed as a Claude Code plugin. It uses MLX-backed local models for
summarization, TTS, and STT, plus a FastAPI daemon that stays warm for the
duration of a voice conversation -- not a 24/7 background service.

There's one integration surface: an active `/voicebridge:voice-code` slash
command that loops between speaking and listening through an MCP server
(`voice_speak`, `voice_listen`, `voice_stop`, `voice_status`). There is no
passive narration -- that was deliberately removed.

Read `AGENTS.md` for the shared project map, commands, development
principles, and Git workflow. Claude-specific notes below override only when
they conflict.

## Claude-Specific Flow

- Installed via Claude Code's plugin mechanism (`/plugin marketplace add`,
  `/plugin install`) -- `.mcp.json` and `hooks/hooks.json` are auto-discovered
  and wired up by Claude Code itself, no manual `claude mcp add` or
  settings.json editing.
- `commands/voice-code.md` drives the conversation: greet via `voice_speak`,
  loop on `voice_listen`, act on the transcript with normal tools silently,
  update via `voice_speak`, repeat.
- The conversation ends either on a stop phrase ("stop"/"goodbye"/etc, after
  which Claude calls `voice_stop`) or two consecutive `voice_listen` timeouts
  (also followed by `voice_stop`). A `SessionEnd` hook (`hooks/session_end.sh`)
  is the safety net if the session just ends without an explicit goodbye.
- The daemon (`voicebridge/daemon/server.py`) holds the summarizer, TTS, and
  STT models warm only while a conversation is active; `voice_speak`/
  `voice_listen` lazily start it on first use via
  `voicebridge/daemon/lifecycle.py`, which both the CLI and the MCP server
  share so shutdown can always find it regardless of which path started it.

## Working Expectations

- Keep changes concise and organized.
- Make incremental commits for coherent work units when committing is part of
  the task.
- Prefer small, reviewable patches over broad rewrites.
- Verify with the narrowest relevant command after code changes.
- Don't reintroduce passive narration or a 24/7 daemon -- both were
  deliberately removed based on real usage.
- Keep spoken text short, conversational, and free of code blocks, bullet
  lists, and long file paths.
