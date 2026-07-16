import unittest
from unittest.mock import patch

import numpy as np

from voicebridge.audio import playback


class ChimeTests(unittest.TestCase):
    def test_start_chime_has_only_a_short_trailing_pause(self):
        with patch.object(playback, "_chime_amplitude", return_value=0.075):
            chime = playback._generate_chime([800, 1000], None)

        tone_duration = 2 * playback._CHIME_TONE_S
        expected_samples = int(
            playback._CHIME_SAMPLE_RATE
            * (tone_duration + playback._CHIME_TRAILING_SILENCE_S)
        )
        self.assertEqual(chime.size, expected_samples)
        self.assertLessEqual(chime.size / playback._CHIME_SAMPLE_RATE, 0.25)

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
