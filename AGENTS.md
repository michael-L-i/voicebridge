# Agent Guide

## Project Overview

`cadence-code` is a Codex, Claude Code, Cursor, and Google Antigravity plugin: a
fully local voice companion for Apple Silicon. Its stdio MCP process owns local
TTS and STT models directly while a voice conversation is active. There is no
HTTP daemon or local summarization model; the host coding agent provides the
exact text sent to TTS.

MLX is the speech inference backend, not a second reasoning layer. Speech
models run through `mlx-audio`; some TTS implementations reuse `mlx-lm` cache
and sampling utilities internally, but Cadence Code never loads a local
reasoning or summarization model.

There is no passive narration. Users explicitly choose Start Talking with
`$start-talking` or `/skills` in Codex, `/cadence-code:start-talking` in Claude
Code, or `/start-talking` in Cursor and Antigravity:

- On a new install, the host calls `voice_models`, shows the fixed first-run
  orientation, and persists its returned Pocket TTS and Parakeet 110M defaults
  through `voice_configure` without pausing for model selection.
- The host calls `voice_start`, which preflights audio access, loads the selected
  TTS and STT models in the MCP process, then speaks a greeting via
  `voice_speak`.
- The host calls `voice_listen` to capture the user's reply via the mic, then
  acts on the transcript with its normal tools -- silently, no play-by-play.
- After interrupting a host turn with Escape, the user can invoke the explicit
  interrupt workflow. `voice_interrupt` silences current audio, opens a fresh
  capture, and returns added guidance without unloading the models.
- The host calls `voice_speak` again with a short spoken-style update, and the
  loop repeats until the user says something like "stop" or two consecutive
  `voice_listen` calls time out.
- At that point the host calls `voice_stop`, which drops both providers, clears
  the MLX cache, and releases the active-session lock. If the host session ends
  unexpectedly, MCP process exit releases its memory and lock.
- The explicit `$wrap-up`, `/cadence-code:wrap-up`, or `/wrap-up` workflow gives
  the same clean ending on demand, allowing a short goodbye to finish before
  release.

The MCP process itself is lightweight until voice mode starts. Models remain
warm between turns, then are released when the conversation stops.

The package supports Python 3.11 through 3.14 and is configured by
`pyproject.toml`.

## Plugin Layout

This repo is the plugin and its own marketplace where the host uses one. Users
install it through the host's plugin mechanism; there is no manual MCP
configuration.

- `.claude-plugin/plugin.json`: plugin manifest and MCP server declaration.
- `.claude-plugin/marketplace.json`: lets this repo be added as its own
  Claude Code marketplace.
- `.codex-plugin/plugin.json`: Codex plugin manifest with an inline MCP server
  declaration. Keeping the declaration here instead of in a root `.mcp.json`
  prevents Claude Code from also discovering it as a project MCP server during
  direct-checkout development.
- `.agents/plugins/marketplace.json`: Codex marketplace metadata for this repo.
- `.cursor-plugin/plugin.json`: Cursor plugin manifest. It exposes the canonical
  Agent Skills and points at the root `mcp.json` without loading the
  Claude-specific command files.
- `.cursor-plugin/marketplace.json`: lets the repository serve as a direct
  GitHub Cursor plugin source.
- `mcp.json`: installed Cursor stdio MCP declaration. It resolves the bootstrap
  through `${CURSOR_PLUGIN_ROOT}` and identifies the host as `cursor`.
- `plugin.json` / `mcp_config.json`: native Antigravity plugin manifest and
  stdio MCP declaration, shared by AGY CLI and Antigravity IDE. The MCP command
  sets `CADENCE_CODE_HOST` through `env` because AGY 1.1.6 accepts but does not
  pass the documented stdio `env` object.
- `skills/start-talking/`, `skills/jump-in/`, `skills/wrap-up/`, and
  `skills/voice-settings/`: canonical Codex, Cursor, and Antigravity workflows.
- `.agents/skills/`: relative symlinks to every canonical Agent Skill so direct
  Codex, Cursor, and Antigravity checkouts expose the installed workflows.
- `.cursor/mcp.json`: Cursor workspace MCP declaration used by `./dev cursor`
  without installing the plugin.
- `.agents/mcp_config.json`: Antigravity workspace MCP declaration used by
  `./dev agy` without installing the plugin.
- `bin/cadence-code-mcp-bootstrap`: a pure-bash wrapper. Builds a private venv
  under `CADENCE_CODE_DATA_DIR` on first run (or after a dependency change),
  then `exec`s into the real `cadence-code-mcp` entrypoint inside it. Claude Code
  points that variable at its plugin data directory; Codex, Cursor, and
  Antigravity use `~/.cadence-code`.
  Every log line in this script goes to stderr only -- stdout is the live MCP
  JSON-RPC channel, and any stray stdout output corrupts the protocol
  handshake.
