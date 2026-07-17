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
                "VOICEBRIDGE_DEV_NPX_BIN": str(fake_npx),
                "VOICEBRIDGE_DEV_DATA_ROOT": str(data_root),
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
            f"VOICEBRIDGE_DATA_DIR={data_root}/inspector", arguments
        )
        self.assertIn("VOICEBRIDGE_HOST=inspector", arguments)
        self.assertIn(str(ROOT / "bin/voicebridge-mcp-bootstrap"), arguments)


if __name__ == "__main__":
    unittest.main()
