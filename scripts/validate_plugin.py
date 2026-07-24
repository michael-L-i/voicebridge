#!/usr/bin/env python3
"""Validate repository-owned plugin contracts without loading speech models.

Per-host manifest *fields* are not asserted here. They are generated from
``scripts/host_manifests.py``, so this checks that the files on disk still match
that source and then validates what generation cannot: the skill symlinks, the
required file set, and the bash that actually launches the server.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from generate_manifests import drift
from host_manifests import ROOT, manifests, project_version


def validate_generated_manifests(failures: list[str]) -> None:
    """Fail when a manifest was hand-edited instead of regenerated."""
    diffs = drift()
    for diff in diffs:
        print(diff, end="", file=sys.stderr)
    if diffs:
        failures.append(
            f"{len(diffs)} manifest(s) drifted from scripts/host_manifests.py; "
            "run: python scripts/generate_manifests.py"
        )


def validate_launcher_programs(failures: list[str]) -> None:
    """Check every generated ``bash -c`` launcher for syntax and stdout purity.

    These programs are the first thing a host executes. A syntax error or a
    stray stdout write corrupts the MCP JSON-RPC handshake, and neither failure
    is visible until a real host session dies.
    """
    for relative_path, manifest in sorted(manifests().items()):
        # Cursor's plugin.json points at a sibling file rather than inlining.
        servers = manifest.get("mcpServers", {})
        if not isinstance(servers, dict):
            continue
        for name, server in servers.items():
            if not isinstance(server, dict):
                continue
            arguments = server.get("args") or []
            if server.get("command") != "bash" or arguments[:1] != ["-c"]:
                continue
            program = arguments[1]
            syntax = subprocess.run(
                ["bash", "-n", "-c", program],
                capture_output=True,
                text=True,
                check=False,
            )
            if syntax.returncode:
                failures.append(
                    f"{relative_path}: {name} launcher is invalid bash: "
                    f"{syntax.stderr.strip()}"
                )
            for statement in program.split("; "):
                if statement.startswith("echo ") and ">&2" not in statement:
                    failures.append(
                        f"{relative_path}: {name} launcher writes to stdout, "
                        f"which corrupts the MCP channel: {statement}"
                    )


def validate_development_skills(failures: list[str]) -> None:
    canonical_root = ROOT / "skills"
    development_root = ROOT / ".agents/skills"
    canonical_skills = {
        path.name for path in canonical_root.iterdir() if path.is_dir()
    }
    development_skills = {path.name for path in development_root.iterdir()}

    for name in sorted(canonical_skills - development_skills):
        failures.append(f"Codex development skill is missing: .agents/skills/{name}")
    for name in sorted(development_skills - canonical_skills):
        failures.append(f"unexpected Codex development skill: .agents/skills/{name}")
    for name in sorted(canonical_skills & development_skills):
        development_skill = development_root / name
        expected_target = Path("../../skills") / name
        if not development_skill.is_symlink():
            failures.append(
                f"Codex development skill must be a symlink: .agents/skills/{name}"
            )
        elif development_skill.readlink() != expected_target:
            failures.append(
                f"Codex development skill must point to {expected_target}: "
                f".agents/skills/{name}"
            )


def main() -> int:
    version = project_version()
    failures: list[str] = []

    if (ROOT / ".mcp.json").exists():
        failures.append("Codex MCP configuration must be bundled in the manifest")

    validate_generated_manifests(failures)
    validate_launcher_programs(failures)
    validate_development_skills(failures)

    required_paths = [
        *sorted(manifests()),
        "bin/cadence-code-mcp-bootstrap",
        "commands/jump-in.md",
        "commands/start-talking.md",
        "commands/voice-settings.md",
        "commands/wrap-up.md",
        "config/default_config.toml",
        "requirements.lock",
        "skills/jump-in/SKILL.md",
        "skills/jump-in/agents/openai.yaml",
        "skills/start-talking/SKILL.md",
        "skills/start-talking/agents/openai.yaml",
        "skills/start-talking/scripts/setup",
        "skills/voice-settings/SKILL.md",
        "skills/voice-settings/agents/openai.yaml",
        "skills/wrap-up/SKILL.md",
        "skills/wrap-up/agents/openai.yaml",
    ]
    for relative_path in required_paths:
        if not (ROOT / relative_path).is_file():
            failures.append(f"required plugin file is missing: {relative_path}")

    bootstrap = ROOT / "bin/cadence-code-mcp-bootstrap"
    syntax = subprocess.run(
        ["bash", "-n", str(bootstrap)], capture_output=True, text=True, check=False
    )
    if syntax.returncode:
        failures.append(f"bootstrap has invalid bash syntax: {syntax.stderr.strip()}")

    if failures:
        for failure in failures:
            print(f"[fail] {failure}", file=sys.stderr)
        return 1

    print(f"[ok] plugin contracts match Cadence Code {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
