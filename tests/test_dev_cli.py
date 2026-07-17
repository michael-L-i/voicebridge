import subprocess
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


if __name__ == "__main__":
    unittest.main()
