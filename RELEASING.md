# Releasing Cadence Code

Cadence Code releases are source releases for the Codex and Claude Code
marketplaces. The repository does not publish to PyPI, Homebrew, or any other
package registry. The default-branch marketplace snapshots are the distribution
channel: merging a bumped manifest version to `main` makes that source available
to users who refresh and update, even before a matching GitHub Release exists.
Treat the merge as publication, not as a private staging step.

## Before creating a release

Use the committed `uv.lock` rather than resolving a new dependency set:

```bash
uv lock --check
uv sync --locked --python 3.13
uv run --locked python scripts/validate_plugin.py
uv run --locked python -m unittest discover -s tests -v
```

For a version change, update every version-bearing contract together:

- `pyproject.toml`
- `uv.lock` (regenerate it after changing the project version)
- `.claude-plugin/plugin.json`
- `.codex-plugin/plugin.json`
- the hardcoded expected version in `tests/test_plugin_contracts.py`

Before merging, push the exact candidate commit and manually dispatch
`Release verification` against its branch or full SHA. Do not leave the input
at a default-branch value or substitute a nearby commit. For example:

```bash
gh workflow run release-verify.yml --ref main -f ref="$(git rev-parse HEAD)"
```

Wait for the complete macOS/Python matrix to pass before merging. The manual
run is the pre-publication gate; the automatic run after publishing the GitHub
Release remains a defense-in-depth check of the tag itself.

## Manual release checklist

Exercise all four paths: fresh Codex install, Codex upgrade from the previous
version, fresh Claude Code install, and Claude Code upgrade from the previous
version. Stop one test session completely before starting the next because the
machine-wide audio lock permits only one conversation. Before merge, use a
temporary GitHub-backed test marketplace pinned to the pushed candidate branch
or SHA; do not use a local checkout override.

For each fresh test:

- Use clean Cadence Code plugin data, confirm first-run setup appears, and accept
  the default Pocket TTS 100M and Parakeet 110M choices.
- Open Cadence Code Settings, confirm the saved choices, make and persist a
  temporary model change, then restore the intended defaults.

For each upgrade test:

- Refresh the GitHub-backed test marketplace, update the installed plugin,
  fully restart the host, and confirm existing model and audio settings remain
  while first-run setup stays skipped.

For every path:

- Verify the installed source is the intended candidate ref, not `./dev`,
  `--plugin-dir`, a checkout MCP override, or a stale cache, and record the
  source commit and manifest version.
- Confirm `voice_status` reports the new version and the correct host
  (`codex` or `claude-code`) after the required host restart.
- Start Voice Code, speak a response, listen and transcribe a reply, exercise
  the explicit interrupt flow, then stop and confirm the session releases.
- Start a second new host process and repeat the status/start/stop smoke test to
  catch stale MCP processes and restart-only failures.

## Release procedure

1. Complete the locked checks, pre-merge manual workflow dispatch, and manual
   candidate checklist above.
2. Merge the reviewed version-change pull request after every required check
   passes. The refreshed marketplace snapshot is now the released source.
3. Refresh the normal GitHub-backed marketplaces for both hosts, update and
   restart, then repeat the source, version/host, and start/stop checks. Confirm
   they resolve the merged default-branch commit rather than the temporary test
   marketplace or a cached copy.
4. Create and push an annotated `vX.Y.Z` tag from the merged commit, then
   publish the matching GitHub Release with curated notes. Summarize user-visible
   changes, upgrade and restart instructions, compatibility or model/config
   changes, migrations or breaking changes, and known issues (or explicitly say
   there are none). Include the verification performed; do not publish an
   unedited commit dump as the release notes.
5. The `Release verification` workflow checks out that tag, confirms its name
   matches `pyproject.toml`, then runs the locked plugin and unit checks and
   builds and inspects the wheel and sdist across macOS 14, 15, and 26 on
   Python 3.11 through 3.14.
6. Confirm that post-publish workflow is green before announcing the release or
   directing users to update their marketplace installation.

Cadence Code deliberately uses the generic GitHub tag `vX.Y.Z` because one
repository release serves both Codex and Claude Code. Current Claude Code's
`claude plugin tag` command instead proposes the plugin-specific
`cadence-code--vX.Y.Z` convention. That Claude-specific tag is not required for
default-branch marketplace refreshes and must not replace the generic tag on a
GitHub Release; the existing release verification intentionally continues to
require `vX.Y.Z`.

The release workflow intentionally does not publish packages, upload release
assets, or require credentials beyond GitHub's read-only workflow token. Its
required manual input identifies the exact candidate branch or SHA; the
published-release trigger independently verifies the final generic tag.

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
