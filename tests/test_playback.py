import unittest
from unittest.mock import patch

import numpy as np

from voicebridge.audio import playback


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

        with (
            patch.object(playback.sd, "play") as play,
            patch.object(playback.sd, "wait") as wait,
        ):
            handle = playback.play_async(audio, 24000)
            handle.wait()

        play.assert_called_once_with(
            audio,
            samplerate=24000,
            blocking=False,
            device=None,
        )
        wait.assert_called_once()


if __name__ == "__main__":
    unittest.main()
