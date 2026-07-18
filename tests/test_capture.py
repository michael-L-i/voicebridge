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

    def test_noise_blip_does_not_reset_silence_countdown(self):
        frame = np.zeros(480, dtype=np.float32)
        blocks = [frame] * 7
        decisions = [True, True, False, False, True, False]

        result = self._listen(
            blocks,
            decisions,
            silence_ms=90,
            max_listen_ms=1000,
        )

        self.assertEqual(result.end_reason, "silence")
        self.assertTrue(result.speech_detected)
        self.assertEqual(result.audio.size, 6 * frame.size)

    def test_resumed_speech_resets_silence_countdown(self):
        frame = np.zeros(480, dtype=np.float32)
        blocks = [frame] * 10
        decisions = [True, True, False, False, True, True, False, False, False]

        result = self._listen(
            blocks,
            decisions,
            silence_ms=90,
            max_listen_ms=1000,
        )

        self.assertEqual(result.end_reason, "silence")
        self.assertEqual(result.audio.size, 9 * frame.size)

    def test_onset_and_endpointing_use_separate_classifiers(self):
        class _RecordingVad:
            def __init__(self, decisions):
                self._decisions = iter(decisions)
                self.calls = 0

            def is_speech(self, pcm16, sample_rate):
                self.calls += 1
                return next(self._decisions)

        frame = np.zeros(480, dtype=np.float32)
        blocks = [frame] * 6
        onset = _RecordingVad([False, True, True])
        endpoint = _RecordingVad([False, False])
        vads = {
            capture._VAD_ONSET_AGGRESSIVENESS: onset,
            capture._VAD_AGGRESSIVENESS: endpoint,
        }

        stream = lambda **stream_kwargs: _FakeInputStream(
            blocks=blocks, **stream_kwargs
        )
        with (
            patch.object(capture.sd, "InputStream", stream),
            patch.object(capture, "play_chime_start"),
            patch.object(capture, "play_chime_end"),
            patch.object(capture.webrtcvad, "Vad", side_effect=lambda agg: vads[agg]),
            patch.object(capture, "_SETTLE_MS", 30),
            patch.object(capture, "_MIN_SPEECH_MS", 60),
            patch.object(capture, "_PRE_ROLL_MS", 120),
        ):
            result = capture.listen(16000, silence_ms=60, max_listen_ms=1000)

        self.assertEqual(result.end_reason, "silence")
        self.assertEqual(onset.calls, 3)
        self.assertEqual(endpoint.calls, 2)

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

    def test_chimes_can_be_split_across_internal_capture_attempts(self):
        with (
            patch.object(
                capture.sd,
                "InputStream",
                lambda **kwargs: _FakeInputStream(**kwargs),
            ),
            patch.object(capture, "play_chime_start") as play_start,
            patch.object(capture, "play_chime_end") as play_end,
            patch.object(capture, "_SETTLE_MS", 1),
        ):
            capture.listen(
                16000,
                max_listen_ms=1,
                start_chime=False,
                end_chime=False,
            )

        play_start.assert_not_called()
        play_end.assert_not_called()

    def test_active_speech_refreshes_the_wall_clock_deadline(self):
        frame = np.zeros(480, dtype=np.float32)
        blocks = [frame] * 13

        class _Clock:
            now = 0.0

            def monotonic(self):
                return self.now

            def advance(self):
                self.now += 0.02

        clock = _Clock()

        class _TimedQueue:
            def __init__(self):
                self.items = []

            def put(self, item):
                self.items.append(item)

            def get(self, timeout=None):
                if not self.items:
                    raise capture.queue.Empty
                clock.advance()
                return self.items.pop(0)

        stream = lambda **stream_kwargs: _FakeInputStream(
            blocks=blocks, **stream_kwargs
        )

        with (
            patch.object(capture.sd, "InputStream", stream),
            patch.object(capture, "play_chime_start"),
            patch.object(capture, "play_chime_end"),
            patch.object(capture.queue, "Queue", _TimedQueue),
            patch.object(capture.time, "monotonic", clock.monotonic),
            patch.object(
                capture.webrtcvad,
                "Vad",
                return_value=_FakeVad([True] * 5 + [False] * 7),
            ),
            patch.object(capture, "_SETTLE_MS", 1),
            patch.object(capture, "_MIN_SPEECH_MS", 30),
        ):
            result = capture.listen(
                16000,
                silence_ms=200,
                max_listen_ms=200,
            )

        self.assertGreater(clock.now, 0.2)
        self.assertEqual(result.end_reason, "silence")
        self.assertTrue(result.speech_detected)

    def test_callback_stall_is_reported_as_a_device_error(self):
        with (
            patch.object(
                capture.sd,
                "InputStream",
                lambda **kwargs: _FakeInputStream(**kwargs),
            ),
            patch.object(capture, "play_chime_start"),
            patch.object(capture, "play_chime_end"),
            patch.object(capture, "_SETTLE_MS", 1),
            patch.object(capture, "_DEVICE_STALL_S", 0.03),
        ):
            result = capture.listen(16000, max_listen_ms=1000)

        self.assertEqual(result.end_reason, "device_error")
        self.assertIn("stopped delivering", result.error)


if __name__ == "__main__":
    unittest.main()
