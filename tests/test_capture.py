import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

try:
    import webrtcvad  # noqa: F401
except ImportError:
    sys.modules["webrtcvad"] = SimpleNamespace(Vad=lambda *args: None)

from voicebridge.audio import capture


class _FakeVad:
    def __init__(self, decisions):
        self._decisions = iter(decisions)

    def is_speech(self, pcm16, sample_rate):
        return next(self._decisions)


class _FakeInputStream:
    def __init__(self, callback, blocks=(), error=None, **kwargs):
        self._callback = callback
        self._blocks = blocks
        self._error = error

    def __enter__(self):
        if self._error:
            raise self._error
        for block in self._blocks:
            self._callback(block[:, None], None, None, None)
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class ListenTests(unittest.TestCase):
    def _listen(self, blocks, decisions, **kwargs):
        stream = lambda **stream_kwargs: _FakeInputStream(
            blocks=blocks, **stream_kwargs
        )
        with (
            patch.object(capture.sd, "InputStream", stream),
            patch.object(capture, "play_chime_start"),
            patch.object(capture, "play_chime_end"),
            patch.object(capture.webrtcvad, "Vad", return_value=_FakeVad(decisions)),
            patch.object(capture, "_SETTLE_MS", 30),
            patch.object(capture, "_MIN_SPEECH_MS", 60),
            patch.object(capture, "_PRE_ROLL_MS", 120),
        ):
            return capture.listen(16000, **kwargs)

    def test_natural_pause_keeps_only_short_preroll(self):
        frame = np.zeros(480, dtype=np.float32)
        blocks = [frame] + ([frame] * 20) + ([frame] * 2) + ([frame] * 2)
        decisions = ([False] * 20) + [True, True, False, False]

        result = self._listen(
            blocks,
            decisions,
            silence_ms=60,
            max_listen_ms=1000,
        )

        self.assertEqual(result.end_reason, "silence")
        self.assertTrue(result.speech_detected)
        self.assertEqual(result.audio.size, 6 * frame.size)

    def test_empty_device_callback_obeys_wall_clock_timeout(self):
        started_at = time.monotonic()
        result = self._listen(
            [],
            [],
            silence_ms=60,
            max_listen_ms=30,
        )

        self.assertLess(time.monotonic() - started_at, 0.5)
        self.assertEqual(result.end_reason, "timeout")
        self.assertFalse(result.speech_detected)

    def test_input_device_failure_is_a_result(self):
        stream = lambda **stream_kwargs: _FakeInputStream(
            error=OSError("device disconnected"), **stream_kwargs
        )
        with (
            patch.object(capture.sd, "InputStream", stream),
            patch.object(capture, "play_chime_start"),
            patch.object(capture, "play_chime_end"),
        ):
            result = capture.listen(16000, max_listen_ms=30)

        self.assertEqual(result.end_reason, "device_error")
        self.assertIn("device disconnected", result.error)
        self.assertFalse(result.speech_detected)


if __name__ == "__main__":
    unittest.main()
