import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class BootstrapTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, dict[str, str]]:
        plugin = root / "plugin"
        (plugin / "bin").mkdir(parents=True)
        shutil.copy2(
            ROOT / "bin/voicebridge-mcp-bootstrap",
            plugin / "bin/voicebridge-mcp-bootstrap",
        )
        (plugin / "pyproject.toml").write_text("[project]\nname = 'fixture'\n")
        (plugin / "requirements.lock").write_text("fixture==1\n")

        fake_python = root / "fake-python"
        fake_pip = root / "fake-pip"
        fake_server = root / "fake-server"
        fake_python.write_text(
            """#!/bin/bash
if [ "$1" = "-c" ]; then
  case "$2" in
    *os.path.realpath*) printf '%s\\n' "$0" ;;
  esac
  exit 0
fi
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  mkdir -p "$3/bin"
  cp "$FAKE_PIP" "$3/bin/pip"
  cp "$FAKE_SERVER" "$3/bin/voicebridge-mcp"
  exit 0
fi
exit 1
"""
        )
        fake_pip.write_text(
            """#!/bin/bash
printf '%s\\n' "$*" >> "$PIP_CALLS"
case " $* " in
  *" --upgrade "*" pip "*)
    exit 43
    ;;
  *" --require-hashes "*)
    if [ "${FAIL_LOCK_INSTALL:-0}" = "1" ]; then
      exit 42
    fi
    ;;
esac
exit 0
"""
        )
        fake_server.write_text("#!/bin/bash\nexit 0\n")
        for executable in (fake_python, fake_pip, fake_server):
            executable.chmod(0o755)

        data = root / "data"
        environment = {
            **os.environ,
            "VOICEBRIDGE_DATA_DIR": str(data),
            "VOICEBRIDGE_PYTHON": str(fake_python),
            "FAKE_PIP": str(fake_pip),
            "FAKE_SERVER": str(fake_server),
            "PIP_CALLS": str(root / "pip-calls"),
        }
        return plugin / "bin/voicebridge-mcp-bootstrap", data, environment

    def test_empty_install_activates_completed_versioned_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, data, environment = self._fixture(Path(directory))

            result = subprocess.run(
                [str(bootstrap)], env=environment, capture_output=True, text=True
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((data / "venv").is_symlink())
            self.assertTrue((data / "venv/bin/voicebridge-mcp").is_file())
            self.assertTrue((data / "venv/.voicebridge-install-marker").is_file())
            self.assertEqual(list(data.glob(".venv-link.*")), [])

    def test_uses_bundled_pip_only_for_locked_runtime_and_local_project(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, _, environment = self._fixture(Path(directory))

            result = subprocess.run(
                [str(bootstrap)], env=environment, capture_output=True, text=True
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = Path(environment["PIP_CALLS"]).read_text().splitlines()
            self.assertEqual(len(calls), 2)
            self.assertIn("--require-hashes", calls[0])
            self.assertIn("--ignore-requires-python", calls[0])
            self.assertIn("requirements.lock", calls[0])
            self.assertIn("--no-deps", calls[1])
            self.assertIn(" -e ", f" {calls[1]} ")
            self.assertNotIn("--upgrade", " ".join(calls))

    def test_failed_update_preserves_legacy_working_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, data, environment = self._fixture(Path(directory))
            legacy = data / "venv"
            (legacy / "bin").mkdir(parents=True)
            (legacy / "bin/voicebridge-mcp").write_text("working\n")
            (legacy / "bin/voicebridge-mcp").chmod(0o755)
            (legacy / ".voicebridge-install-marker").write_text("stale\n")
            environment["FAIL_LOCK_INSTALL"] = "1"

            result = subprocess.run(
                [str(bootstrap)], env=environment, capture_output=True, text=True
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(legacy.is_symlink())
            self.assertEqual(
                (legacy / "bin/voicebridge-mcp").read_text(), "working\n"
            )
            self.assertEqual(list(data.glob(".venv-build.*")), [])


if __name__ == "__main__":
    unittest.main()
