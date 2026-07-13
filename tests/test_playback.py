import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
