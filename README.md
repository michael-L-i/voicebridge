# voicebridge

[![CI](https://github.com/michael-L-i/voicebridge/actions/workflows/ci.yml/badge.svg)](https://github.com/michael-L-i/voicebridge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)

VoiceBridge is a local voice conversation plugin for Claude Code on Apple
Silicon. Run `/voicebridge:voice-code`, talk naturally, and let Claude Code
decide what to say back.

The plugin is deliberately small:

- Claude Code controls the conversation and writes every spoken response.
- Kokoro converts Claude's text to speech.
- Parakeet transcribes microphone audio back to text.
- The plugin does not run a daemon, a summarizer, or a second language model.

Detailed answers stay on screen. Claude sends a separate concise version to
speech, so audio sounds like a coworker giving you the useful part instead of
reading a terminal response verbatim.

## How it works

Claude Code starts one lightweight stdio MCP server with the plugin. The server
does not load speech models until voice mode begins. `voice_start` loads Kokoro
and Parakeet into that MCP process, the same model instances are reused between
turns, and `voice_stop` releases them and clears the MLX cache.

VoiceBridge does use MLX, but only for speech inference:

- TTS: `mlx-community/Kokoro-82M-bf16` through MLX Audio
- STT: `mlx-community/parakeet-tdt-0.6b-v3` through MLX Audio

There is no Qwen call and no `mlx-lm` import in VoiceBridge. MLX Audio currently
declares `mlx-lm` as a transitive package dependency, so its executable may be
present in the private environment even though VoiceBridge never invokes it.

Only one voice conversation can own the microphone, speakers, and model memory
at a time. An advisory lock prevents two Claude Code sessions from interfering
with one another. Speech playback and microphone capture are also serialized;
there is no echo cancellation.

## Install

In Claude Code:

```text
/plugin marketplace add michael-L-i/voicebridge
/plugin install voicebridge@voicebridge-marketplace
```

Restart Claude Code after installation, then run:

```text
/voicebridge:voice-code
```

The first start creates a private Python environment. The first voice session
may also download the configured speech models. Later turns reuse the loaded
models until the conversation ends.

To update an installed release:

```text
/plugin marketplace update voicebridge-marketplace
/plugin update voicebridge@voicebridge-marketplace
```

Then fully exit every running Claude Code session that loaded VoiceBridge and
restart Claude Code. Updating the marketplace changes the installed files but
cannot replace an MCP process that is already running; `voice_start` reports the
runtime version and capture settings so stale sessions are detected explicitly.

## Configuration

The first run creates `config.toml` in Claude Code's persistent plugin data
directory. The supported settings are:

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

## Development

Python 3.11 or newer is required.

```bash
python -m pip install -e .
voicebridge doctor
voicebridge listen-test
python -m unittest discover -s tests -v
```

The plugin MCP tools are `voice_start`, `voice_speak`, `voice_listen`,
`voice_stop`, and `voice_status`. `voice_speak` always plays the exact text
Claude Code supplies; it never rewrites or summarizes that text locally.
`voice_status` reports the running package version and effective endpointing
settings, which is useful for confirming an update actually restarted the MCP
process.

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
