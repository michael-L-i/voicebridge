from voicebridge.config import STTConfig, TTSConfig
from voicebridge.providers.base import STTProvider, TTSProvider
from voicebridge.providers.chatterbox_tts import ChatterboxTTSProvider
from voicebridge.providers.kokoro_tts import KokoroTTSProvider
from voicebridge.providers.moonshine_stt import MoonshineSTTProvider
from voicebridge.providers.parakeet_stt import ParakeetSTTProvider
from voicebridge.providers.qwen_tts import QwenTTSProvider
from voicebridge.providers.whisper_stt import WhisperSTTProvider

TTS_PROVIDERS = {
    "chatterbox": ChatterboxTTSProvider,
    "kokoro": KokoroTTSProvider,
    "qwen": QwenTTSProvider,
}

STT_PROVIDERS = {
    "moonshine": MoonshineSTTProvider,
    "parakeet": ParakeetSTTProvider,
    "whisper": WhisperSTTProvider,
}


def get_tts_provider(config: TTSConfig) -> TTSProvider:
    try:
        cls = TTS_PROVIDERS[config.provider]
    except KeyError:
        raise ValueError(
            f"Unknown tts.provider {config.provider!r}. Available: {sorted(TTS_PROVIDERS)}"
        )
    return cls(config)


def get_stt_provider(config: STTConfig) -> STTProvider:
    try:
        cls = STT_PROVIDERS[config.provider]
    except KeyError:
        raise ValueError(
            f"Unknown stt.provider {config.provider!r}. Available: {sorted(STT_PROVIDERS)}"
        )
    return cls(config)
