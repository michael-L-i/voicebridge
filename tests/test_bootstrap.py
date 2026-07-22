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
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        fake_mv = fake_bin / "mv"
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
        fake_mv.write_text(
            f"""#!/bin/bash
previous=""
last=""
for argument in "$@"; do
  previous="$last"
  last="$argument"
done

case "$previous:$last" in
  */venv:*/.venv-previous.*)
    {shutil.which("mv")} "$@"
    if [ "${{INTERRUPT_AFTER_LEGACY_MOVE:-0}}" = "1" ]; then
      kill -TERM "$PPID"
    fi
    exit 0
    ;;
  */.venv-link.*:*/venv)
    if [ "${{FAIL_ACTIVATE:-0}}" = "1" ]; then
      exit 43
    fi
    {shutil.which("mv")} "$@"
    if [ "${{INTERRUPT_AFTER_ACTIVATE:-0}}" = "1" ]; then
      kill -TERM "$PPID"
    fi
    exit 0
    ;;
esac

exec {shutil.which("mv")} "$@"
"""
        )
        for executable in (fake_python, fake_pip, fake_server, fake_mv):
            executable.chmod(0o755)

        data = root / "data"
        environment = {
            **os.environ,
            "VOICEBRIDGE_DATA_DIR": str(data),
            "VOICEBRIDGE_PYTHON": str(fake_python),
            "FAKE_PIP": str(fake_pip),
            "FAKE_SERVER": str(fake_server),
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "PIP_CALLS": str(root / "pip-calls"),
        }
        return plugin / "bin/voicebridge-mcp-bootstrap", data, environment

    def _run(
        self, bootstrap: Path, environment: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(bootstrap)], env=environment, capture_output=True, text=True
        )

    def _seed_legacy_environment(self, data: Path) -> Path:
        legacy = data / "venv"
        (legacy / "bin").mkdir(parents=True)
        (legacy / "bin/voicebridge-mcp").write_text("working\n")
        (legacy / "bin/voicebridge-mcp").chmod(0o755)
        (legacy / ".voicebridge-install-marker").write_text("stale\n")
        return legacy

    def _assert_only_active_environment_remains(self, data: Path) -> None:
        active_builds = []
        if (data / "venv").is_symlink() and (data / "venv").exists():
            active_builds = [(data / "venv").resolve()]
        builds = [path.resolve() for path in data.glob(".venv-build.*")]
        self.assertEqual(builds, active_builds)
        self.assertEqual(list(data.glob(".venv-link.*")), [])
        self.assertEqual(list(data.glob(".venv-previous.*")), [])

    def test_empty_install_activates_completed_versioned_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, data, environment = self._fixture(Path(directory))

            result = self._run(bootstrap, environment)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((data / "venv").is_symlink())
            self.assertTrue((data / "venv/bin/voicebridge-mcp").is_file())
            self.assertTrue((data / "venv/.voicebridge-install-marker").is_file())
            self._assert_only_active_environment_remains(data)

    def test_update_replaces_symlink_and_removes_old_target(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, data, environment = self._fixture(Path(directory))
            first = self._run(bootstrap, environment)
            old_target = (data / "venv").resolve()
            (data / "venv/.voicebridge-install-marker").write_text("stale\n")

            result = self._run(bootstrap, environment)

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((data / "venv").is_symlink())
            self.assertNotEqual((data / "venv").resolve(), old_target)
            self.assertFalse(old_target.exists())
            self._assert_only_active_environment_remains(data)

    def test_failed_update_preserves_existing_symlink_target(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, data, environment = self._fixture(Path(directory))
            first = self._run(bootstrap, environment)
            old_link = os.readlink(data / "venv")
            old_target = (data / "venv").resolve()
            (data / "venv/.voicebridge-install-marker").write_text("stale\n")
            environment["FAIL_LOCK_INSTALL"] = "1"

            result = self._run(bootstrap, environment)

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue((data / "venv").is_symlink())
            self.assertEqual(os.readlink(data / "venv"), old_link)
            self.assertEqual((data / "venv").resolve(), old_target)
            self.assertTrue((old_target / "bin/voicebridge-mcp").is_file())
            self._assert_only_active_environment_remains(data)

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
            legacy = self._seed_legacy_environment(data)
            environment["FAIL_LOCK_INSTALL"] = "1"

            result = self._run(bootstrap, environment)

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(legacy.is_symlink())
            self.assertEqual(
                (legacy / "bin/voicebridge-mcp").read_text(), "working\n"
            )
            self._assert_only_active_environment_remains(data)

    def test_activation_failure_restores_legacy_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, data, environment = self._fixture(Path(directory))
            legacy = self._seed_legacy_environment(data)
            environment["FAIL_ACTIVATE"] = "1"

            result = self._run(bootstrap, environment)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("could not activate", result.stderr)
            self.assertFalse(legacy.is_symlink())
            self.assertEqual(
                (legacy / "bin/voicebridge-mcp").read_text(), "working\n"
            )
            self._assert_only_active_environment_remains(data)

    def test_interruption_after_legacy_move_restores_previous_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, data, environment = self._fixture(Path(directory))
            legacy = self._seed_legacy_environment(data)
            environment["INTERRUPT_AFTER_LEGACY_MOVE"] = "1"

            result = self._run(bootstrap, environment)

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(legacy.is_symlink())
            self.assertEqual(
                (legacy / "bin/voicebridge-mcp").read_text(), "working\n"
            )
            self._assert_only_active_environment_remains(data)

    def test_interruption_after_activation_keeps_completed_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            bootstrap, data, environment = self._fixture(Path(directory))
            legacy = self._seed_legacy_environment(data)
            environment["INTERRUPT_AFTER_ACTIVATE"] = "1"

            result = self._run(bootstrap, environment)

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(legacy.is_symlink())
            self.assertTrue((legacy / "bin/voicebridge-mcp").is_file())
            self.assertTrue((legacy / ".voicebridge-install-marker").is_file())
            self._assert_only_active_environment_remains(data)


if __name__ == "__main__":
    unittest.main()
