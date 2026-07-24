#!/usr/bin/env python3
"""Validate repository-owned plugin contracts without loading speech models."""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


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


def validate_antigravity_development_mcp(failures: list[str]) -> None:
    server = load_json(".agents/mcp_config.json").get("mcpServers", {}).get(
        "cadence-code", {}
    )
    if server.get("command") != "env":
        failures.append("Antigravity development MCP must launch through env")
    if server.get("args") != [
        "CADENCE_CODE_HOST=antigravity",
        "bash",
        "./bin/cadence-code-mcp-bootstrap",
    ]:
        failures.append("Antigravity development MCP must use the checkout bootstrap")
    if server.get("cwd") != ".":
        failures.append("Antigravity development MCP must run from the checkout root")


def main() -> int:
    with (ROOT / "pyproject.toml").open("rb") as file:
        project = tomllib.load(file)["project"]

    claude = load_json(".claude-plugin/plugin.json")
    codex = load_json(".codex-plugin/plugin.json")
    antigravity = load_json("plugin.json")
    antigravity_mcp = load_json("mcp_config.json")
    version = project["version"]

    failures: list[str] = []
    if claude.get("version") != version or codex.get("version") != version:
        failures.append("plugin manifest versions must match pyproject.toml")
    if claude.get("mcpServers", {}).get("cadence-code", {}).get("command") != (
        "${CLAUDE_PLUGIN_ROOT}/bin/cadence-code-mcp-bootstrap"
    ):
        failures.append("Claude Code must use the repository bootstrap")
    codex_server = codex.get("mcpServers", {}).get("cadence-code", {})
    if codex_server.get("command") != "bash":
        failures.append("Codex MCP server must launch through bash")
    if codex_server.get("args") != ["./bin/cadence-code-mcp-bootstrap"]:
        failures.append("Codex MCP server must use the repository bootstrap")
    if (ROOT / ".mcp.json").exists():
        failures.append("Codex MCP configuration must be bundled in the manifest")
    if antigravity.get("$schema") != (
        "https://antigravity.google/schemas/v1/plugin.json"
    ):
        failures.append("Antigravity plugin must use the official schema")
    if antigravity.get("name") != "cadence-code":
        failures.append("Antigravity plugin name must be cadence-code")
    antigravity_server = antigravity_mcp.get("mcpServers", {}).get(
        "cadence-code", {}
    )
    if antigravity_server.get("command") != "env":
        failures.append("Antigravity MCP server must launch through env")
    if antigravity_server.get("args") != [
        "CADENCE_CODE_HOST=antigravity",
        "bash",
        "${extensionPath}/bin/cadence-code-mcp-bootstrap"
    ]:
        failures.append("Antigravity MCP server must use the installed bootstrap")
    if antigravity_server.get("cwd") != "${extensionPath}":
        failures.append("Antigravity MCP server must run from its plugin root")

    validate_development_skills(failures)
    validate_antigravity_development_mcp(failures)

    required_paths = [
        ".agents/mcp_config.json",
        "bin/cadence-code-mcp-bootstrap",
        "mcp_config.json",
        "plugin.json",
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
