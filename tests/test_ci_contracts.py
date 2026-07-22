import re
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CiContractTests(unittest.TestCase):
    def test_package_supports_only_the_tested_python_range(self):
        with (ROOT / "pyproject.toml").open("rb") as file:
            project = tomllib.load(file)["project"]

        self.assertEqual(project["requires-python"], ">=3.11,<3.15")

    def test_ci_uses_locked_apple_silicon_validation(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

        self.assertIn("pull_request:", workflow)
        for macos in ("macos-14", "macos-15", "macos-26"):
            self.assertIn(f'macos: "{macos}"', workflow)
        for python in ("3.11", "3.12", "3.13", "3.14"):
            self.assertIn(f'python: "{python}"', workflow)
        self.assertIn("runs-on: ${{ matrix.macos }}", workflow)
        self.assertIn("name: CI complete", workflow)
        self.assertIn("needs: [test, package, dependency-review]", workflow)
        self.assertIn("uv lock --check", workflow)
        self.assertIn("uv export --locked --no-dev --no-emit-project", workflow)
        self.assertIn("diff -u requirements.lock", workflow)
        self.assertIn("Bootstrap an empty production environment", workflow)
        self.assertIn("./bin/voicebridge-mcp-bootstrap </dev/null", workflow)
        self.assertIn("Verify the bootstrapped Kokoro English frontend", workflow)
        self.assertIn("-p test_kokoro_frontend.py", workflow)
        self.assertIn("VOICEBRIDGE_DATA_DIR: ${{ runner.temp }}", workflow)
        self.assertIn("VOICEBRIDGE_PYTHON: python", workflow)
        self.assertNotIn("uv sync --locked", workflow)
        self.assertIn("import mlx.core as mx", workflow)
        self.assertIn("scripts/validate_plugin.py", workflow)
        self.assertIn("scripts/verify_distribution.py", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("actions/dependency-review-action@", workflow)

    def test_release_workflow_verifies_but_never_publishes(self):
        workflow = (ROOT / ".github/workflows/release-verify.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("release:", workflow)
        self.assertIn("types: [published]", workflow)
        self.assertIn('macos: ["macos-14", "macos-15", "macos-26"]', workflow)
        self.assertIn('python: ["3.11", "3.12", "3.13", "3.14"]', workflow)
        self.assertIn("Verify the release tag matches the package version", workflow)
        self.assertIn("Bootstrap an empty release environment", workflow)
        self.assertIn("Verify the bootstrapped Kokoro English frontend", workflow)
        self.assertIn("-p test_kokoro_frontend.py", workflow)
        self.assertIn("diff -u requirements.lock", workflow)
        self.assertNotIn("uv sync --locked", workflow)
        self.assertIn("uv build --out-dir", workflow)
        self.assertNotIn("twine upload", workflow)
        self.assertNotIn("gh release create", workflow)
        self.assertNotIn("pypi", workflow.lower())

    def test_codeql_scans_python_without_installing_apple_dependencies(self):
        workflow = (ROOT / ".github/workflows/codeql.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("pull_request:", workflow)
        self.assertIn("branches: [main]", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("security-events: write", workflow)
        self.assertIn("runs-on: ubuntu-latest", workflow)
        self.assertIn("languages: python", workflow)
        self.assertIn("build-mode: none", workflow)
        self.assertNotIn("pip install", workflow)
        self.assertNotIn("uv ", workflow)

        action_refs = re.findall(r"uses: [^@\s]+@([^\s]+)", workflow)
        self.assertTrue(action_refs)
        for ref in action_refs:
            self.assertRegex(ref, r"^[0-9a-f]{40}$")

    def test_production_requirements_are_hashed_and_lock_key_dependencies(self):
        requirements = (ROOT / "requirements.lock").read_text(encoding="utf-8")

        self.assertIn("mlx-audio==0.4.5", requirements)
        self.assertIn("misaki==0.9.4", requirements)
        self.assertIn(
            "en-core-web-sm @ https://github.com/explosion/spacy-models/releases/"
            "download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl",
            requirements,
        )
        self.assertIn("huggingface-hub==1.23.0", requirements)
        self.assertIn("--hash=sha256:", requirements)

    def test_bootstrap_scopes_the_misaki_metadata_workaround(self):
        bootstrap = (ROOT / "bin/voicebridge-mcp-bootstrap").read_text(
            encoding="utf-8"
        )
        install_lines = bootstrap.replace("\\\n", "").splitlines()
        ignored = [
            line for line in install_lines if "--ignore-requires-python" in line
        ]

        self.assertEqual(len(ignored), 1)
        self.assertIn("--no-deps", ignored[0])
        self.assertIn("MISAKI_REQUIREMENT", ignored[0])

    def test_plugin_validation_script_passes_for_this_checkout(self):
        result = subprocess.run(
            [sys.executable, "scripts/validate_plugin.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
