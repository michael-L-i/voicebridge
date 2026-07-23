import unittest
from unittest.mock import patch

from cadence_code.mcp import server
from cadence_code.mcp.runtime import VoiceSessionNotStarted


class VoiceServerTests(unittest.TestCase):
    def test_speak_returns_stable_session_not_started_error(self):
        with patch.object(
            server.runtime,
            "speak",
            side_effect=VoiceSessionNotStarted(),
        ):
            result = server.voice_speak("Hello")

        self.assertEqual(
            result,
            {
                "ok": False,
                "error": "voice session is not started; call voice_start first",
                "error_code": "session_not_started",
            },
        )

    def test_listen_returns_stable_session_not_started_error(self):
        with patch.object(
            server.runtime,
            "listen",
            side_effect=VoiceSessionNotStarted(),
        ):
            result = server.voice_listen()

        self.assertEqual(
            result,
            {
                "ok": False,
                "error": "voice session is not started; call voice_start first",
                "error_code": "session_not_started",
            },
        )


if __name__ == "__main__":
    unittest.main()
