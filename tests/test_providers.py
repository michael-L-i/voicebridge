import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from voicebridge.config import STTConfig
from voicebridge.providers.moonshine_stt import MoonshineSTTProvider
from voicebridge.providers.registry import STT_PROVIDERS


class MoonshineSTTProviderTests(unittest.TestCase):
    def test_loads_once_and_transcribes_float32_audio(self):
        model = Mock()
        model.generate.return_value = SimpleNamespace(text="  hello moonshine  ")
        config = STTConfig(
            provider="moonshine",
            model="UsefulSensors/moonshine-base",
        )

        with patch(
            "voicebridge.providers.moonshine_stt.load_model",
            return_value=model,
        ) as load_model:
            provider = MoonshineSTTProvider(config)
            self.assertIs(provider.load(), provider)
            self.assertIs(provider.load(), provider)
            transcript = provider.transcribe(np.ones(8, dtype=np.float64))

        load_model.assert_called_once_with("UsefulSensors/moonshine-base")
        audio = model.generate.call_args.args[0]
        self.assertEqual(audio.dtype, np.float32)
        self.assertEqual(transcript, "hello moonshine")
        self.assertEqual(provider.sample_rate, 16000)

    def test_is_registered(self):
        self.assertIs(STT_PROVIDERS["moonshine"], MoonshineSTTProvider)


if __name__ == "__main__":
    unittest.main()
