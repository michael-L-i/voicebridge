# voicebridge

[![CI](https://github.com/michael-L-i/voicebridge/actions/workflows/ci.yml/badge.svg)](https://github.com/michael-L-i/voicebridge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11-3.14](https://img.shields.io/badge/Python-3.11--3.14-blue.svg)](https://www.python.org/)

VoiceBridge is a local voice conversation plugin for Codex and Claude Code on
Apple Silicon. Start Voice Code, talk naturally, and let your coding agent
decide what to say back.

See [VoiceBridge privacy](PRIVACY.md) for the precise local-processing and host
handoff boundary.

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

VoiceBridge offers several local options in each direction, ordered by
resource use:

| TTS model card | Tier | Language in VoiceBridge | License | Download |
| --- | --- | --- | --- | ---: |
| [Pocket TTS 100M](https://huggingface.co/mlx-community/pocket-tts) | Lightweight | English | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | 236 MB |
| [Kokoro 82M](https://huggingface.co/mlx-community/Kokoro-82M-bf16) | Lightweight | English | [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) | 389 MB |
| [Chatterbox Turbo 350M](https://huggingface.co/mlx-community/chatterbox-turbo-4bit) | Balanced | English | [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) | 417 MB |
| [Qwen 0.6B](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit) | Heavy, highest quality | English | [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) | 1.97 GB |

| STT model card | Tier | Language | License | Download |
| --- | --- | --- | --- | ---: |
| [Moonshine Base 61M](https://huggingface.co/UsefulSensors/moonshine-base) | Lightweight | English | [MIT](https://opensource.org/license/mit) | 248 MB |
| [Parakeet 110M](https://huggingface.co/mlx-community/parakeet-tdt_ctc-110m) | Balanced | English | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | 459 MB |
| [Parakeet 0.6B v3](https://huggingface.co/mlx-community/parakeet-tdt-0.6b-v3) | Heavy, highest accuracy | 25 languages | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | 2.51 GB |

The built-in TTS paths are currently English-only. Moonshine and Parakeet 110M
are English transcription models; choose Parakeet 0.6B v3 for multilingual
transcription. Follow each model card for its upstream limitations and license
terms.

Some MLX Audio speech implementations reuse `mlx-lm` cache and sampling
utilities internally. VoiceBridge does not load a local reasoning or
summarization model; those utilities are only inference plumbing for speech.

Only one voice conversation can own the microphone, speakers, and model memory
at a time. A machine-wide advisory lock prevents Codex, Claude Code, or direct
development sessions from interfering with one another. Speech playback and
microphone capture are also serialized; there is no echo cancellation.

## Requirements

Before installing, confirm that the Mac has:

- Apple Silicon and macOS 14 or newer.
- Python 3.11 through 3.14 available on `PATH`.
- A working microphone and audio output device, with microphone permission for
  the host application.
- Internet access for the initial locked dependency install and selected model
  downloads.
- Disk space for a private Python environment plus the selected model pair.
  Model weights range from about 484 MB to 4.48 GB; the default Pocket TTS and
  Parakeet 110M pair is about 695 MB. Cached models are shared with other local
  Hugging Face applications.

## Privacy boundary

Microphone access begins only after the user explicitly invokes Voice Code.
Raw audio is held in memory for local STT and is not saved by VoiceBridge; TTS
also runs locally. The resulting transcript is handed to Codex or Claude Code,
which may process and retain it under that host's separate settings and privacy
policy. VoiceBridge has no telemetry and does not send recordings or
transcripts to its developer. Initial dependency and model downloads do contact
their package hosts. See [PRIVACY.md](PRIVACY.md) for details and local storage
locations.

## Install for Codex

VoiceBridge works in the Codex CLI and desktop app. The Codex IDE extension does
not currently support plugins. Add this repository as a marketplace and install
the plugin from a terminal:

```bash
codex plugin marketplace add michael-L-i/voicebridge
codex plugin add voicebridge@voicebridge-marketplace
```

Start a new Codex session after installation. Invoke `$voice-code` in a prompt,
or select Voice Code from `/skills`. To change the saved speech models later,
invoke `$voice-settings` or choose VoiceBridge Settings from `/skills`.

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

To change the saved speech models later, run:

```text
/voicebridge:voice-settings
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

The plugin's first MCP start downloads locked Python dependencies into a private
environment. Before any model download, Voice Code asks the user to choose one
TTS and one STT tier, with Pocket and Parakeet 110M preselected. It then asks
macOS for microphone access and validates audio before downloading only that
pair from Hugging Face. Setup can take several minutes; low disk space is
reported as a warning. Existing installations keep their current configuration
and skip the chooser. Use VoiceBridge Settings to open the same model selectors
again at any time; after confirmation, it stops an active voice session before
applying the new pair.

Kokoro's English text pipeline is installed with the private environment. It
does not install Python packages or require network access during synthesis;
only the selected speech model weights may be downloaded when voice mode starts.

## Configuration

The first run creates `config.toml`. Codex and direct development use
`~/.voicebridge`; Claude Code uses its persistent per-plugin data directory.
The supported settings are:

```toml
config_version = 3

[tts]
provider = "pocket"
model = "mlx-community/pocket-tts"
voice = "alba"
speed = 1.0

[stt]
provider = "parakeet"
model = "mlx-community/parakeet-tdt_ctc-110m"
silence_ms = 1000
max_listen_ms = 30000

[audio]
input_device = "default"
output_device = "default"
```

Upgrades from the old architecture automatically remove obsolete `[daemon]`
and `[summarizer]` sections while preserving these speech and audio settings.
The speech-model libraries keep their normal user caches, so downloaded model
weights can be reused across hosts.

### Model storage and cleanup

Speech weights are stored in Hugging Face's shared cache at
`~/.cache/huggingface/hub`, not in VoiceBridge's data directory. Switching a
model downloads the new choice but deliberately keeps the previous one so
other local MLX tools can reuse it.

After stopping every VoiceBridge session, inspect the cache and interactively
remove only model repositories you no longer use:

```bash
hf cache scan
hf cache delete --sort size
```

For example, VoiceBridge's current Qwen and Parakeet repositories appear as
`models--mlx-community--Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit` and
`models--mlx-community--parakeet-tdt_ctc-110m`. Avoid deleting the whole
Hugging Face cache: it is shared with other local applications.

## Troubleshooting

- **No microphone or output:** allow microphone access for Codex or Claude Code
  in macOS **System Settings > Privacy & Security > Microphone**, verify the
  `[audio]` device settings, then restart the host.
- **Setup or model download fails:** confirm the supported Python version,
  internet access, and free disk space, then restart the host to retry. A failed
  dependency rebuild leaves the previous environment unchanged.
- **Session already in use:** stop Voice Code in every Codex, Claude Code, and
  development session. Only one process can own the audio session.
- **An update still reports the old version:** fully exit every host process
  that loaded VoiceBridge and start a new one; running MCP processes are not
  replaced in place.

For a checkout-based diagnosis, run `uv run --locked voicebridge doctor`. Use
`uv run --locked voicebridge listen-test` for a manual microphone test.

## Uninstall

Stop every VoiceBridge session first. For Codex:

```bash
codex plugin remove voicebridge@voicebridge-marketplace
codex plugin marketplace remove voicebridge-marketplace
```

Codex removal leaves configuration and the private environment in
`~/.voicebridge`; remove that directory manually if the data is no longer
wanted.

For Claude Code:

```bash
claude plugin uninstall voicebridge@voicebridge-marketplace
claude plugin marketplace remove voicebridge-marketplace
```

Claude Code prompts about its persistent plugin data during uninstall; do not
choose `--keep-data` if configuration and the private environment should also be
removed. Model weights remain in the shared Hugging Face cache for both hosts;
use the targeted cache commands above to inspect and remove only unwanted
repositories.

## Development

VoiceBridge supports Apple Silicon Macs running macOS 14 or newer and Python
3.11 through 3.14. Newer Python versions are added after their MLX dependency
stack is available and validated. `uv.lock` is the source of truth for local
development and CI.

```bash
uv lock --check
uv sync --locked --python 3.13
uv run --locked voicebridge doctor
uv run --locked voicebridge listen-test
uv run --locked python scripts/validate_plugin.py
./dev check
./dev inspector
./dev claude
./dev claude --fresh
./dev codex
./dev codex --fresh
./dev reset
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before intentionally changing the lock or
its production `requirements.lock` export.

The plugin MCP tools are `voice_models`, `voice_configure`, `voice_start`,
`voice_speak`, `voice_listen`, `voice_interrupt`, `voice_stop`, and
`voice_status`.
`voice_models` reports the ordered local choices without downloading them, and
`voice_configure` persists a pair before a voice session begins. `voice_speak`
always plays the exact text the host supplies; it never rewrites or summarizes
that text locally. Both `voice_speak` and `voice_listen` require a successful
explicit `voice_start`; they never run audio preflight, acquire the audio
session, or download or load models implicitly. If called too early, they
return `error_code: "session_not_started"` without changing first-run state.
After stopping the host's current turn with Escape, `voice_interrupt`
immediately silences current audio and captures added spoken guidance without
unloading the models.
`voice_status` reports the host, first-run state, running package version, and
effective endpointing settings, which is useful for confirming an update
actually restarted the MCP process.

## CI and releases

Pull requests and pushes to `main` verify the production requirements export,
bootstrap the plugin from an empty data directory, then run plugin contracts,
unit tests, and an MLX native-import smoke check in that production-style
environment. The matrix covers every supported GitHub-hosted Apple-Silicon
macOS image (`macos-14`, `macos-15`, and `macos-26`) and Python 3.11 through
3.14. Package artifacts are built and inspected once on macOS 14 / Python
3.14. The release workflow repeats the bootstrapped compatibility matrix for a
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
