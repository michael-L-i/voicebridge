import os
import re
import shutil
import tempfile
import tomllib
from pathlib import Path

from pydantic import BaseModel

# Under the Claude Code plugin, the manifest sets this to ${CLAUDE_PLUGIN_DATA}.
# (a persistent per-plugin data dir) so config and the active-session lock
# live there instead of a path hardcoded to one machine. Falls back to
# ~/.voicebridge for direct-Python development commands.
CONFIG_DIR = Path(os.environ.get("VOICEBRIDGE_DATA_DIR", str(Path.home() / ".voicebridge")))
CONFIG_PATH = CONFIG_DIR / "config.toml"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default_config.toml"
_SECTION_HEADER = re.compile(r"^\s*\[([^]]+)]\s*(?:#.*)?$")
_LEGACY_SECTIONS = {"daemon", "summarizer"}


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


class AudioConfig(BaseModel):
    input_device: str | int = "default"
    output_device: str | int = "default"


class Config(BaseModel):
    tts: TTSConfig = TTSConfig()
    stt: STTConfig = STTConfig()
    audio: AudioConfig = AudioConfig()


def ensure_config_exists() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        shutil.copy(DEFAULT_CONFIG_PATH, CONFIG_PATH)
    else:
        _remove_legacy_sections(CONFIG_PATH)
    return CONFIG_PATH


def _remove_legacy_sections(path: Path) -> None:
    """Remove settings from the retired daemon and Qwen summarizer."""
    original = path.read_text(encoding="utf-8")
    kept_lines = []
    in_legacy_section = False

    for line in original.splitlines(keepends=True):
        header = _SECTION_HEADER.match(line.rstrip("\r\n"))
        if header:
            in_legacy_section = header.group(1).strip() in _LEGACY_SECTIONS
        if not in_legacy_section:
            kept_lines.append(line)

    cleaned = "".join(kept_lines).lstrip("\r\n")
    if cleaned == original:
        return

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as temporary:
        temporary.write(cleaned)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def load_config() -> Config:
    path = ensure_config_exists()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return Config.model_validate(data)
