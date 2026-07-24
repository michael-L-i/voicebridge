import unittest
from unittest.mock import patch

from cadence_code.mcp import server
from cadence_code.mcp.runtime import VoiceSessionNotStarted


class VoiceServerTests(unittest.TestCase):
    def test_start_can_return_before_models_finish_loading(self):
        with patch.object(
            server.runtime,
            "start",
            return_value={"ready": False, "starting": True},
        ) as start:
            result = server.voice_start(wait=False)

        start.assert_called_once_with(wait=False)
        self.assertEqual(result, {"ok": True, "ready": False, "starting": True})

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
