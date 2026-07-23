import unittest
import threading
from unittest.mock import patch

import numpy as np

from cadence_code.audio import playback


class ChimeTests(unittest.TestCase):
    def test_start_chime_has_only_a_short_trailing_pause(self):
        with patch.object(playback, "_chime_amplitude", return_value=0.075):
            chime = playback._generate_chime([659.26, 987.77], None)

        ringing_duration = playback._CHIME_NOTE_SPACING_S + playback._CHIME_NOTE_S
        expected_samples = int(playback._CHIME_SAMPLE_RATE * ringing_duration) + int(
            playback._CHIME_SAMPLE_RATE * playback._CHIME_TRAILING_SILENCE_S
        )
        self.assertEqual(chime.size, expected_samples)
        self.assertLessEqual(chime.size / playback._CHIME_SAMPLE_RATE, 0.3)

    def test_chime_peak_matches_device_amplitude(self):
        with patch.object(playback, "_chime_amplitude", return_value=0.15):
            chime = playback._generate_chime([659.26, 987.77], None)

        self.assertAlmostEqual(float(np.max(np.abs(chime))), 0.15, places=5)

    def test_async_playback_returns_after_start_and_waits_on_handle(self):
        audio = np.ones(8, dtype=np.float32)

        streams = []

        class _OutputStream:
            def __init__(self, callback, finished_callback, **kwargs):
                self.callback = callback
                self.finished_callback = finished_callback
                self.kwargs = kwargs
                streams.append(self)

            def __enter__(self):
                while True:
                    outdata = np.empty((4, 1), dtype=np.float32)
                    try:
                        self.callback(outdata, 4, None, None)
                    except playback.sd.CallbackStop:
                        self.finished_callback()
                        break
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def abort(self, ignore_errors=False):
                self.finished_callback()

        with patch.object(playback.sd, "OutputStream", _OutputStream):
            handle = playback.play_async(audio, 24000)
            handle.wait()

        self.assertEqual(streams[0].kwargs["samplerate"], 24000)
        self.assertEqual(streams[0].kwargs["channels"], 1)
        self.assertEqual(streams[0].kwargs["device"], None)

    def test_async_playback_can_be_cancelled_idempotently(self):
        audio = np.ones(24000, dtype=np.float32)
        aborted = threading.Event()

        class _StalledOutputStream:
            def __init__(self, finished_callback, **kwargs):
                self.finished_callback = finished_callback

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def abort(self, ignore_errors=False):
                aborted.set()
                self.finished_callback()

        with patch.object(playback.sd, "OutputStream", _StalledOutputStream):
            handle = playback.play_async(audio, 24000)
            handle.cancel()
            handle.cancel()
            handle.wait(timeout=0.5)

        self.assertTrue(aborted.is_set())
        self.assertTrue(handle.cancelled)


if __name__ == "__main__":
    unittest.main()
