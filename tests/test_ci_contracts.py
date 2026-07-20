import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CiContractTests(unittest.TestCase):
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
        self.assertIn("diff -u requirements.lock", workflow)
        self.assertNotIn("uv sync --locked", workflow)
        self.assertIn("uv build --out-dir", workflow)
        self.assertNotIn("twine upload", workflow)
        self.assertNotIn("gh release create", workflow)
        self.assertNotIn("pypi", workflow.lower())

    def test_production_requirements_are_hashed_and_lock_key_dependencies(self):
        requirements = (ROOT / "requirements.lock").read_text(encoding="utf-8")

        self.assertIn("mlx-audio==0.4.5", requirements)
        self.assertIn("misaki==0.9.4", requirements)
        self.assertIn("huggingface-hub==1.23.0", requirements)
        self.assertIn("--hash=sha256:", requirements)

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
