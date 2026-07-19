TTS_MODELS = (
    {
        "id": "kokoro",
        "label": "Kokoro 82M",
        "tier": "lightweight",
        "parameters_millions": 82,
        "download_mb": 389,
        "provider": "kokoro",
        "model": "mlx-community/Kokoro-82M-bf16",
        "voice": "af_heart",
        "description": "Fast, compact speech with a clean built-in voice.",
    },
    {
        "id": "chatterbox",
        "label": "Chatterbox Turbo 350M",
        "tier": "balanced",
        "parameters_millions": 350,
        "download_mb": 417,
        "provider": "chatterbox",
        "model": "mlx-community/chatterbox-turbo-4bit",
        "voice": "default",
        "description": "More expressive English speech at a moderate footprint.",
    },
    {
        "id": "qwen",
        "label": "Qwen 0.6B",
        "tier": "heavy",
        "parameters_millions": 600,
        "download_mb": 1974,
        "provider": "qwen",
        "model": "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit",
        "voice": "Aiden",
        "description": "The most natural built-in voice with higher memory use.",
    },
)

STT_MODELS = (
    {
        "id": "moonshine",
        "label": "Moonshine Base 61M",
        "tier": "lightweight",
        "parameters_millions": 61,
        "download_mb": 248,
        "provider": "moonshine",
        "model": "UsefulSensors/moonshine-base",
        "description": "Very light, low-latency English transcription.",
    },
    {
        "id": "parakeet-110m",
        "label": "Parakeet 110M",
        "tier": "balanced",
        "parameters_millions": 114,
        "download_mb": 459,
        "provider": "parakeet",
        "model": "mlx-community/parakeet-tdt_ctc-110m",
        "description": "Accurate, noise-robust English transcription with balanced resource use.",
    },
    {
        "id": "parakeet",
        "label": "Parakeet 0.6B v3",
        "tier": "heavy",
        "parameters_millions": 600,
        "download_mb": 2509,
        "provider": "parakeet",
        "model": "mlx-community/parakeet-tdt-0.6b-v3",
        "description": "The most accurate option with 25-language support.",
    },
)

DEFAULT_TTS_MODEL = "qwen"
DEFAULT_STT_MODEL = "parakeet-110m"


def get_model_option(kind: str, option_id: str) -> dict:
    options = TTS_MODELS if kind == "tts" else STT_MODELS if kind == "stt" else ()
    for option in options:
        if option["id"] == option_id:
            return dict(option)
    available = [option["id"] for option in options]
    if not available:
        raise ValueError(f"Unknown model kind {kind!r}")
    raise ValueError(
        f"Unknown {kind} model {option_id!r}. Available: {available}"
    )


def _selected_id(options: tuple[dict, ...], provider: str, model: str) -> str | None:
    for option in options:
        if option["provider"] == provider and option["model"] == model:
            return option["id"]
    return None


def model_catalog(
    *,
    tts_provider: str,
    tts_model: str,
    stt_provider: str,
    stt_model: str,
) -> dict:
    return {
        "defaults": {"tts": DEFAULT_TTS_MODEL, "stt": DEFAULT_STT_MODEL},
        "current": {
            "tts": _selected_id(TTS_MODELS, tts_provider, tts_model),
            "stt": _selected_id(STT_MODELS, stt_provider, stt_model),
        },
        "tts": [
            {**option, "default": option["id"] == DEFAULT_TTS_MODEL}
            for option in TTS_MODELS
        ],
        "stt": [
            {**option, "default": option["id"] == DEFAULT_STT_MODEL}
            for option in STT_MODELS
        ],
    }
