import shutil
import tomllib
from pathlib import Path

from pydantic import BaseModel

CONFIG_DIR = Path.home() / ".voicebridge"
CONFIG_PATH = CONFIG_DIR / "config.toml"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default_config.toml"


class DaemonConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8756


class SummarizerConfig(BaseModel):
    model: str = "mlx-community/Qwen2.5-3B-Instruct-4bit"
    max_tokens: int = 80
    context_window_summaries: int = 3


class TTSConfig(BaseModel):
    provider: str = "kokoro"
    model: str = "mlx-community/Kokoro-82M-bf16"
    voice: str = "af_heart"
    speed: float = 1.0


class STTConfig(BaseModel):
    provider: str = "parakeet"
    model: str = "mlx-community/parakeet-tdt-0.6b-v3"
    silence_ms: int = 800
    max_listen_ms: int = 30000


class NarrationConfig(BaseModel):
    min_narrate_chars: int = 40
    narrate_stop: bool = True
    narrate_subagent_stop: bool = True


class AudioConfig(BaseModel):
    input_device: str = "default"
    output_device: str = "default"


class Config(BaseModel):
    daemon: DaemonConfig = DaemonConfig()
    summarizer: SummarizerConfig = SummarizerConfig()
    tts: TTSConfig = TTSConfig()
    stt: STTConfig = STTConfig()
    narration: NarrationConfig = NarrationConfig()
    audio: AudioConfig = AudioConfig()


def ensure_config_exists() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        shutil.copy(DEFAULT_CONFIG_PATH, CONFIG_PATH)
    return CONFIG_PATH


def load_config() -> Config:
    path = ensure_config_exists()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return Config.model_validate(data)
