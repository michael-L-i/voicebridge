from cadence_code.config import STTConfig, TTSConfig
from cadence_code.providers.base import STTProvider, TTSProvider
from cadence_code.providers.chatterbox_tts import ChatterboxTTSProvider
from cadence_code.providers.kokoro_tts import KokoroTTSProvider
from cadence_code.providers.moonshine_stt import MoonshineSTTProvider
from cadence_code.providers.parakeet_stt import ParakeetSTTProvider
from cadence_code.providers.pocket_tts import PocketTTSProvider
from cadence_code.providers.qwen_tts import QwenTTSProvider
from cadence_code.providers.whisper_stt import WhisperSTTProvider

TTS_PROVIDERS = {
    "chatterbox": ChatterboxTTSProvider,
    "kokoro": KokoroTTSProvider,
    "pocket": PocketTTSProvider,
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
