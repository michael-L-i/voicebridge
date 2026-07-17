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


def main() -> int:
    with (ROOT / "pyproject.toml").open("rb") as file:
        project = tomllib.load(file)["project"]

    claude = load_json(".claude-plugin/plugin.json")
    codex = load_json(".codex-plugin/plugin.json")
    mcp = load_json(".mcp.json")
    version = project["version"]

    failures: list[str] = []
    if claude.get("version") != version or codex.get("version") != version:
        failures.append("plugin manifest versions must match pyproject.toml")
    if claude.get("mcpServers", {}).get("voicebridge", {}).get("command") != (
        "${CLAUDE_PLUGIN_ROOT}/bin/voicebridge-mcp-bootstrap"
    ):
        failures.append("Claude Code must use the repository bootstrap")
    if codex.get("mcpServers") != "./.mcp.json":
        failures.append("Codex manifest must reference .mcp.json")
    if mcp.get("mcpServers", {}).get("voicebridge", {}).get("command") != "bash":
        failures.append("Codex MCP server must launch through bash")

    required_paths = [
        "bin/voicebridge-mcp-bootstrap",
        "commands/voice-code.md",
        "config/default_config.toml",
        "skills/voice-code/SKILL.md",
        "skills/voice-code/agents/openai.yaml",
    ]
    for relative_path in required_paths:
        if not (ROOT / relative_path).is_file():
            failures.append(f"required plugin file is missing: {relative_path}")

    bootstrap = ROOT / "bin/voicebridge-mcp-bootstrap"
    syntax = subprocess.run(
        ["bash", "-n", str(bootstrap)], capture_output=True, text=True, check=False
    )
    if syntax.returncode:
        failures.append(f"bootstrap has invalid bash syntax: {syntax.stderr.strip()}")

    if failures:
        for failure in failures:
            print(f"[fail] {failure}", file=sys.stderr)
        return 1

    print(f"[ok] plugin contracts match VoiceBridge {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
