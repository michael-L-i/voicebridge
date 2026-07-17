import ast
import json
import subprocess
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class PluginContractTests(unittest.TestCase):
    def test_versions_and_host_metadata_are_synchronized(self):
        with (ROOT / "pyproject.toml").open("rb") as file:
            project_version = tomllib.load(file)["project"]["version"]
        claude = _json(".claude-plugin/plugin.json")
        codex = _json(".codex-plugin/plugin.json")

        self.assertEqual(project_version, "0.4.0")
        self.assertEqual(claude["version"], project_version)
        self.assertEqual(codex["version"], project_version)
        self.assertEqual(
            claude["mcpServers"]["voicebridge"]["env"]["VOICEBRIDGE_HOST"],
            "claude-code",
        )
        self.assertEqual(codex["skills"], "./skills/")

    def test_codex_manifest_bundles_mcp_without_project_config(self):
        codex = _json(".codex-plugin/plugin.json")
        server = codex["mcpServers"]["voicebridge"]

        self.assertFalse((ROOT / ".mcp.json").exists())
        self.assertEqual(server["type"], "stdio")
        self.assertEqual(server["command"], "bash")
        self.assertEqual(server["args"], ["./bin/voicebridge-mcp-bootstrap"])
        self.assertEqual(server["cwd"], ".")
        self.assertEqual(server["env"]["VOICEBRIDGE_HOST"], "codex")
        self.assertEqual(server["startup_timeout_sec"], 900)
        self.assertEqual(server["tool_timeout_sec"], 1800)
        self.assertEqual(server["default_tools_approval_mode"], "approve")

    def test_codex_marketplace_points_at_repo_root_with_required_policy(self):
        marketplace = _json(".agents/plugins/marketplace.json")
        entry = marketplace["plugins"][0]

        self.assertEqual(marketplace["name"], "voicebridge-marketplace")
        self.assertEqual(entry["name"], "voicebridge")
        self.assertEqual(entry["source"], {"source": "local", "path": "./"})
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertEqual(entry["category"], "Productivity")

    def test_codex_skill_is_explicit_and_references_exact_tool_surface(self):
        skill = (ROOT / "skills/voice-code/SKILL.md").read_text(encoding="utf-8")
        command = (ROOT / "commands/voice-code.md").read_text(encoding="utf-8")
        metadata = (ROOT / "skills/voice-code/agents/openai.yaml").read_text(
            encoding="utf-8"
        )
        expected_tools = {
            "voice_models",
            "voice_configure",
            "voice_start",
            "voice_speak",
            "voice_listen",
            "voice_stop",
        }

        self.assertIn("allow_implicit_invocation: false", metadata)
        self.assertIn("explicitly invokes $voice-code", skill)
        self.assertIn("If `first_run` is true", skill)
        self.assertIn("before any", skill)
        self.assertIn("model download", skill)
        for tool in expected_tools:
            self.assertIn(f"mcp__voicebridge__{tool}", skill)
            self.assertIn(f"mcp__voicebridge__{tool}", command)
        self.assertIn("If `first_run` is true", command)

    def test_server_exposes_only_the_seven_voice_tools(self):
        source = (ROOT / "voicebridge/mcp/server.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        tools = {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "tool"
                for decorator in node.decorator_list
            )
        }
        self.assertEqual(
            tools,
            {
                "voice_models",
                "voice_configure",
                "voice_start",
                "voice_speak",
                "voice_listen",
                "voice_stop",
                "voice_status",
            },
        )
        self.assertIn("Only call audio tools after the user explicitly", source)

    def test_bootstrap_is_valid_bash_and_checks_platform_before_rebuild(self):
        bootstrap = ROOT / "bin/voicebridge-mcp-bootstrap"
        result = subprocess.run(
            ["bash", "-n", str(bootstrap)],
            check=False,
            capture_output=True,
            text=True,
        )
        source = bootstrap.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("VOICEBRIDGE_DEV_DATA_DIR", source)
        self.assertLess(source.index("uname -s"), source.index('rm -rf "${VENV_DIR}"'))
        self.assertLess(
            source.index("version_info < (3, 11)"), source.index('rm -rf "${VENV_DIR}"')
        )
        logical_source = source.replace("\\\n", "")
        for line in logical_source.splitlines():
            if line.strip().startswith("echo "):
                self.assertIn(">", line, f"echo lacks a redirection: {line}")


if __name__ == "__main__":
    unittest.main()