- `commands/start-talking.md`, `commands/jump-in.md`,
  `commands/voice-settings.md`, and `commands/wrap-up.md`: the corresponding
  Claude Code slash commands, namespaced to the plugin automatically.

## Important Paths

- `cadence_code/cli.py`: Click CLI with `doctor` and `listen-test` for direct
  development. The plugin path invokes the MCP bootstrap instead.
- `cadence_code/config.py`: Pydantic config models. `CONFIG_DIR` reads the
  `CADENCE_CODE_DATA_DIR` env var (set to `${CLAUDE_PLUGIN_DATA}` by the Claude
  manifest, falling back to `~/.cadence-code` for Codex, Cursor, Antigravity,
  and direct-Python dev).
  Existing configs are migrated away from the retired `[daemon]` and
  `[summarizer]` sections without replacing current voice or audio choices.
- `config/default_config.toml`: default speech model and audio settings
  copied into the user's config directory on first run.
- `cadence_code/audio/capture.py` / `playback.py`: mic capture using a real
  WebRTC voice-activity classifier (not an amplitude threshold -- ported from
  studying voicemode's approach, a meaningfully more reliable
  speech/silence signal across rooms and mics), callback-driven so a
  device-level hang cannot block indefinitely (a blocking `stream.read()`
  hung for hours in practice when the Mac slept mid-listen). Audible
  start/end chimes mark exactly when the mic is listening. Playback and
  capture are serialized through a shared lock (never record and speak at
  the same instant -- there's no echo cancellation).
- `cadence_code/audio/preflight.py`: validates configured audio devices and
  briefly opens the mic without retaining samples before model setup begins.
- `cadence_code/providers/`: STT/TTS provider abstractions
  (`TTSProvider`/`STTProvider`) and a plain-dict registry keyed by config
  string. TTS providers are Pocket TTS, Kokoro, Chatterbox Turbo, and Qwen
  0.6B; STT providers are Moonshine Base, Parakeet 110M, and Parakeet 0.6B.
- `cadence_code/mcp/server.py`: the small MCP tool surface -- `voice_models`,
  `voice_configure`, `voice_start`, `voice_speak`, `voice_listen`,
  `voice_interrupt`, `voice_stop`, and `voice_status`.
- `cadence_code/mcp/runtime.py`: owns warm model providers and the advisory
  machine-wide session lock. Only one Cadence Code conversation across any host
  can use the audio devices and model memory at a time. Status includes
  host, first-run state, running version, and capture timing so stale
  post-update MCP processes are visible.

## Local Commands

Run commands from the repository root.

```bash
python -m pip install -e .
cadence-code doctor
cadence-code listen-test
python -m unittest discover -s tests -v
```

For behavioral changes, run the unit tests plus the narrowest relevant manual
check, usually `cadence-code doctor`, `cadence-code listen-test`, or a direct
`voice_start`/`voice_speak`/`voice_interrupt`/`voice_listen`/`voice_stop`
sequence through a real Codex, Claude Code, Cursor, or Antigravity MCP client
session.

## Visible Plugin Test Sessions

When the user asks to launch a Cadence Code test instance, use `cmux` to create
and drive a visible, clearly named tab/surface in the user's current workspace.
Do not create a separate native cmux window unless the user asks for one. Invoke
Start Talking on the user's behalf and leave the session open for hands-on
audio testing; do not ask the user to type routine launch, install, or
initialization commands.

Support Claude Code, Codex, Cursor, and Antigravity as first-class test hosts.
If the user does not name a host, default to Claude Code. Launch the named host
rather than substituting another host because its direct-checkout workflow is
simpler.

- For a local Claude Code branch test, run `./dev claude`, then send
  `/cadence-code:start-talking`. This tests the checkout directly through
  `--plugin-dir` instead of the installed plugin cache.
- For a local Codex branch test, run `./dev codex`, then send `$start-talking`.
  The launcher injects the checkout's MCP server for that process only and does
  not install a plugin or configure a marketplace.
- For a local Cursor branch test, run `./dev cursor`, then send
  `/start-talking`. The launcher uses the checkout's `.cursor` MCP configuration
  and shared Agent Skills without installing a plugin or changing user
  configuration.
- For a local Antigravity branch test, run `./dev agy`, then send
  `/start-talking`. The launcher uses the checkout's `.agents` MCP and skill
  configuration without installing a plugin or changing user configuration.
- For a GitHub release test, update/install the normal GitHub-backed plugin,
  verify the requested version and source, launch the host without a local
  plugin override, and invoke Start Talking.
- Name the cmux tab with the host, source (`local` or `release`), branch or
  version, and use `cmux read-screen` to verify startup.
- Fully stop or close an existing Cadence Code test before launching another;
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
