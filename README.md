# voicebridge

[![CI](https://github.com/michael-L-i/voicebridge/actions/workflows/ci.yml/badge.svg)](https://github.com/michael-L-i/voicebridge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)

VoiceBridge is a local voice conversation plugin for Codex and Claude Code on
Apple Silicon. Start Voice Code, talk naturally, and let your coding agent
decide what to say back.

The plugin is deliberately small:

- Codex or Claude Code controls the conversation and writes every spoken response.
- Kokoro converts the host's text to speech.
- Parakeet transcribes microphone audio back to text.
- The plugin does not run a daemon, a summarizer, or a second language model.

Detailed answers stay on screen. The host sends a separate concise version to
speech, so audio sounds like a coworker giving you the useful part instead of
reading a terminal response verbatim.

## How it works

The host starts one lightweight stdio MCP server with the plugin. The server
does not load speech models until voice mode begins. `voice_start` first checks
the configured input and output devices and briefly opens the microphone
without retaining audio. It then loads Kokoro and Parakeet into that MCP
process. The same model instances are reused between turns, and `voice_stop`
releases them and clears the MLX cache.

VoiceBridge does use MLX, but only for speech inference:

- TTS: `mlx-community/Kokoro-82M-bf16` through MLX Audio
- STT: `mlx-community/parakeet-tdt-0.6b-v3` through MLX Audio

There is no Qwen call and no `mlx-lm` import in VoiceBridge. MLX Audio currently
declares `mlx-lm` as a transitive package dependency, so its executable may be
present in the private environment even though VoiceBridge never invokes it.

Only one voice conversation can own the microphone, speakers, and model memory
at a time. A machine-wide advisory lock prevents Codex, Claude Code, or direct
development sessions from interfering with one another. Speech playback and
microphone capture are also serialized; there is no echo cancellation.

## Install for Codex

VoiceBridge works in the Codex CLI, desktop app, and IDE extension. Add this
repository as a marketplace and install the plugin from a terminal:

```bash
codex plugin marketplace add michael-L-i/voicebridge
codex plugin add voicebridge@voicebridge-marketplace
```

Start a new Codex session after installation. Invoke `$voice-code` in a prompt,
or select Voice Code from `/skills`.

To update an installed release:

```bash
codex plugin marketplace upgrade voicebridge-marketplace
codex plugin add voicebridge@voicebridge-marketplace
```

Then start a new Codex session so it discovers the updated skill and MCP tools.

## Install for Claude Code

In Claude Code:

```text
/plugin marketplace add michael-L-i/voicebridge
/plugin install voicebridge@voicebridge-marketplace
```

Restart Claude Code after installation, then run:

```text
/voicebridge:voice-code
```

To update an installed release:

```text
/plugin marketplace update voicebridge-marketplace
/plugin update voicebridge@voicebridge-marketplace
```

Then fully exit every running Claude Code session that loaded VoiceBridge and
restart Claude Code. Updating the marketplace changes the installed files but
cannot replace an MCP process that is already running; `voice_start` reports the
runtime version and capture settings so stale sessions are detected explicitly.

## First run

The first start creates a private Python environment. The first voice session
asks macOS for microphone access and validates audio before downloading the
configured speech models. Model downloads can take several minutes and several
gigabytes; low disk space is reported as a warning. Later turns reuse the
loaded models until the conversation ends.

## Configuration

The first run creates `config.toml`. Codex and direct development use
`~/.voicebridge`; Claude Code uses its persistent per-plugin data directory.
The supported settings are:

```toml
config_version = 2

[tts]
provider = "kokoro"
model = "mlx-community/Kokoro-82M-bf16"
voice = "af_heart"
speed = 1.0

[stt]
provider = "parakeet"
model = "mlx-community/parakeet-tdt-0.6b-v3"
silence_ms = 2000
max_listen_ms = 30000

[audio]
input_device = "default"
output_device = "default"
```

Upgrades from the old architecture automatically remove obsolete `[daemon]`
and `[summarizer]` sections while preserving these speech and audio settings.
The speech-model libraries keep their normal user caches, so downloaded model
weights can be reused across hosts.

Removing the Codex plugin does not delete `~/.voicebridge`. To remove its Codex
configuration and private Python environment as well, delete that directory
manually after stopping every VoiceBridge session.

## Development

Python 3.11 or newer is required.

```bash
python -m pip install -e .
voicebridge doctor
voicebridge listen-test
python -m unittest discover -s tests -v
```

The plugin MCP tools are `voice_start`, `voice_speak`, `voice_listen`,
`voice_stop`, and `voice_status`. `voice_speak` always plays the exact text the
host supplies; it never rewrites or summarizes that text locally.
`voice_status` reports the host, first-run state, running package version, and
effective endpointing settings, which is useful for confirming an update
actually restarted the MCP process.

## CI and releases

Pull requests and pushes to `main` run the locked dependency checks, plugin
contract validation, unit tests, and a package build on GitHub's Apple Silicon
`macos-14` runner for Python 3.11 and 3.13, including a fresh-process MLX
native-import smoke check. The release workflow repeats those checks for a
published GitHub release and verifies that its `vX.Y.Z` tag matches the package
version. It validates build artifacts only; it does not publish to PyPI or
require publishing credentials. See [RELEASING.md](RELEASING.md) for the
maintainer procedure.

## Contributing and support

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) for setup,
testing, and pull request guidance. Use
[GitHub Discussions](https://github.com/michael-L-i/voicebridge/discussions) for
questions and the structured [issue forms](https://github.com/michael-L-i/voicebridge/issues/new/choose)
for bugs and concrete feature proposals.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report security issues
privately as described in [SECURITY.md](SECURITY.md).

## License

VoiceBridge is released under the [MIT License](LICENSE).
