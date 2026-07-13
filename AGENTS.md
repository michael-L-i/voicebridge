# Agent Guide

## Project Overview

`voicebridge` is a Claude Code plugin: a fully local voice companion for Apple
Silicon. Its stdio MCP process owns local TTS and STT models directly while a
voice conversation is active. There is no HTTP daemon or local summarization
model; Claude Code provides the exact text sent to TTS.

There is no passive narration. The only user experience is `/voicebridge:voice-code`:

- The user runs the slash command. Claude calls `voice_start`, which loads
  Kokoro and Parakeet in the MCP process, then speaks a greeting via
  `voice_speak`.
- Claude calls `voice_listen` to capture the user's reply via the mic, then
  acts on the transcript with its normal tools -- silently, no play-by-play.
- Claude calls `voice_speak` again with a short spoken-style update, and the
  loop repeats until the user says something like "stop" or two consecutive
  `voice_listen` calls time out.
- At that point Claude calls `voice_stop`, which drops both providers, clears
  the MLX cache, and releases the active-session lock. If the Claude Code
  session ends unexpectedly, MCP process exit releases its memory and lock.

The MCP process itself is lightweight until voice mode starts. Models remain
warm between turns, then are released when the conversation stops.

The package is Python 3.11+ and is configured by `pyproject.toml`.

## Plugin Layout

This repo is both the plugin and its own marketplace (see
`.claude-plugin/marketplace.json`), matching the pattern used by
`mbailey/voicemode`. Users install it via Claude Code's own plugin mechanism
(`/plugin marketplace add` then `/plugin install`) -- there's no manual
`claude mcp add` or hand-editing `~/.claude/settings.json` involved.

- `.claude-plugin/plugin.json`: plugin manifest and MCP server declaration.
- `.claude-plugin/marketplace.json`: lets this repo be added as its own
  marketplace.
- `bin/voicebridge-mcp-bootstrap`: a pure-bash wrapper. Builds a private venv
  under `${CLAUDE_PLUGIN_DATA}/venv` on first run (or after a dependency
  change), then `exec`s into the real `voicebridge-mcp` entrypoint inside it.
  Every log line in this script goes to stderr only -- stdout is the live MCP
  JSON-RPC channel, and any stray stdout output corrupts the protocol
  handshake.
- `commands/voice-code.md`: the `/voicebridge:voice-code` slash command
  (namespaced to the plugin name automatically by Claude Code).

## Important Paths

- `voicebridge/cli.py`: Click CLI with `doctor` and `listen-test` for direct
  development. The plugin path invokes the MCP bootstrap instead.
- `voicebridge/config.py`: Pydantic config models. `CONFIG_DIR` reads the
  `VOICEBRIDGE_DATA_DIR` env var (set to `${CLAUDE_PLUGIN_DATA}` by the plugin
  manifest, falling back to `~/.voicebridge` for direct-Python dev).
- `config/default_config.toml`: default speech model and audio settings
  copied into the user's config directory on first run.
- `voicebridge/audio/capture.py` / `playback.py`: mic capture using a real
  WebRTC voice-activity classifier (not an amplitude threshold -- ported from
  studying voicemode's approach, a meaningfully more reliable
  speech/silence signal across rooms and mics), callback-driven so a
  device-level hang cannot block indefinitely (a blocking `stream.read()`
  hung for hours in practice when the Mac slept mid-listen). Audible
  start/end chimes mark exactly when the mic is listening. Playback and
  capture are serialized through a shared lock (never record and speak at
  the same instant -- there's no echo cancellation).
- `voicebridge/providers/`: STT/TTS provider abstractions
  (`TTSProvider`/`STTProvider`) and a plain-dict registry keyed by config
  string. Concrete providers: `kokoro_tts.py` (default TTS), `parakeet_stt.py`
  (default STT), `whisper_stt.py` (alternate STT, proves the registry swap
  works via config alone).
- `voicebridge/mcp/server.py`: the small MCP tool surface -- `voice_start`,
  `voice_speak`, `voice_listen`, `voice_stop`, and `voice_status`.
- `voicebridge/mcp/runtime.py`: owns warm model providers and the advisory
  session lock. Only one Claude Code voice conversation can use the machine's
  audio devices and model memory at a time.

## Local Commands

Run commands from the repository root.

```bash
python -m pip install -e .
voicebridge doctor
voicebridge listen-test
python -m unittest discover -s tests -v
```

For behavioral changes, run the unit tests plus the narrowest relevant manual
check, usually `voicebridge doctor`, `voicebridge listen-test`, or a direct
`voice_start`/`voice_speak`/`voice_listen`/`voice_stop` sequence through a real
MCP client session.

## Development Principles

- Keep changes small, direct, and organized around the existing module
  boundaries.
- Prefer concise code over broad abstractions. Add helpers only when they
  remove real duplication or clarify a shared behavior.
- Preserve local-first behavior. Do not add cloud services, telemetry, or
  network dependencies unless the user explicitly asks for them.
- Keep audio playback and recording serialized through the existing audio
  lock.
- Do not introduce a detached service, automatic passive narration, or a
  second language model. They are deliberately outside the product.
- Treat mic/model failures defensively. A missing model, device failure, or
  timed-out listen should surface as a clear result, not a crash.
- Keep heavy model imports out of MCP startup. `voice_start` intentionally
  loads both speech models before the greeting so turns stay responsive.
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
  around process/session locking, audio locking, sample rates, and model
  compatibility gotchas.
- Avoid large rewrites when a focused patch solves the problem.
- Keep markdown and code ASCII unless a file already uses another character
  set or the content specifically requires it.
