# Releasing VoiceBridge

VoiceBridge releases are source releases for the Codex and Claude Code
marketplaces. The repository does not publish to PyPI, Homebrew, or any other
package registry.

## Before creating a release

Use the committed `uv.lock` rather than resolving a new dependency set:

```bash
uv lock --check
uv sync --locked --python 3.13
uv run --locked python scripts/validate_plugin.py
uv run --locked python -m unittest discover -s tests -v
```

For a version change, keep `pyproject.toml`, `.claude-plugin/plugin.json`, and
`.codex-plugin/plugin.json` synchronized. Regenerate and commit `uv.lock` only
when the dependency declaration changes.

## Release procedure

1. Merge the version-change pull request after the macOS CI checks pass.
2. Create and push an annotated `vX.Y.Z` tag from the reviewed commit, then
   publish the matching GitHub release.
3. The `Release verification` workflow checks out that tag, confirms its name
   matches `pyproject.toml`, then runs the locked plugin and unit checks and
   builds and inspects the wheel and sdist across macOS 14, 15, and 26 on
   Python 3.11 through 3.14.
4. Confirm that workflow is green before announcing the release or directing
   users to update their marketplace installation.

The release workflow intentionally does not publish packages, upload release
assets, or require credentials beyond GitHub's read-only workflow token. It can
also be run manually against a branch or tag to rehearse a release build.

## Repository settings to enable once

Configure a branch protection rule or ruleset for `main` that requires
`CI / CI complete` before merging. That aggregate job passes only when every
Apple-Silicon compatibility, package, and dependency-review job has passed.
Require pull requests and a maintainer review as appropriate for the project.
These are repository-owner settings, so they are deliberately not changed by
the workflows themselves.

The workflows run on GitHub-hosted Apple-Silicon images because MLX and the
supported audio stack are Apple-Silicon-specific. Each job imports the locked
native MLX runtime in a fresh process before exercising the unit suite. Model
downloads, microphone permissions, and physical audio devices remain manual
Apple Silicon checks; they cannot be meaningfully or safely automated on a
hosted runner.
