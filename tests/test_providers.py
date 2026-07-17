import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from voicebridge.config import STTConfig, TTSConfig
from voicebridge.providers.chatterbox_tts import ChatterboxTTSProvider
from voicebridge.providers.moonshine_stt import MoonshineSTTProvider
from voicebridge.providers.qwen_tts import QwenTTSProvider
from voicebridge.providers.registry import STT_PROVIDERS, TTS_PROVIDERS


class QwenTTSProviderTests(unittest.TestCase):
    def test_loads_once_and_joins_aiden_english_audio(self):
        model = Mock()
        model.generate.return_value = [
            SimpleNamespace(audio=np.array([0.1])),
            SimpleNamespace(audio=np.array([0.2, 0.3])),
        ]
        config = TTSConfig(
            provider="qwen",
            model="mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit",
            voice="Aiden",
            speed=1.1,
        )

        with patch(
            "voicebridge.providers.qwen_tts.load_model",
            return_value=model,
        ) as load_model:
            provider = QwenTTSProvider(config)
            self.assertIs(provider.load(), provider)
            audio = provider.synthesize("Hello from Qwen.")

        load_model.assert_called_once_with(
            "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit"
        )
        model.generate.assert_called_once_with(
            text="Hello from Qwen.",
            voice="Aiden",
            lang_code="english",
            speed=1.1,
        )
        np.testing.assert_allclose(audio, [0.1, 0.2, 0.3])
        self.assertEqual(audio.dtype, np.float32)
        self.assertEqual(provider.sample_rate, 24000)

    def test_voice_override_replaces_configured_speaker(self):
        model = Mock()
        model.generate.return_value = []

        with patch(
            "voicebridge.providers.qwen_tts.load_model",
            return_value=model,
        ):
            audio = QwenTTSProvider(TTSConfig(voice="Aiden")).synthesize(
                "Use Ryan.", voice="Ryan"
            )

        self.assertEqual(model.generate.call_args.kwargs["voice"], "Ryan")
        self.assertEqual(audio.size, 0)

    def test_is_registered(self):
        self.assertIs(TTS_PROVIDERS["qwen"], QwenTTSProvider)


class ChatterboxTTSProviderTests(unittest.TestCase):
    def test_loads_once_and_joins_default_voice_audio(self):
        model = Mock()
        model.generate.return_value = [
            SimpleNamespace(audio=np.array([0.1, 0.2])),
            SimpleNamespace(audio=np.array([0.3])),
        ]
        config = TTSConfig(
            provider="chatterbox",
            model="mlx-community/chatterbox-turbo-4bit",
            voice="default",
        )

        with patch(
            "voicebridge.providers.chatterbox_tts.load_model",
            return_value=model,
        ) as load_model:
            provider = ChatterboxTTSProvider(config)
            self.assertIs(provider.load(), provider)
            audio = provider.synthesize("Hello there.")

        load_model.assert_called_once_with("mlx-community/chatterbox-turbo-4bit")
        model.generate.assert_called_once_with(text="Hello there.")
        np.testing.assert_allclose(audio, [0.1, 0.2, 0.3])
        self.assertEqual(audio.dtype, np.float32)
        self.assertEqual(provider.sample_rate, 24000)

    def test_voice_override_is_used_as_reference_audio(self):
        model = Mock()
        model.generate.return_value = []
        config = TTSConfig(voice="default")

        with patch(
            "voicebridge.providers.chatterbox_tts.load_model",
            return_value=model,
        ):
            audio = ChatterboxTTSProvider(config).synthesize(
                "Clone this.", voice="voice.wav"
            )

        model.generate.assert_called_once_with(
            text="Clone this.", ref_audio="voice.wav"
        )
        self.assertEqual(audio.dtype, np.float32)
        self.assertEqual(audio.size, 0)

    def test_is_registered(self):
        self.assertIs(TTS_PROVIDERS["chatterbox"], ChatterboxTTSProvider)


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
