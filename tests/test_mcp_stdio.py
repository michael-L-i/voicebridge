import json
import subprocess
import sys
import unittest
from pathlib import Path

from voicebridge.providers.registry import STT_PROVIDERS, TTS_PROVIDERS


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "noisy_stdio_server.py"


class MCPStdioTests(unittest.TestCase):
    def test_model_output_never_enters_json_rpc_stdout(self):
        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "stdio-test", "version": "1"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "voice_start", "arguments": {}},
            },
        ]
        result = subprocess.run(
            [sys.executable, str(FIXTURE)],
            cwd=ROOT,
            input="".join(json.dumps(message) + "\n" for message in messages),
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        frames = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([frame.get("id") for frame in frames], [1, 2])
        self.assertTrue(all(frame.get("jsonrpc") == "2.0" for frame in frames))

        providers = {*TTS_PROVIDERS, *STT_PROVIDERS}
        for provider in providers:
            self.assertNotIn(f"NOISY {provider}", result.stdout)
            self.assertIn(f"NOISY {provider} load", result.stderr)
            self.assertIn(f"NOISY {provider} inference", result.stderr)


if __name__ == "__main__":
    unittest.main()
