# Agent Guide

## Project Overview

`voicebridge` is a Claude Code plugin: a fully local voice companion for Apple
Silicon. It runs a local FastAPI daemon that keeps speech, transcription, and
summarization models warm, exposed to Claude only through an MCP server and a
slash command.

There is no passive narration. The only user experience is `/voicebridge:voice-code`:

- The user runs the slash command. Claude speaks a greeting via the
  `voice_speak` MCP tool, which lazily starts the background daemon on first
  use if it isn't already running.
- Claude calls `voice_listen` to capture the user's reply via the mic, then
  acts on the transcript with its normal tools -- silently, no play-by-play.
- Claude calls `voice_speak` again with a short spoken-style update, and the
  loop repeats until the user says something like "stop" or two consecutive
  `voice_listen` calls time out.
- At that point Claude calls `voice_stop`, which shuts the daemon down and
  frees the several GB of MLX models it holds in memory. A `SessionEnd` hook
  is a safety net for the same shutdown if the session just ends instead
  (closed terminal, `/clear`, etc.) without an explicit goodbye.

The daemon is deliberately session-scoped, not a 24/7 background service --
it only exists while a voice conversation is actually happening.

The package is Python 3.11+ and is configured by `pyproject.toml`.

## Plugin Layout

This repo is both the plugin and its own marketplace (see
`.claude-plugin/marketplace.json`), matching the pattern used by
`mbailey/voicemode`. Users install it via Claude Code's own plugin mechanism
(`/plugin marketplace add` then `/plugin install`) -- there's no manual
`claude mcp add` or hand-editing `~/.claude/settings.json` involved.

- `.claude-plugin/plugin.json`: plugin manifest.
- `.claude-plugin/marketplace.json`: lets this repo be added as its own
  marketplace.
- `.mcp.json`: declares the MCP server. Claude Code auto-starts it whenever
  the plugin is enabled; its `command` points at `bin/voicebridge-mcp-bootstrap`.
- `bin/voicebridge-mcp-bootstrap`: a pure-bash wrapper. Builds a private venv
  under `${CLAUDE_PLUGIN_DATA}/venv` on first run (or after a dependency
  change), then `exec`s into the real `voicebridge-mcp` entrypoint inside it.
  Every log line in this script goes to stderr only -- stdout is the live MCP
  JSON-RPC channel, and any stray stdout output corrupts the protocol
  handshake.
- `hooks/hooks.json` + `hooks/session_end.sh`: the `SessionEnd` safety-net
  shutdown described above. Pure bash, no Python dependency, since it must
  work even if the venv bootstrap never completed.
- `commands/voice-code.md`: the `/voicebridge:voice-code` slash command
  (namespaced to the plugin name automatically by Claude Code).

## Important Paths

- `voicebridge/cli.py`: Click CLI -- `doctor`, `start`, `stop`, `status`,
  `listen-test`. Used for direct-Python development; the plugin path doesn't
  invoke this directly (the MCP bootstrap wrapper starts the daemon itself).
- `voicebridge/config.py`: Pydantic config models. `CONFIG_DIR` reads the
  `VOICEBRIDGE_DATA_DIR` env var (set to `${CLAUDE_PLUGIN_DATA}` by `.mcp.json`
  under the plugin, falling back to `~/.voicebridge` for direct-Python dev).
- `config/default_config.toml`: default daemon, model, and audio settings
  copied into the user's config directory on first run.
- `voicebridge/daemon/server.py`: FastAPI daemon with `/health`, `/speak`, and
  `/listen` routes only.
- `voicebridge/daemon/lifecycle.py`: shared PID-file bookkeeping
  (`start_background`/`stop_background`/`pid_alive`/`read_pid`), used by both
  `cli.py` and `mcp/server.py` so the `SessionEnd` hook can always find the
  daemon to kill it, regardless of which path started it.
- `voicebridge/daemon/audio_in.py` / `audio_out.py`: mic capture with
  energy-based VAD, and playback serialized through a shared lock (never
  record and speak at the same instant -- there's no echo cancellation).
- `voicebridge/daemon/summarizer.py`: MLX summarizer wrapper, the spoken-style
  compression prompt, and the `is_already_short` heuristic that skips
  compression on text that's already spoken-sized.
- `voicebridge/daemon/state.py`: per-session spoken-summary history only
  (`SessionState`), for conversational continuity within a `/voice-code`
  session.
- `voicebridge/providers/`: STT/TTS provider abstractions
  (`TTSProvider`/`STTProvider`) and a plain-dict registry keyed by config
  string. Concrete providers: `kokoro_tts.py` (default TTS), `parakeet_stt.py`
  (default STT), `whisper_stt.py` (alternate STT, proves the registry swap
  works via config alone).
- `voicebridge/mcp/server.py`: the MCP tools -- `voice_speak`, `voice_listen`,
  `voice_stop`, `voice_status`. Reads `CLAUDE_CODE_SESSION_ID` (set by Claude
  Code on every process it spawns) to key session state without the agent
  needing to pass it explicitly.

## Local Commands

Run commands from the repository root.

```bash
python -m pip install -e .
voicebridge doctor
voicebridge start
voicebridge start --background
voicebridge status
voicebridge stop
voicebridge listen-test
```

There is no dedicated test suite in this repo yet. For behavioral changes, run
the narrowest relevant manual check, usually `voicebridge doctor`,
`voicebridge status`, `voicebridge listen-test`, or a direct
`voice_speak`/`voice_listen`/`voice_stop` call through a real MCP client
session.

## Development Principles

- Keep changes small, direct, and organized around the existing module
  boundaries.
- Prefer concise code over broad abstractions. Add helpers only when they
  remove real duplication or clarify a shared behavior.
- Preserve local-first behavior. Do not add cloud services, telemetry, or
  network dependencies unless the user explicitly asks for them.
- Keep audio playback and recording serialized through the existing audio
  lock.
- Keep the daemon session-scoped. Don't reintroduce a 24/7 background service
  or automatic passive narration -- both were deliberately removed.
- Treat mic/model failures defensively -- a missing model, a dead daemon, or
  a timed-out listen should surface as a clear result, not a crash.
- Be careful with model loading paths. The daemon intentionally loads models
  once at startup so `voice_speak`/`voice_listen` calls avoid model-load
  latency mid-conversation.
- Keep spoken output brief and natural. This project optimizes for audio, not
  screen-style reports.
- Don't assume a dependency's currently-pinned transitive versions are
  stable -- `misaki`'s own newer releases silently added a hard dependency on
  `phonemizer-fork` (not plain `phonemizer`) and `espeakng-loader`; verify
  fresh installs periodically rather than trusting an old working venv.

## Git Workflow

- Check `git status` before editing and before finishing.
- Make incremental commits for coherent units of work when commits are
  requested or when a task naturally spans multiple independent changes.
- Use clear commit messages that describe the user-visible change.
- Do not mix unrelated cleanup into feature or bug-fix commits.
- Never revert user changes unless the user explicitly asks.

## Style Notes

- Follow the current Python style: simple modules, typed function signatures
  where useful, and straightforward Pydantic models for structured config.
- Keep comments sparse and useful. Explain non-obvious behavior, especially
  around the daemon lifecycle, audio locking, sample rates, and model
  compatibility gotchas.
- Avoid large rewrites when a focused patch solves the problem.
- Keep markdown and code ASCII unless a file already uses another character
  set or the content specifically requires it.
