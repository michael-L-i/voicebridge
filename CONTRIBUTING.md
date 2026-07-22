# Contributing to VoiceBridge

Thanks for helping improve VoiceBridge. Bug reports, focused fixes,
documentation improvements, and carefully scoped features are welcome.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
By submitting a contribution, you agree that it may be distributed under the
project's [MIT License](LICENSE).

## Before you start

- Search existing issues and pull requests before opening a new one.
- Use a GitHub Discussion for setup help and general questions.
- Open an issue before investing in a large change so its scope and product fit
  can be discussed first.
- Never include credentials, private transcripts, recordings, model caches, or
  other sensitive data in an issue or pull request.

VoiceBridge is deliberately local and narrowly scoped. Contributions should
preserve the boundaries described in the README: no cloud services, telemetry,
detached daemon, passive narration, or second language model unless the project
direction is explicitly changed first.

## Development setup

Development requires an Apple Silicon Mac running macOS 14 or newer and Python
3.11 through 3.14. From the repository root:

```bash
uv sync --locked --python 3.13
./dev check
uv run --locked python scripts/validate_plugin.py
uv run --locked voicebridge doctor
```

The first real voice session can download several speech-model files. Unit
tests do not load the models or access the microphone.

`uv.lock` is the source of truth for development, CI, and production runtime
dependencies. The plugin bootstrap installs the hashed `requirements.lock`
export so user environments resolve the same versions. After an intentional
lockfile change, regenerate that export with:

```bash
uv export --locked --no-dev --no-emit-project --no-annotate --no-header \
  --output-file requirements.lock
```

Run `uv lock --check` before opening a pull request. CI also verifies that the
committed export still exactly matches `uv.lock`.

To inspect the checkout's MCP tools without installing either host plugin, run:

```bash
./dev inspector
```

This uses an isolated `.voicebridge-dev/` data directory. Opening the Inspector
can install the Python dependencies, but model weights are not downloaded until
you call `voice_start`.

To test the complete Claude Code flow from the checkout without installing a
plugin or marketplace, run:

```bash
./dev claude
```

Then invoke `/voicebridge:voice-code`. Claude Code loads the checkout directly
with `--plugin-dir`, while VoiceBridge keeps its development environment and
configuration under `.voicebridge-dev/claude/`.

Use `./dev claude --fresh` to exercise first-run model selection again. It
clears only the development configuration and onboarding marker, retaining the
private venv so dependency setup does not repeat.

Codex can exercise the same checkout without installing its plugin or adding a
marketplace:

```bash
./dev codex
```

Then invoke `$voice-code`. The launcher supplies the local MCP server through
one-session Codex overrides, and the repository exposes the canonical skill
through `.agents/skills/`. No user-level Codex configuration is changed.

Use `./dev codex --fresh` to repeat first-run model selection without rebuilding
the development venv.

When you need to discard every local-development venv and configuration, first
close Claude Code, Codex, and MCP Inspector sessions using VoiceBridge, then run:

```bash
./dev reset
```

The command moves only `.voicebridge-dev/` to macOS Trash. It does not touch an
installed plugin's data or the speech libraries' shared model caches.

## Making a change

1. Fork the repository and create a short-lived branch from `main`.
2. Keep the patch focused. Avoid unrelated refactors or formatting churn.
3. Add or update tests for behavior changes.
4. Update user-facing documentation when configuration or behavior changes.
5. Run the locked unit and plugin checks, including `./dev check`, before
   opening a pull request.

For changes involving audio devices, model loading, or the MCP lifecycle, also
run the narrowest relevant manual check on Apple Silicon:

```bash
voicebridge doctor
voicebridge listen-test
```

A full voice-mode change should be exercised through
`voice_start`/`voice_speak`/`voice_interrupt`/`voice_listen`/`voice_stop` in a
real Claude Code session. Note what you tested in the pull request; do not
attach recordings unless everyone captured in them has consented.

## Pull requests

Pull requests should explain the problem, the chosen approach, and how the
change was verified. Small pull requests are easier to review and merge.

All automated checks must pass. A maintainer review is required, and review
conversations must be resolved before merge. Maintainers may ask for a change
to be split or simplified when that makes the project easier to maintain.

## Reporting security problems

Do not open a public issue for a suspected vulnerability. Follow the private
reporting instructions in [SECURITY.md](SECURITY.md).
