# voicebridge

[![CI](https://github.com/michael-L-i/voicebridge/actions/workflows/ci.yml/badge.svg)](https://github.com/michael-L-i/voicebridge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11-3.14](https://img.shields.io/badge/Python-3.11--3.14-blue.svg)](https://www.python.org/)

A local voice interface for Codex and Claude Code on Apple Silicon. Start Voice
Code, talk naturally, and let your coding agent decide what to say back — no
daemon, no cloud, no second language model in the loop. See
[VoiceBridge privacy](PRIVACY.md) for the exact local-processing and host
handoff boundary.

## Requirements

- Apple Silicon Mac, macOS 14+
- Python 3.11-3.14 on `PATH`
- A working microphone and output device, with mic permission for the host app
- Internet access for the initial install and selected model downloads
- ~500 MB-4.5 GB disk space depending on the models you pick (shared with other
  local Hugging Face apps)

## Install

**Claude Code**

```text
/plugin marketplace add michael-L-i/voicebridge
/plugin install voicebridge@voicebridge-marketplace
```

Restart Claude Code, then run `/voicebridge:voice-code`.

**Codex** (CLI and desktop app; the IDE extension doesn't support plugins yet)

```bash
codex plugin marketplace add michael-L-i/voicebridge
codex plugin add voicebridge@voicebridge-marketplace
```

Start a new Codex session, then run `$voice-code` (or pick Voice Code from
`/skills`).

On first run you'll pick a TTS and STT model (Pocket + Parakeet 110M are
preselected), grant microphone access, and the chosen pair downloads
automatically. Change your choice anytime with `/voicebridge:voice-settings`
(Claude Code) or `$voice-settings` (Codex).

If Claude Code's voice tools are still connecting on first use, Voice Code
finishes the one-time dependency setup and asks you to run `/reload-plugins`
before invoking it again.

To update, re-run the marketplace/plugin update commands for your host, then
fully restart it — an already-running MCP process isn't replaced in place.

## How it works

VoiceBridge runs one lightweight stdio MCP server alongside your coding agent.
The agent decides what to say and writes every spoken response; VoiceBridge
just converts that text to speech and your replies back to text, using local
MLX models. Detailed answers stay on screen — voice gets a short, separately
composed version, like a coworker giving you the useful part instead of
reading a terminal response aloud.

Only one voice conversation can hold the microphone and model memory at a
time, enforced by a machine-wide lock so Codex, Claude Code, and dev sessions
never collide.

## Model choices

| TTS model card | Tier | Language | License | Download |
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

TTS is currently English-only. For multilingual transcription, choose
Parakeet 0.6B v3. Follow each model card for its upstream license terms.

## Configuration

Settings live in `config.toml` — `~/.voicebridge` for Codex and direct
development, or Claude Code's per-plugin data directory. It has `[tts]`,
`[stt]`, and `[audio]` sections for model, voice, speed, endpointing, and
device choices; upgrades migrate old configs automatically.

Model weights are cached in Hugging Face's shared cache
(`~/.cache/huggingface/hub`), not VoiceBridge's own directory, so switching
models keeps the previous one for other local MLX tools to reuse. Clean up
manually with:

```bash
hf cache scan
hf cache delete --sort size
```

## Troubleshooting

- **No microphone or output:** allow mic access for Codex or Claude Code in
  macOS **System Settings > Privacy & Security > Microphone**, verify the
  `[audio]` device settings, then restart the host.
- **Setup or model download fails:** confirm the supported Python version,
  internet access, and free disk space, then restart the host to retry.
- **Session already in use:** stop Voice Code in every Codex, Claude Code, and
  dev session — only one process can own the audio session at a time.
- **An update still reports the old version:** fully exit every host process
  that loaded VoiceBridge and start a new one.

For a checkout-based diagnosis, run `uv run --locked voicebridge doctor` or
`uv run --locked voicebridge listen-test`.

## Uninstall

Stop every VoiceBridge session first.

```bash
# Codex
codex plugin remove voicebridge@voicebridge-marketplace
codex plugin marketplace remove voicebridge-marketplace

# Claude Code
claude plugin uninstall voicebridge@voicebridge-marketplace
claude plugin marketplace remove voicebridge-marketplace
```

Both leave configuration and the private Python environment behind (decline
`--keep-data` in Claude Code to remove them too); delete `~/.voicebridge`
manually for Codex. Model weights stay in the shared Hugging Face cache — use
the cache commands above to remove specific ones.

## Development

`uv.lock` is the source of truth for local development and CI.

```bash
uv sync --locked --python 3.13
uv run --locked voicebridge doctor
./dev check    # tests + plugin validation
./dev claude   # local branch test in Claude Code
./dev codex    # local branch test in Codex
```

See [AGENTS.md](AGENTS.md) for the full project map and MCP tool reference,
and [CONTRIBUTING.md](CONTRIBUTING.md) before changing the lock file. CI and
release details are in [RELEASING.md](RELEASING.md).

## Contributing and support

Contributions are welcome. Use
[GitHub Discussions](https://github.com/michael-L-i/voicebridge/discussions)
for questions and the
[issue forms](https://github.com/michael-L-i/voicebridge/issues/new/choose)
for bugs and feature proposals.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report security
issues privately as described in [SECURITY.md](SECURITY.md).

## License

VoiceBridge is released under the [MIT License](LICENSE).
