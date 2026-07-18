import json
import os
import re
import shutil
import tempfile
import tomllib
from pathlib import Path

from pydantic import BaseModel

# Claude Code sets this to its persistent per-plugin data directory. Codex and
# direct development use ~/.voicebridge. The machine-wide audio-session lock is
# deliberately separate so every host contends on the same lock.
CONFIG_DIR = Path(os.environ.get("VOICEBRIDGE_DATA_DIR", str(Path.home() / ".voicebridge")))
CONFIG_PATH = CONFIG_DIR / "config.toml"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default_config.toml"
_SECTION_HEADER = re.compile(r"^\s*\[([^]]+)]\s*(?:#.*)?$")
_LEGACY_SECTIONS = {"daemon", "summarizer"}
_CURRENT_CONFIG_VERSION = 3
_DEFAULT_SILENCE_MS = 1000
# silence_ms defaults shipped by earlier config versions. A stored value is
# migrated only when it still equals the default of its own version, so a
# user-chosen value survives the upgrade.
_OLD_SILENCE_DEFAULTS = {1: 800, 2: 2000}
_VERSION_SETTING = re.compile(r"^\s*config_version\s*=\s*\d+\s*(?:#.*)?$")


class TTSConfig(BaseModel):
    provider: str = "qwen"
    model: str = "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit"
    voice: str = "Aiden"
    speed: float = 1.0


class STTConfig(BaseModel):
    provider: str = "whisper"
    model: str = "mlx-community/whisper-small.en-asr-fp16"
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
    old_silence_default = _OLD_SILENCE_DEFAULTS.get(version)
    silence_setting = (
        re.compile(rf"^(\s*silence_ms\s*=\s*){old_silence_default}(\s*(?:#.*)?)$")
        if old_silence_default is not None
        else None
    )
    kept_lines = []
    in_legacy_section = False
    current_section = None
    version_line_seen = False

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
        elif current_section is None and _VERSION_SETTING.match(content):
            version_line_seen = True
            line = f"config_version = {_CURRENT_CONFIG_VERSION}{newline}"
        elif silence_setting is not None and current_section == "stt":
            content = silence_setting.sub(
                rf"\g<1>{_DEFAULT_SILENCE_MS}\g<2>", content
            )
            line = content + newline
        if not in_legacy_section:
            kept_lines.append(line)

    cleaned = "".join(kept_lines).lstrip("\r\n")
    if version < _CURRENT_CONFIG_VERSION and not version_line_seen:
        cleaned = f"config_version = {_CURRENT_CONFIG_VERSION}\n\n{cleaned}"
    if cleaned == original:
        return

    _write_atomic(path, cleaned)


def load_config() -> Config:
    path = ensure_config_exists()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return Config.model_validate(data)


def save_model_selection(tts: TTSConfig, stt: STTConfig) -> Config:
    path = ensure_config_exists()
    original = path.read_text(encoding="utf-8")
    updated = _replace_section_settings(
        original,
        "tts",
        {
            "provider": tts.provider,
            "model": tts.model,
            "voice": tts.voice,
            "speed": tts.speed,
        },
    )
    updated = _replace_section_settings(
        updated,
        "stt",
        {
            "provider": stt.provider,
            "model": stt.model,
            "silence_ms": stt.silence_ms,
            "max_listen_ms": stt.max_listen_ms,
        },
    )
    if updated != original:
        _write_atomic(path, updated)
    return Config.model_validate(tomllib.loads(updated))


def _replace_section_settings(
    text: str,
    section: str,
    settings: dict[str, str | int | float],
) -> str:
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    start = None
    end = len(lines)

    for index, line in enumerate(lines):
        header = _SECTION_HEADER.match(line.rstrip("\r\n"))
        if header and header.group(1).strip() == section:
            start = index
            continue
        if start is not None and header:
            end = index
            break

    if start is None:
        separator = "" if not text or text.endswith(("\n", "\r")) else newline
        body = "".join(
            f"{key} = {json.dumps(value)}{newline}"
            for key, value in settings.items()
        )
        return f"{text}{separator}{newline}[{section}]{newline}{body}"

    remaining = dict(settings)
    assignment = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z_][\w-]*)\s*=")
    for index in range(start + 1, end):
        match = assignment.match(lines[index])
        if match and match.group("key") in remaining:
            key = match.group("key")
            line_ending = (
                "\r\n"
                if lines[index].endswith("\r\n")
                else "\n"
                if lines[index].endswith("\n")
                else newline
            )
            lines[index] = (
                f"{match.group('indent')}{key} = {json.dumps(remaining.pop(key))}"
                f"{line_ending}"
            )

    if remaining:
        if end > start + 1 and not lines[end - 1].endswith(("\n", "\r")):
            lines[end - 1] += newline
        insertion = [
            f"{key} = {json.dumps(value)}{newline}"
            for key, value in remaining.items()
        ]
        lines[end:end] = insertion
    return "".join(lines)


def _write_atomic(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as temporary:
        temporary.write(text)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)
