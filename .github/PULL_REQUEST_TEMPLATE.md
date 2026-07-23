## What changed?

<!-- Explain the problem and the approach. Keep the pull request focused. -->

## How was it tested?

<!-- List automated tests and any Apple Silicon/manual voice checks. -->

## Checklist

- [ ] I kept this change within Cadence Code's local-first product scope.
- [ ] I added or updated tests for behavior changes.
- [ ] I updated documentation for user-facing changes.
- [ ] `uv lock --check` passes locally.
- [ ] `uv run --locked python -m unittest discover -s tests -v` passes locally.
- [ ] `uv run --locked python scripts/validate_plugin.py` passes locally.
- [ ] I ran the relevant Apple Silicon manual check, or this change does not need one.
- [ ] I did not include credentials, private transcripts, recordings, model
      files, or caches.
