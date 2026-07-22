import os
import shutil
import subprocess
import tempfile
import time
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
case " $* " in
  *" --require-hashes "*)
    printf 'install\n' >> "$INSTALL_LOG"
    if [ -n "${LOCK_INSTALL_DELAY:-}" ]; then
      sleep "$LOCK_INSTALL_DELAY"
    fi
    if [ "${FAIL_LOCK_INSTALL:-0}" = "1" ]; then
      exit 42
    fi
    ;;
esac
exit 0
"""
        )
        fake_server.write_text(
            "#!/bin/bash\nprintf 'server\\n' >> \"$SERVER_EXEC_LOG\"\nexit 0\n"
        )
        for executable in (fake_python, fake_pip, fake_server):
            executable.chmod(0o755)

        data = root / "data"
        environment = {
            **os.environ,
            "VOICEBRIDGE_DATA_DIR": str(data),
            "VOICEBRIDGE_PYTHON": str(fake_python),
            "FAKE_PIP": str(fake_pip),
            "FAKE_SERVER": str(fake_server),
            "INSTALL_LOG": str(root / "install.log"),
            "SERVER_EXEC_LOG": str(root / "server.log"),
        }
        return plugin / "bin/voicebridge-mcp-bootstrap", data, environment

    def _wait_for_install(self, environment: dict[str, str]) -> None:
        install_log = Path(environment["INSTALL_LOG"])
        deadline = time.monotonic() + 5
        while not install_log.exists():
            if time.monotonic() >= deadline:
                self.fail("bootstrap did not start its locked install")
            time.sleep(0.01)

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
            self.assertEqual(result.stdout, "")

    def test_concurrent_callers_share_one_install_and_both_run_server(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, data, environment = self._fixture(Path(directory))
            environment["LOCK_INSTALL_DELAY"] = "0.5"

            first = subprocess.Popen(
                [str(bootstrap)],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._wait_for_install(environment)
            second = subprocess.Popen(
                [str(bootstrap)],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            first_stdout, first_stderr = first.communicate(timeout=10)
            second_stdout, second_stderr = second.communicate(timeout=10)

            self.assertEqual(first.returncode, 0, first_stderr)
            self.assertEqual(second.returncode, 0, second_stderr)
            self.assertEqual(first_stdout, "")
            self.assertEqual(second_stdout, "")
            self.assertEqual(
                Path(environment["INSTALL_LOG"]).read_text().splitlines(),
                ["install"],
            )
            self.assertEqual(
                Path(environment["SERVER_EXEC_LOG"]).read_text().splitlines(),
                ["server", "server"],
            )
            self.assertTrue((data / "venv/bin/voicebridge-mcp").is_file())
            self.assertFalse((data / ".venv-install.lock").exists())

    def test_failed_installer_releases_waiter_to_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, data, environment = self._fixture(Path(directory))
            failing_environment = {**environment, "FAIL_LOCK_INSTALL": "1"}
            failing_environment["LOCK_INSTALL_DELAY"] = "0.5"

            first = subprocess.Popen(
                [str(bootstrap)],
                env=failing_environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._wait_for_install(environment)
            second = subprocess.Popen(
                [str(bootstrap)],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            first_stdout, first_stderr = first.communicate(timeout=10)
            second_stdout, second_stderr = second.communicate(timeout=10)

            self.assertNotEqual(first.returncode, 0, first_stderr)
            self.assertEqual(second.returncode, 0, second_stderr)
            self.assertEqual(first_stdout, "")
            self.assertEqual(second_stdout, "")
            self.assertEqual(
                Path(environment["INSTALL_LOG"]).read_text().splitlines(),
                ["install", "install"],
            )
            self.assertEqual(
                Path(environment["SERVER_EXEC_LOG"]).read_text().splitlines(),
                ["server"],
            )
            self.assertFalse((data / ".venv-install.lock").exists())

    def test_stale_installer_lock_is_recovered_without_pruning_builds(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, data, environment = self._fixture(Path(directory))
            lock = data / ".venv-install.lock"
            lock.mkdir(parents=True)
            (lock / "owner").write_text("999999|stale process|dead-token\n")
            orphan_build = data / ".venv-build.orphan"
            orphan_build.mkdir()

            result = subprocess.run(
                [str(bootstrap)], env=environment, capture_output=True, text=True
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertIn("recovered a stale installer lock", result.stderr)
            self.assertTrue(orphan_build.is_dir())
            self.assertTrue((data / "venv/bin/voicebridge-mcp").is_file())
            self.assertFalse(lock.exists())

    def test_incomplete_installer_lock_from_early_crash_is_recovered(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, data, environment = self._fixture(Path(directory))
            lock = data / ".venv-install.lock"
            lock.mkdir(parents=True)

            result = subprocess.run(
                [str(bootstrap)],
                env=environment,
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertIn("recovered an incomplete installer lock", result.stderr)
            self.assertTrue((data / "venv/bin/voicebridge-mcp").is_file())
            self.assertFalse(lock.exists())

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
            self.assertFalse((data / ".venv-install.lock").exists())


if __name__ == "__main__":
    unittest.main()
