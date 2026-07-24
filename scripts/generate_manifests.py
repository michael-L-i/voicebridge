#!/usr/bin/env python3
"""Write every per-host manifest from scripts/host_manifests.py.

    python scripts/generate_manifests.py            # rewrite the manifests
    python scripts/generate_manifests.py --check    # fail on any drift

``--check`` runs inside ``scripts/validate_plugin.py`` and therefore in CI, so a
hand-edited manifest fails the build with the exact diff to reapply upstream.
"""

from __future__ import annotations

import argparse
import difflib
import sys

from host_manifests import ROOT, manifests, render


def drift() -> list[str]:
    """Return a unified diff per manifest that differs from its source."""
    diffs: list[str] = []
    for relative_path, manifest in sorted(manifests().items()):
        expected = render(manifest)
        path = ROOT / relative_path
        actual = path.read_text(encoding="utf-8") if path.is_file() else ""
        if actual == expected:
            continue
        diffs.append(
            "".join(
                difflib.unified_diff(
                    actual.splitlines(keepends=True),
                    expected.splitlines(keepends=True),
                    fromfile=f"{relative_path} (on disk)",
                    tofile=f"{relative_path} (generated)",
                )
            )
        )
    return diffs


def write() -> list[str]:
    """Write every manifest, returning the paths that changed."""
    changed: list[str] = []
    for relative_path, manifest in sorted(manifests().items()):
        expected = render(manifest)
        path = ROOT / relative_path
        if path.is_file() and path.read_text(encoding="utf-8") == expected:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected, encoding="utf-8")
        changed.append(relative_path)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift instead of rewriting the manifests",
    )
    arguments = parser.parse_args()

    if arguments.check:
        diffs = drift()
        if diffs:
            for diff in diffs:
                print(diff, end="", file=sys.stderr)
            print(
                "\n[fail] manifests are stale. Edit scripts/host_manifests.py, "
                "then run: python scripts/generate_manifests.py",
                file=sys.stderr,
            )
            return 1
        print(f"[ok] {len(manifests())} host manifests match their source")
        return 0

    changed = write()
    for relative_path in changed:
        print(f"[write] {relative_path}")
    print(f"[ok] {len(manifests())} host manifests generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
