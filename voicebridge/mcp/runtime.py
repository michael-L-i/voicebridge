import fcntl
import gc
import threading
import time
from pathlib import Path
from typing import Any

from voicebridge.config import CONFIG_DIR, Config, load_config


class VoiceSessionBusy(RuntimeError):
    pass


class VoiceRuntime:
    """Own local voice models for one Claude Code MCP process."""

    def __init__(self, config: Config | None = None):
        self.config = config or load_config()
        self._operation_lock = threading.RLock()
        self._session_lock_file = None
        self._tts: Any = None
        self._stt: Any = None

    @property
    def ready(self) -> bool:
        return self._tts is not None and self._stt is not None

    def start(self) -> dict:
        """Acquire the local voice session and warm both speech models."""
        with self._operation_lock:
            if self.ready:
                return self.status(already_ready=True)

            self._acquire_session_lock()
            started_at = time.monotonic()
            try:
                # Keep heavy MLX imports out of MCP process startup. They are
                # first needed only when the user explicitly starts voice mode.
                from voicebridge.providers.registry import get_stt_provider, get_tts_provider

                self._tts = get_tts_provider(self.config.tts).load()
                self._stt = get_stt_provider(self.config.stt).load()
            except Exception as exc:
                self._release_locked()
                raise RuntimeError(f"could not load local voice models: {exc}") from exc

            return {
                **self.status(),
                "load_ms": int((time.monotonic() - started_at) * 1000),
            }

    def speak(self, text: str, voice: str | None = None) -> dict:
        """Speak Claude Code's exact text with no local rewriting."""
        spoken_text = text.strip()
        if not spoken_text:
            raise ValueError("voice_speak requires non-empty text")

        with self._operation_lock:
            self._ensure_started()
            from voicebridge.audio.playback import play

            started_at = time.monotonic()
            audio = self._tts.synthesize(spoken_text, voice=voice)
            play(audio, self._tts.sample_rate)
            return {
                "spoken_text": spoken_text,
                "duration_ms": int((time.monotonic() - started_at) * 1000),
            }

    def listen(self, timeout_ms: int, silence_ms: int) -> dict:
        with self._operation_lock:
            self._ensure_started()
            from voicebridge.audio.capture import listen

            started_at = time.monotonic()
            audio, timed_out = listen(
                self._stt.sample_rate,
                silence_ms=silence_ms,
                max_listen_ms=timeout_ms,
            )
            transcript = self._stt.transcribe(audio) if audio.size > 0 else ""
            return {
                "transcript": transcript,
                "duration_ms": int((time.monotonic() - started_at) * 1000),
                "timed_out": timed_out,
            }

    def stop(self) -> dict:
        with self._operation_lock:
            stopped = self.ready or self._session_lock_file is not None
            self._release_locked()
            return {"stopped": stopped}

    def status(self, *, already_ready: bool = False) -> dict:
        return {
            "ready": self.ready,
            "already_ready": already_ready,
            "models": {
                "tts": self.config.tts.model if self._tts is not None else None,
                "stt": self.config.stt.model if self._stt is not None else None,
            },
        }

    def _ensure_started(self) -> None:
        if not self.ready:
            self.start()

    def _acquire_session_lock(self) -> None:
        if self._session_lock_file is not None:
            return

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        lock_file = Path(CONFIG_DIR / "active-session.lock").open("a+")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            lock_file.close()
            raise VoiceSessionBusy(
                "another Claude Code session is already using voicebridge"
            ) from exc
        self._session_lock_file = lock_file

    def _release_locked(self) -> None:
        self._tts = None
        self._stt = None
        gc.collect()
        try:
            import mlx.core as mx

            mx.clear_cache()
        except (ImportError, AttributeError):
            pass

        if self._session_lock_file is not None:
            fcntl.flock(self._session_lock_file.fileno(), fcntl.LOCK_UN)
            self._session_lock_file.close()
            self._session_lock_file = None
