# voicebridge

[![CI](https://github.com/michael-L-i/voicebridge/actions/workflows/ci.yml/badge.svg)](https://github.com/michael-L-i/voicebridge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)

VoiceBridge is a local voice conversation plugin for Codex and Claude Code on
Apple Silicon. Start Voice Code, talk naturally, and let your coding agent
decide what to say back.

The plugin is deliberately small:

- Codex or Claude Code controls the conversation and writes every spoken response.
- The selected local TTS model converts the host's text to speech.
- The selected local STT model transcribes microphone audio back to text.
- The plugin does not run a daemon, a summarizer, or a second language model.

Detailed answers stay on screen. The host sends a separate concise version to
speech, so audio sounds like a coworker giving you the useful part instead of
reading a terminal response verbatim.

## How it works

The host starts one lightweight stdio MCP server with the plugin. The server
does not load speech models until voice mode begins. On a new installation, the
host first presents the available TTS and STT tiers and saves the user's choice.
`voice_start` then checks the configured input and output devices, briefly opens
the microphone without retaining audio, and loads only the selected models.
The same model instances are reused between turns, and `voice_stop` releases
them and clears the MLX cache.

VoiceBridge offers three local options in each direction, ordered by resource
use:

| TTS | Tier | Download |
| --- | --- | ---: |
| Kokoro 82M | Lightweight | 389 MB |
| Chatterbox Turbo 350M | Balanced | 417 MB |
| Qwen 0.6B | Heavy, highest quality | 1.97 GB |

| STT | Tier | Download |
| --- | --- | ---: |
| Moonshine Base 61M | Lightweight | 248 MB |
| Whisper Small.en 244M | Balanced | 485 MB |
| Parakeet 0.6B v3 | Heavy, highest accuracy | 2.51 GB |

Some MLX Audio speech implementations reuse `mlx-lm` cache and sampling
utilities internally. VoiceBridge does not load a local reasoning or
summarization model; those utilities are only inference plumbing for speech.

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

The first start creates a private Python environment. Before any model download,
Voice Code asks the user to choose one TTS and one STT tier, with Qwen and
Whisper preselected. It then asks macOS for microphone access and validates
audio before downloading only that pair. Model downloads can take several
minutes; low disk space is reported as a warning. Existing installations keep
their current configuration and skip the chooser.

## Configuration

The first run creates `config.toml`. Codex and direct development use
`~/.voicebridge`; Claude Code uses its persistent per-plugin data directory.
The supported settings are:

```toml
config_version = 2

[tts]
provider = "qwen"
model = "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit"
voice = "Aiden"
speed = 1.0

[stt]
provider = "whisper"
model = "mlx-community/whisper-small.en-asr-fp16"
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

VoiceBridge supports Apple Silicon Macs running macOS 14 or newer and Python
3.11 through 3.14. Newer Python versions are added after their MLX dependency
stack is available and validated.

```bash
python -m pip install -e .
voicebridge doctor
voicebridge listen-test
./dev check
./dev inspector
./dev claude
./dev claude --fresh
./dev codex
./dev codex --fresh
./dev reset
```

The plugin MCP tools are `voice_models`, `voice_configure`, `voice_start`,
`voice_speak`, `voice_listen`, `voice_stop`, and `voice_status`.
`voice_models` reports the ordered local choices without downloading them, and
`voice_configure` persists a pair before a voice session begins. `voice_speak`
always plays the exact text the host supplies; it never rewrites or summarizes
that text locally. `voice_status` reports the host, first-run state, running
package version, and effective endpointing settings, which is useful for
confirming an update actually restarted the MCP process.

## CI and releases

Pull requests and pushes to `main` run locked dependency checks, plugin
contract validation, unit tests, and a fresh-process MLX native-import smoke
check across every supported GitHub-hosted Apple-Silicon macOS image
(`macos-14`, `macos-15`, and `macos-26`) and Python 3.11 through 3.14. Package
artifacts are built and inspected once on macOS 14 / Python 3.14. The release
workflow repeats the compatibility matrix for a published GitHub release and
verifies that its `vX.Y.Z` tag matches the package version. It validates build
artifacts only; it does not publish to PyPI or require publishing credentials.
See [RELEASING.md](RELEASING.md) for the maintainer procedure.

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
