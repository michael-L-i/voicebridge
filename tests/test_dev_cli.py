import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEV = ROOT / "dev"


class DevCliTests(unittest.TestCase):
    def test_dev_script_is_executable_bash(self):
        self.assertTrue(DEV.stat().st_mode & 0o111)
        subprocess.run(["bash", "-n", DEV], check=True)

    def test_check_help_describes_offline_scope(self):
        result = subprocess.run(
            [DEV, "check", "--help"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("unit tests", result.stdout)
        self.assertIn("does not install", result.stdout)
        self.assertIn("download speech models", result.stdout)

    def test_inspector_launches_checkout_server_with_isolated_data(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_npx = temp / "npx"
            fake_npx.write_text(
                "#!/bin/bash\nprintf '%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            fake_npx.chmod(0o755)
            data_root = temp / "data"
            env = {
                **os.environ,
                "CADENCE_CODE_DEV_NPX_BIN": str(fake_npx),
                "CADENCE_CODE_DEV_DATA_ROOT": str(data_root),
            }

            result = subprocess.run(
                [DEV, "inspector"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

        arguments = result.stdout.splitlines()
        self.assertIn("@modelcontextprotocol/inspector", arguments)
        self.assertIn(
            f"CADENCE_CODE_DATA_DIR={data_root.resolve()}/inspector", arguments
        )
        self.assertIn("CADENCE_CODE_HOST=inspector", arguments)
        self.assertIn(str(ROOT / "bin/cadence-code-mcp-bootstrap"), arguments)

    def test_claude_loads_checkout_directly_with_development_data(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_claude = temp / "claude"
            fake_claude.write_text(
                "#!/bin/bash\n"
                "printf 'cwd=%s\\n' \"$PWD\"\n"
                "printf 'data=%s\\n' \"$CADENCE_CODE_DEV_DATA_DIR\"\n"
                "printf 'arg=%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            fake_claude.chmod(0o755)
            data_root = temp / "data"
            env = {
                **os.environ,
                "CADENCE_CODE_DEV_CLAUDE_BIN": str(fake_claude),
                "CADENCE_CODE_DEV_DATA_ROOT": str(data_root),
            }

            result = subprocess.run(
                [DEV, "claude", "--model", "test-model"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"cwd={ROOT}", result.stdout)
        self.assertIn(f"data={data_root.resolve()}/claude", result.stdout)
        self.assertIn("arg=--plugin-dir", result.stdout)
        self.assertIn(f"arg={ROOT}", result.stdout)
        self.assertIn("arg=--model", result.stdout)
        self.assertIn("arg=test-model", result.stdout)

    def test_claude_fresh_resets_onboarding_but_keeps_venv(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_claude = temp / "claude"
            fake_claude.write_text(
                "#!/bin/bash\nprintf 'arg=%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            fake_claude.chmod(0o755)
            data_root = temp / "data"
            claude_data = data_root / "claude"
            venv = claude_data / "venv"
            venv.mkdir(parents=True)
            (claude_data / "config.toml").write_text("configured\n")
            (claude_data / "onboarding-v1.complete").write_text("done\n")
            keep = venv / "keep"
            keep.write_text("warm\n")
            env = {
                **os.environ,
                "CADENCE_CODE_DEV_CLAUDE_BIN": str(fake_claude),
                "CADENCE_CODE_DEV_DATA_ROOT": str(data_root),
            }

            result = subprocess.run(
                [DEV, "claude", "--fresh"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((claude_data / "config.toml").exists())
            self.assertFalse((claude_data / "onboarding-v1.complete").exists())
            self.assertTrue(keep.exists())
        self.assertNotIn("arg=--fresh", result.stdout)

    def test_codex_injects_checkout_mcp_without_marketplace(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_codex = temp / "codex"
            fake_codex.write_text(
                "#!/bin/bash\n"
                "printf 'cwd=%s\\n' \"$PWD\"\n"
                "printf 'arg=%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            data_root = temp / "data"
            env = {
                **os.environ,
                "CADENCE_CODE_DEV_CODEX_BIN": str(fake_codex),
                "CADENCE_CODE_DEV_DATA_ROOT": str(data_root),
            }

            result = subprocess.run(
                [DEV, "codex", "--model", "test-model"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

        arguments = result.stdout.splitlines()
        self.assertIn(f"cwd={ROOT}", arguments)
        self.assertIn("arg=-C", arguments)
        self.assertIn(f"arg={ROOT}", arguments)
        self.assertIn(
            "arg=mcp_servers.cadence-code.command="
            f"{ROOT}/bin/cadence-code-mcp-bootstrap",
            arguments,
        )
        self.assertIn(
            "arg=mcp_servers.cadence-code.env.CADENCE_CODE_DATA_DIR="
            f"{data_root.resolve()}/codex",
            arguments,
        )
        self.assertIn(
            "arg=mcp_servers.cadence-code.env.CADENCE_CODE_HOST=codex",
            arguments,
        )
        self.assertIn("arg=mcp_servers.cadence-code.required=true", arguments)
        self.assertNotIn("plugin", " ".join(arguments))
        self.assertNotIn("marketplace", " ".join(arguments))

    def test_codex_development_skills_point_at_all_canonical_sources(self):
        canonical_root = ROOT / "skills"
        development_root = ROOT / ".agents/skills"
        canonical_skills = {
            path.name for path in canonical_root.iterdir() if path.is_dir()
        }
        development_skills = {path.name for path in development_root.iterdir()}

        self.assertEqual(development_skills, canonical_skills)
        for name in canonical_skills:
            development_skill = development_root / name
            self.assertTrue(development_skill.is_symlink())
            self.assertEqual(
                development_skill.readlink(), Path("../../skills") / name
            )
            self.assertEqual(development_skill.resolve(), canonical_root / name)

    def test_codex_fresh_resets_onboarding_but_keeps_venv(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_codex = temp / "codex"
            fake_codex.write_text(
                "#!/bin/bash\nprintf 'arg=%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            data_root = temp / "data"
            codex_data = data_root / "codex"
            venv = codex_data / "venv"
            venv.mkdir(parents=True)
            (codex_data / "config.toml").write_text("configured\n")
            (codex_data / "onboarding-v1.complete").write_text("done\n")
            keep = venv / "keep"
            keep.write_text("warm\n")
            env = {
                **os.environ,
                "CADENCE_CODE_DEV_CODEX_BIN": str(fake_codex),
                "CADENCE_CODE_DEV_DATA_ROOT": str(data_root),
            }

            result = subprocess.run(
                [DEV, "codex", "--fresh"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((codex_data / "config.toml").exists())
            self.assertFalse((codex_data / "onboarding-v1.complete").exists())
            self.assertTrue(keep.exists())
        self.assertNotIn("arg=--fresh", result.stdout)

    def test_cursor_loads_checkout_with_development_data(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_cursor = temp / "agent"
            fake_cursor.write_text(
                "#!/bin/bash\n"
                "printf 'cwd=%s\\n' \"$PWD\"\n"
                "printf 'data=%s\\n' \"$CADENCE_CODE_DATA_DIR\"\n"
                "printf 'host=%s\\n' \"$CADENCE_CODE_HOST\"\n"
                "printf 'arg=%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            fake_cursor.chmod(0o755)
            data_root = temp / "data"
            env = {
                **os.environ,
                "CADENCE_CODE_DEV_CURSOR_BIN": str(fake_cursor),
                "CADENCE_CODE_DEV_DATA_ROOT": str(data_root),
            }

            result = subprocess.run(
                [DEV, "cursor", "--model", "test-model"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

        arguments = result.stdout.splitlines()
        self.assertIn(f"cwd={ROOT}", arguments)
        self.assertIn(f"data={data_root.resolve()}/cursor", arguments)
        self.assertIn("host=cursor", arguments)
        self.assertIn("arg=--workspace", arguments)
        self.assertIn(f"arg={ROOT}", arguments)
        self.assertIn("arg=--model", arguments)
        self.assertIn("arg=test-model", arguments)

    def test_cursor_plugin_mode_exercises_the_installed_manifest(self):
        """--plugin is the only local check of the shipped Cursor manifest.

        ${CURSOR_PLUGIN_ROOT} is undocumented, so the workspace .cursor/mcp.json
        path cannot prove the installed mcp.json resolves. This mode must load
        the checkout through --plugin-dir and must not pre-set the host, or a
        broken manifest would be masked by the launcher's own environment.
        """
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_cursor = temp / "agent"
            fake_cursor.write_text(
                "#!/bin/bash\n"
                "printf 'host=%s\\n' \"${CADENCE_CODE_HOST-unset}\"\n"
                "printf 'arg=%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            fake_cursor.chmod(0o755)
            data_root = temp / "data"
            env = {
                **os.environ,
                "CADENCE_CODE_DEV_CURSOR_BIN": str(fake_cursor),
                "CADENCE_CODE_DEV_DATA_ROOT": str(data_root),
            }
            env.pop("CADENCE_CODE_HOST", None)

            result = subprocess.run(
                [DEV, "cursor", "--plugin"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

        arguments = result.stdout.splitlines()
        self.assertIn("arg=--plugin-dir", arguments)
        self.assertIn(f"arg={ROOT}", arguments)
        self.assertIn("host=unset", arguments)
        self.assertNotIn("arg=--plugin", arguments)

    def test_cursor_workspace_mcp_uses_checkout_bootstrap(self):
        server = json.loads(
            (ROOT / ".cursor/mcp.json").read_text(encoding="utf-8")
        )["mcpServers"]["cadence-code"]

        self.assertEqual(server["command"], "bash")
        self.assertEqual(
            server["args"],
            ["${workspaceFolder}/bin/cadence-code-mcp-bootstrap"],
        )
        self.assertEqual(server["cwd"], "${workspaceFolder}")
        self.assertEqual(server["env"]["CADENCE_CODE_HOST"], "cursor")

    def test_cursor_fresh_resets_onboarding_but_keeps_venv(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_cursor = temp / "agent"
            fake_cursor.write_text(
                "#!/bin/bash\nprintf 'arg=%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            fake_cursor.chmod(0o755)
            data_root = temp / "data"
            cursor_data = data_root / "cursor"
            venv = cursor_data / "venv"
            venv.mkdir(parents=True)
            (cursor_data / "config.toml").write_text("configured\n")
            (cursor_data / "onboarding-v1.complete").write_text("done\n")
            keep = venv / "keep"
            keep.write_text("warm\n")
            env = {
                **os.environ,
                "CADENCE_CODE_DEV_CURSOR_BIN": str(fake_cursor),
                "CADENCE_CODE_DEV_DATA_ROOT": str(data_root),
            }

            result = subprocess.run(
                [DEV, "cursor", "--fresh"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((cursor_data / "config.toml").exists())
            self.assertFalse((cursor_data / "onboarding-v1.complete").exists())
            self.assertTrue(keep.exists())
        self.assertNotIn("arg=--fresh", result.stdout)

    def test_agy_loads_checkout_with_development_data(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_agy = temp / "agy"
            fake_agy.write_text(
                "#!/bin/bash\n"
                "printf 'cwd=%s\\n' \"$PWD\"\n"
                "printf 'data=%s\\n' \"$CADENCE_CODE_DATA_DIR\"\n"
                "printf 'host=%s\\n' \"$CADENCE_CODE_HOST\"\n"
                "printf 'arg=%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            fake_agy.chmod(0o755)
            data_root = temp / "data"
            env = {
                **os.environ,
                "CADENCE_CODE_DEV_AGY_BIN": str(fake_agy),
                "CADENCE_CODE_DEV_DATA_ROOT": str(data_root),
            }

            result = subprocess.run(
                [DEV, "agy", "--model", "test-model"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

        self.assertIn(f"cwd={ROOT}", result.stdout)
        self.assertIn(f"data={data_root.resolve()}/antigravity", result.stdout)
        self.assertIn("host=antigravity", result.stdout)
        self.assertIn("arg=--model", result.stdout)
        self.assertIn("arg=test-model", result.stdout)

    def test_agy_workspace_mcp_uses_checkout_bootstrap(self):
        server = json.loads(
            (ROOT / ".agents/mcp_config.json").read_text(encoding="utf-8")
        )["mcpServers"]["cadence-code"]

        self.assertEqual(server["command"], "bash")
        self.assertEqual(server["args"][0], "-c")
        # AGY 1.1.6 accepts but does not pass the documented stdio env object,
        # so the launcher exports the host identity itself.
        self.assertIn("export CADENCE_CODE_HOST=antigravity", server["args"][1])
        self.assertIn("bin/cadence-code-mcp-bootstrap", server["args"][1])
        self.assertEqual(server["env"]["CADENCE_CODE_HOST"], "antigravity")
        self.assertEqual(server["cwd"], ".")
        self.assertEqual(server["timeoutSeconds"], 1800)

    def test_agy_fresh_resets_onboarding_but_keeps_venv(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fake_agy = temp / "agy"
            fake_agy.write_text(
                "#!/bin/bash\nprintf 'arg=%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            fake_agy.chmod(0o755)
            data_root = temp / "data"
            agy_data = data_root / "antigravity"
            venv = agy_data / "venv"
            venv.mkdir(parents=True)
            (agy_data / "config.toml").write_text("configured\n")
            (agy_data / "onboarding-v1.complete").write_text("done\n")
            keep = venv / "keep"
            keep.write_text("warm\n")
            env = {
                **os.environ,
                "CADENCE_CODE_DEV_AGY_BIN": str(fake_agy),
                "CADENCE_CODE_DEV_DATA_ROOT": str(data_root),
            }

            result = subprocess.run(
                [DEV, "agy", "--fresh"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((agy_data / "config.toml").exists())
            self.assertFalse((agy_data / "onboarding-v1.complete").exists())
            self.assertTrue(keep.exists())
        self.assertNotIn("arg=--fresh", result.stdout)

    def test_reset_removes_only_guarded_development_root(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            data_root = temp / ".cadence-code-dev"
            (data_root / "codex/venv").mkdir(parents=True)
            (data_root / "codex/config.toml").write_text("configured\n")
            fake_pgrep = temp / "pgrep"
            fake_pgrep.write_text("#!/bin/bash\nexit 1\n", encoding="utf-8")
            fake_pgrep.chmod(0o755)
            fake_trash = temp / "trash"
            fake_trash.write_text(
                "#!/bin/bash\nrm -rf -- \"$1\"\n",
                encoding="utf-8",
            )
            fake_trash.chmod(0o755)
            env = {
                **os.environ,
                "CADENCE_CODE_DEV_DATA_ROOT": str(data_root),
                "CADENCE_CODE_DEV_PGREP_BIN": str(fake_pgrep),
                "CADENCE_CODE_DEV_TRASH_BIN": str(fake_trash),
            }

            result = subprocess.run(
                [DEV, "reset"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(data_root.exists())
        self.assertIn("to Trash", result.stdout)

    def test_reset_refuses_while_cadence_code_process_is_running(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            data_root = temp / ".cadence-code-dev"
            data_root.mkdir()
            fake_pgrep = temp / "pgrep"
            fake_pgrep.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
            fake_pgrep.chmod(0o755)
            env = {
                **os.environ,
                "CADENCE_CODE_DEV_DATA_ROOT": str(data_root),
                "CADENCE_CODE_DEV_PGREP_BIN": str(fake_pgrep),
            }

            result = subprocess.run(
                [DEV, "reset"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(data_root.exists())
        self.assertIn("stop every Cadence Code host session", result.stderr)


if __name__ == "__main__":
    unittest.main()
