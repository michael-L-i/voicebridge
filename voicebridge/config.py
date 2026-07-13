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
_CURRENT_CONFIG_VERSION = 2
_OLD_DEFAULT_SILENCE_MS = 800
_DEFAULT_SILENCE_MS = 2000
_SILENCE_SETTING = re.compile(
    rf"^(\s*silence_ms\s*=\s*){_OLD_DEFAULT_SILENCE_MS}(\s*(?:#.*)?)$"
)


class TTSConfig(BaseModel):
    provider: str = "kokoro"
    model: str = "mlx-community/Kokoro-82M-bf16"
    voice: str = "af_heart"
    speed: float = 1.0


class STTConfig(BaseModel):
    provider: str = "parakeet"
    model: str = "mlx-community/parakeet-tdt-0.6b-v3"
    silence_ms: int = _DEFAULT_SILENCE_MS
    max_listen_ms: int = 30000


class AudioConfig(BaseModel):
    input_device: str | int = "default"
    output_device: str | int = "default"


class Config(BaseModel):
    config_version: int = _CURRENT_CONFIG_VERSION
    tts: TTSConfig = TTSConfig()
    stt: STTConfig = STTConfig()
    audio: AudioConfig = AudioConfig()


def ensure_config_exists() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        shutil.copy(DEFAULT_CONFIG_PATH, CONFIG_PATH)
    else:
        _migrate_config(CONFIG_PATH)
    return CONFIG_PATH


def _migrate_config(path: Path) -> None:
    """Migrate old defaults and remove retired runtime settings."""
    original = path.read_text(encoding="utf-8")
    parsed = tomllib.loads(original)
    version = int(parsed.get("config_version", 1))
    kept_lines = []
    in_legacy_section = False
    current_section = None

    for line in original.splitlines(keepends=True):
        newline = (
            "\r\n"
            if line.endswith("\r\n")
            else "\n"
            if line.endswith("\n")
            else ""
        )
        content = line[: -len(newline)] if newline else line
        header = _SECTION_HEADER.match(content)
        if header:
            current_section = header.group(1).strip()
            in_legacy_section = current_section in _LEGACY_SECTIONS
        elif version < 2 and current_section == "stt":
            content = _SILENCE_SETTING.sub(
                rf"\g<1>{_DEFAULT_SILENCE_MS}\g<2>", content
            )
            line = content + newline
        if not in_legacy_section:
            kept_lines.append(line)

    cleaned = "".join(kept_lines).lstrip("\r\n")
    if version < _CURRENT_CONFIG_VERSION:
        cleaned = f"config_version = {_CURRENT_CONFIG_VERSION}\n\n{cleaned}"
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
