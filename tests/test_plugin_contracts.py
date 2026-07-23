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

        self.assertEqual(project_version, "0.6.0")
        self.assertEqual(claude["version"], project_version)
        self.assertEqual(codex["version"], project_version)
        self.assertEqual(
            claude["mcpServers"]["cadence-code"]["env"]["CADENCE_CODE_HOST"],
            "claude-code",
        )
        self.assertEqual(codex["skills"], "./skills/")

    def test_codex_manifest_bundles_mcp_without_project_config(self):
        codex = _json(".codex-plugin/plugin.json")
        server = codex["mcpServers"]["cadence-code"]

        self.assertFalse((ROOT / ".mcp.json").exists())
        self.assertEqual(server["type"], "stdio")
        self.assertEqual(server["command"], "bash")
        self.assertEqual(server["args"], ["./bin/cadence-code-mcp-bootstrap"])
        self.assertEqual(server["cwd"], ".")
        self.assertEqual(server["env"]["CADENCE_CODE_HOST"], "codex")
        self.assertEqual(server["startup_timeout_sec"], 900)
        self.assertEqual(server["tool_timeout_sec"], 1800)
        self.assertEqual(server["default_tools_approval_mode"], "approve")

    def test_codex_marketplace_points_at_repo_root_with_required_policy(self):
        marketplace = _json(".agents/plugins/marketplace.json")
        entry = marketplace["plugins"][0]

        self.assertEqual(marketplace["name"], "cadence-code-marketplace")
        self.assertEqual(entry["name"], "cadence-code")
        self.assertEqual(entry["source"], {"source": "local", "path": "./"})
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertEqual(entry["category"], "Productivity")

    def test_start_talking_is_explicit_and_references_exact_tool_surface(self):
        skill = (ROOT / "skills/start-talking/SKILL.md").read_text(
            encoding="utf-8"
        )
        command = (ROOT / "commands/start-talking.md").read_text(encoding="utf-8")
        metadata = (ROOT / "skills/start-talking/agents/openai.yaml").read_text(
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
        self.assertIn("explicitly invokes $start-talking", skill)
        self.assertIn("If `first_run` is true", skill)
        self.assertIn("before any", skill)
        self.assertIn("model download", skill)
        for tool in expected_tools:
            self.assertIn(f"mcp__cadence-code__{tool}", skill)
            self.assertIn(f"mcp__cadence-code__{tool}", command)
        self.assertIn("cadence-code-mcp-bootstrap --setup", command)
        self.assertIn("/reload-plugins", command)
        self.assertIn("If `first_run` is true", command)
        self.assertIn('error_code: "session_not_started"', skill)
        self.assertIn('error_code: "session_not_started"', command)

    def test_first_run_onboarding_covers_text_voice_and_host_controls(self):
        codex = (ROOT / "skills/start-talking/SKILL.md").read_text(
            encoding="utf-8"
        )
        claude = (ROOT / "commands/start-talking.md").read_text(encoding="utf-8")

        for workflow in (codex, claude):
            normalized = " ".join(workflow.split())
            self.assertIn("reproduce this fixed onboarding script verbatim", normalized)
            self.assertIn("WELCOME TO CADENCE CODE", normalized)
            self.assertIn("I want to talk with you", normalized)
            self.assertIn("YOU TALK -> I WORK -> WE KEEP GOING", normalized)
            self.assertIn("We take turns", normalized)
            self.assertIn("listen for your next turn", normalized)
            self.assertIn("QUICK CONTROLS", normalized)
            self.assertIn("READY TO GO", normalized)
            self.assertIn("Pocket TTS 100M", normalized)
            self.assertIn("Parakeet 110M", normalized)
            self.assertIn("PRIVATE BY DEFAULT", normalized)
            self.assertIn("stay on this Mac", normalized)
            self.assertIn("skip the fixed script", normalized)
            self.assertIn("local defaults load automatically", normalized)
            self.assertIn("defaults.tts", normalized)
            self.assertIn("defaults.stt", normalized)
            self.assertIn("Do not present a model selector", normalized)
            self.assertIn("or wait for confirmation", normalized)
            self.assertIn("Welcome to Cadence Code. I want to talk with you", normalized)
            self.assertIn("We'll alternate turns", normalized)
            self.assertIn("press Escape", normalized)
            self.assertIn("choose Jump In", normalized)

        for command in ("$start-talking", "$jump-in", "$wrap-up", "$voice-settings"):
            self.assertIn(command, codex)
        for command in (
            "/cadence-code:start-talking",
            "/cadence-code:jump-in",
            "/cadence-code:wrap-up",
            "/cadence-code:voice-settings",
        ):
            self.assertIn(command, claude)

    def test_settings_are_available_from_both_host_uis(self):
        skill = (ROOT / "skills/voice-settings/SKILL.md").read_text(
            encoding="utf-8"
        )
        command = (ROOT / "commands/voice-settings.md").read_text(
            encoding="utf-8"
        )
        metadata = (ROOT / "skills/voice-settings/agents/openai.yaml").read_text(
            encoding="utf-8"
        )

        self.assertIn("explicitly invokes $voice-settings", skill)
        self.assertIn("allow_implicit_invocation: false", metadata)
        for tool in {"voice_status", "voice_models", "voice_configure", "voice_stop"}:
            self.assertIn(f"mcp__cadence-code__{tool}", skill)
            self.assertIn(f"mcp__cadence-code__{tool}", command)
        self.assertIn("Do not call `mcp__cadence-code__voice_start`", skill)
        self.assertIn("Do not call `mcp__cadence-code__voice_start`", command)

        codex = _json(".codex-plugin/plugin.json")
        self.assertIn(
            "Choose Cadence Code speech and transcription models.",
            codex["interface"]["defaultPrompt"],
        )

    def test_server_exposes_only_the_eight_voice_tools(self):
        source = (ROOT / "cadence_code/mcp/server.py").read_text(encoding="utf-8")
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
                "voice_interrupt",
                "voice_stop",
                "voice_status",
            },
        )
        self.assertIn("Only call audio tools after the user explicitly", source)
        self.assertIn("never starts a session or loads models implicitly", source)

    def test_jump_in_is_available_from_both_host_uis(self):
        skill = (ROOT / "skills/jump-in/SKILL.md").read_text(
            encoding="utf-8"
        )
        command = (ROOT / "commands/jump-in.md").read_text(encoding="utf-8")
        metadata = (ROOT / "skills/jump-in/agents/openai.yaml").read_text(
            encoding="utf-8"
        )

        self.assertIn("explicitly invokes $jump-in", skill)
        self.assertIn("allow_implicit_invocation: false", metadata)
        self.assertIn("mcp__cadence-code__voice_interrupt", skill)
        self.assertIn("mcp__cadence-code__voice_interrupt", command)
        self.assertIn("added guidance", skill)
        self.assertIn("added guidance", command)
        self.assertIn("Escape", command)

    def test_wrap_up_is_explicit_and_finishes_final_speech(self):
        skill = (ROOT / "skills/wrap-up/SKILL.md").read_text(encoding="utf-8")
        command = (ROOT / "commands/wrap-up.md").read_text(encoding="utf-8")
        metadata = (ROOT / "skills/wrap-up/agents/openai.yaml").read_text(
            encoding="utf-8"
        )

        self.assertIn("explicitly invokes $wrap-up", skill)
        self.assertIn("allow_implicit_invocation: false", metadata)
        for workflow in (skill, command):
            self.assertIn("mcp__cadence-code__voice_status", workflow)
            self.assertIn("mcp__cadence-code__voice_speak", workflow)
            self.assertIn("mcp__cadence-code__voice_stop", workflow)
            self.assertIn("wait_for_speech: true", workflow)
            self.assertIn("exactly once", workflow)
            self.assertIn("Do not listen again", workflow)

    def test_bootstrap_is_valid_bash_and_checks_platform_before_rebuild(self):
        bootstrap = ROOT / "bin/cadence-code-mcp-bootstrap"
        result = subprocess.run(
            ["bash", "-n", str(bootstrap)],
            check=False,
            capture_output=True,
            text=True,
        )
        source = bootstrap.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CADENCE_CODE_DEV_DATA_DIR", source)
        self.assertIn('REQUIREMENTS="${PLUGIN_ROOT}/requirements.lock"', source)
        self.assertIn("--require-hashes", source)
        self.assertIn("--no-deps", source)
        self.assertNotIn('pip" install --quiet -e', source)
        self.assertLess(source.index("uname -s"), source.index("BUILD_DIR=$(mktemp"))
        self.assertLess(
            source.index("(3, 11) <= sys.version_info < (3, 15)"),
            source.index("BUILD_DIR=$(mktemp"),
        )
        logical_source = source.replace("\\\n", "")
        self.assertNotIn("--upgrade pip", logical_source)
        for line in logical_source.splitlines():
            if line.strip().startswith("echo "):
                self.assertIn(">", line, f"echo lacks a redirection: {line}")


if __name__ == "__main__":
    unittest.main()
