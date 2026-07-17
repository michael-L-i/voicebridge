# Agent Guide

## Project Overview

`voicebridge` is a Codex and Claude Code plugin: a fully local voice companion
for Apple Silicon. Its stdio MCP process owns local TTS and STT models directly
while a voice conversation is active. There is no HTTP daemon or local
summarization model; the host coding agent provides the exact text sent to TTS.

MLX is the speech inference backend, not a second reasoning layer. Speech
models run through `mlx-audio`; some TTS implementations reuse `mlx-lm` cache
and sampling utilities internally, but VoiceBridge never loads a local
reasoning or summarization model.

There is no passive narration. Users explicitly start Voice Code with
`$voice-code` or `/skills` in Codex, or `/voicebridge:voice-code` in Claude Code:

- On a new install, the host calls `voice_models`, presents the ordered local
  choices, and persists the selected pair through `voice_configure`.
- The host calls `voice_start`, which preflights audio access, loads the selected
  TTS and STT models in the MCP process, then speaks a greeting via
  `voice_speak`.
- The host calls `voice_listen` to capture the user's reply via the mic, then
  acts on the transcript with its normal tools -- silently, no play-by-play.
- The host calls `voice_speak` again with a short spoken-style update, and the
  loop repeats until the user says something like "stop" or two consecutive
  `voice_listen` calls time out.
- At that point the host calls `voice_stop`, which drops both providers, clears
  the MLX cache, and releases the active-session lock. If the host session ends
  unexpectedly, MCP process exit releases its memory and lock.

The MCP process itself is lightweight until voice mode starts. Models remain
warm between turns, then are released when the conversation stops.

The package is Python 3.11+ and is configured by `pyproject.toml`.

## Plugin Layout

This repo is the plugin and its own marketplace for both hosts. Users install it
through the host's plugin mechanism; there is no manual MCP configuration.

- `.claude-plugin/plugin.json`: plugin manifest and MCP server declaration.
- `.claude-plugin/marketplace.json`: lets this repo be added as its own
  Claude Code marketplace.
- `.codex-plugin/plugin.json`: Codex plugin manifest.
- `.agents/plugins/marketplace.json`: Codex marketplace metadata for this repo.
- `.mcp.json`: Codex's stdio MCP declaration and first-run timeouts.
- `skills/voice-code/`: explicit Codex `$voice-code` workflow.
- `bin/voicebridge-mcp-bootstrap`: a pure-bash wrapper. Builds a private venv
  under `VOICEBRIDGE_DATA_DIR` on first run (or after a dependency change),
  then `exec`s into the real `voicebridge-mcp` entrypoint inside it. Claude Code
  points that variable at its plugin data directory; Codex uses `~/.voicebridge`.
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
  manifest, falling back to `~/.voicebridge` for Codex and direct-Python dev).
  Existing configs are migrated away from the retired `[daemon]` and
  `[summarizer]` sections without replacing current voice or audio choices.
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
- `voicebridge/audio/preflight.py`: validates configured audio devices and
  briefly opens the mic without retaining samples before model setup begins.
- `voicebridge/providers/`: STT/TTS provider abstractions
  (`TTSProvider`/`STTProvider`) and a plain-dict registry keyed by config
  string. TTS providers are Kokoro, Chatterbox Turbo, and Qwen 0.6B; STT
  providers are Moonshine Base, Whisper Small, and Parakeet 0.6B.
- `voicebridge/mcp/server.py`: the small MCP tool surface -- `voice_models`,
  `voice_configure`, `voice_start`, `voice_speak`, `voice_listen`, `voice_stop`,
  and `voice_status`.
- `voicebridge/mcp/runtime.py`: owns warm model providers and the advisory
  machine-wide session lock. Only one VoiceBridge conversation across either
  host can use the audio devices and model memory at a time. Status includes
  host, first-run state, running version, and capture timing so stale
  post-update MCP processes are visible.

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
Codex or Claude Code MCP client session.

## Visible Plugin Test Sessions

When the user asks to launch a VoiceBridge test instance, use `cmux` to create
and drive a visible, clearly named tab/surface in the user's current workspace.
Do not create a separate native cmux window unless the user asks for one. Start
Voice Code on the user's behalf and leave the session open for hands-on audio
testing; do not ask the user to type routine launch, install, or initialization
commands.

Support both Claude Code and Codex as first-class test hosts. If the user does
not name a host, default to Claude Code. If the user names Codex, launch and
initialize a Codex test tab instead; do not substitute Claude Code merely
because its direct-checkout workflow is simpler.

- For a local Claude Code branch test, launch Claude from outside the checkout
  with `--add-dir <checkout> --plugin-dir <checkout>`, then send
  `/voicebridge:voice-code`. Do not use the checkout itself as Claude's working
  directory: Claude would also load the repo-level Codex `.mcp.json`, creating
  a second VoiceBridge server with the wrong host identity. This tests the
  checkout directly instead of the installed plugin cache.
- For a local Codex test, confirm the configured marketplace points at the
  requested checkout, use the documented cachebuster/reinstall flow, start a
  new Codex session, then send `$voice-code`.
- For a GitHub release test, update/install the normal GitHub-backed plugin,
  verify the requested version and source, launch the host without a local
  plugin override, and start Voice Code.
- Name the cmux tab with the host, source (`local` or `release`), branch or
  version, and use `cmux read-screen` to verify startup.
- Fully stop or close an existing VoiceBridge test before launching another;
  the machine-wide audio-session lock permits only one active conversation.
- Treat a new host process as required after changing or reinstalling a plugin.
  Report the launched host, source path or release version, and cmux target.

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
