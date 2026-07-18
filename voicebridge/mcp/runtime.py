import fcntl
import gc
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from voicebridge import __version__
from voicebridge.config import (
    CONFIG_DIR,
    Config,
    STTConfig,
    TTSConfig,
    load_config,
    save_model_selection,
)

SESSION_LOCK_PATH = Path.home() / ".voicebridge" / "active-session.lock"
_ONBOARDING_MARKER = "onboarding-v1.complete"


class VoiceSessionBusy(RuntimeError):
    pass


@dataclass(frozen=True)
class _QueuedCapture:
    result: Any
    started_at: float
    timeout_ms: int
    silence_ms: int


class _QueuedListen:
    def __init__(self, target: Callable[[], Any]) -> None:
        self._target = target
        self._result: Any = None
        self._error: Exception | None = None
        self._thread = threading.Thread(
            target=self._run,
            name="voicebridge-queued-listen",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        try:
            self._result = self._target()
        except Exception as exc:
            self._error = exc

    def wait(self) -> Any:
        self._thread.join()
        if self._error is not None:
            raise self._error
        if self._result is None:
            raise RuntimeError("queued microphone capture returned no result")
        return self._result


class VoiceRuntime:
    """Own local voice models for one host MCP process."""

    def __init__(self, config: Config | None = None, *, data_dir: Path | None = None):
        self.config = config or load_config()
        self.data_dir = Path(data_dir) if data_dir is not None else CONFIG_DIR
        self.host = os.environ.get("VOICEBRIDGE_HOST", "direct")
        self._operation_lock = threading.RLock()
        self._session_lock_file = None
        self._last_preflight: dict | None = None
        self._tts: Any = None
        self._stt: Any = None
        self._playback: Any = None
        self._queued_listen: _QueuedListen | None = None
        self._queued_listen_lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._tts is not None and self._stt is not None

    def start(self) -> dict:
        """Acquire the local voice session and warm both speech models."""
        with self._operation_lock:
            if self.ready:
                return {
                    **self.status(already_ready=True),
                    "preflight": self._last_preflight,
                }

            self._acquire_session_lock()
            started_at = time.monotonic()
            first_run = self._is_first_run()
            try:
                from voicebridge.audio.preflight import run_preflight

                self._last_preflight = run_preflight(
                    input_device=self.config.audio.input_device,
                    output_device=self.config.audio.output_device,
                    data_dir=self.data_dir,
                )

                # Keep heavy MLX imports out of MCP process startup. They are
                # first needed only when the user explicitly starts voice mode.
                from voicebridge.providers.registry import (
                    get_stt_provider,
                    get_tts_provider,
                )

                self._tts = get_tts_provider(self.config.tts).load()
                self._stt = get_stt_provider(self.config.stt).load()
                self._mark_onboarding_complete()
            except Exception as exc:
                self._release_locked()
                raise RuntimeError(
                    f"could not start local voice session: {exc}"
                ) from exc

            return {
                **self.status(first_run=first_run),
                "preflight": self._last_preflight,
                "load_ms": int((time.monotonic() - started_at) * 1000),
            }

    def speak(
        self,
        text: str,
        voice: str | None = None,
        listen_after: bool = False,
    ) -> dict:
        """Speak the host agent's exact text with no local rewriting."""
        spoken_text = text.strip()
        if not spoken_text:
            raise ValueError("voice_speak requires non-empty text")

        with self._operation_lock:
            self._ensure_started()
            with self._queued_listen_lock:
                if self._queued_listen is not None:
                    raise RuntimeError(
                        "voice_listen must collect the queued microphone capture "
                        "before voice_speak is called again"
                    )
            from voicebridge.audio.playback import play_async

            self._wait_for_playback()
            started_at = time.monotonic()
            audio = self._tts.synthesize(spoken_text, voice=voice)
            synthesis_ms = int((time.monotonic() - started_at) * 1000)
            self._playback = play_async(
                audio,
                self._tts.sample_rate,
                device=self.config.audio.output_device,
            )
            if listen_after:
                queued_listen = _QueuedListen(self._run_queued_capture)
                with self._queued_listen_lock:
                    self._queued_listen = queued_listen
                queued_listen.start()
            return {
                "spoken_text": spoken_text,
                "duration_ms": int(
                    (audio.shape[0] / self._tts.sample_rate) * 1000
                ),
                "synthesis_ms": synthesis_ms,
                "playback_started": self._playback is not None,
                "listen_queued": listen_after,
            }

    def listen(
        self,
        timeout_ms: int | None = None,
        silence_ms: int | None = None,
    ) -> dict:
        with self._queued_listen_lock:
            queued_listen = self._queued_listen
            self._queued_listen = None
        if queued_listen is not None:
            queued_capture = queued_listen.wait()
            with self._operation_lock:
                return {
                    **self._listen_locked(
                        None,
                        None,
                        queued_capture=queued_capture,
                    ),
                    "capture_queued": True,
                }

        with self._operation_lock:
            return self._listen_locked(timeout_ms, silence_ms)

    def stop(self) -> dict:
        with self._queued_listen_lock:
            queued_listen = self._queued_listen
            self._queued_listen = None
        if queued_listen is not None:
            try:
                queued_listen.wait()
            except Exception:
                pass

        with self._operation_lock:
            stopped = self.ready or self._session_lock_file is not None
            try:
                self._wait_for_playback()
            finally:
                self._release_locked()
            return {"stopped": stopped}

    def status(
        self,
        *,
        already_ready: bool = False,
        first_run: bool | None = None,
    ) -> dict:
        return {
            "version": __version__,
            "host": self.host,
            "first_run": self._is_first_run() if first_run is None else first_run,
            "ready": self.ready,
            "already_ready": already_ready,
            "backend": "mlx-audio",
            "capture": {
                "silence_ms": self.config.stt.silence_ms,
                "timeout_ms": self.config.stt.max_listen_ms,
            },
            "models": {
                "tts": self.config.tts.model if self._tts is not None else None,
                "stt": self.config.stt.model if self._stt is not None else None,
            },
        }

    def models(self) -> dict:
        from voicebridge.models import model_catalog

        return model_catalog(
            tts_provider=self.config.tts.provider,
            tts_model=self.config.tts.model,
            stt_provider=self.config.stt.provider,
            stt_model=self.config.stt.model,
        )

    def configure_models(self, tts: str, stt: str) -> dict:
        with self._operation_lock:
            if self.ready or self._session_lock_file is not None:
                raise RuntimeError(
                    "voice models cannot be changed during an active session; "
                    "call voice_stop first"
                )

            from voicebridge.models import get_model_option

            tts_option = get_model_option("tts", tts)
            stt_option = get_model_option("stt", stt)
            tts_config = TTSConfig(
                provider=tts_option["provider"],
                model=tts_option["model"],
                voice=tts_option["voice"],
                speed=self.config.tts.speed,
            )
            stt_config = STTConfig(
                provider=stt_option["provider"],
                model=stt_option["model"],
                silence_ms=self.config.stt.silence_ms,
                max_listen_ms=self.config.stt.max_listen_ms,
            )
            self.config = save_model_selection(tts_config, stt_config)
            return {
                "configured": True,
                "selection": {"tts": tts, "stt": stt},
                "models": {
                    "tts": self.config.tts.model,
                    "stt": self.config.stt.model,
                },
            }

    def _ensure_started(self) -> None:
        if not self.ready:
            self.start()

    def _wait_for_playback(self) -> None:
        playback = self._playback
        self._playback = None
        if playback is not None:
            playback.wait()

    def _run_queued_capture(self) -> _QueuedCapture:
        with self._operation_lock:
            self._ensure_started()
            self._wait_for_playback()
            from voicebridge.audio.capture import listen

            timeout_ms = self.config.stt.max_listen_ms
            silence_ms = self.config.stt.silence_ms
            started_at = time.monotonic()
            result = listen(
                self._stt.sample_rate,
                silence_ms=silence_ms,
                max_listen_ms=timeout_ms,
                input_device=self.config.audio.input_device,
                output_device=self.config.audio.output_device,
                start_chime=True,
                end_chime=False,
            )
            return _QueuedCapture(
                result=result,
                started_at=started_at,
                timeout_ms=timeout_ms,
                silence_ms=silence_ms,
            )

    def _listen_locked(
        self,
        timeout_ms: int | None,
        silence_ms: int | None,
        *,
        queued_capture: _QueuedCapture | None = None,
    ) -> dict:
        self._ensure_started()
        self._wait_for_playback()
        from voicebridge.audio.capture import listen
        from voicebridge.audio.playback import audio_lock, play_chime_end

        effective_timeout_ms = (
            queued_capture.timeout_ms
            if queued_capture is not None
            else timeout_ms
            if timeout_ms is not None
            else self.config.stt.max_listen_ms
        )
        effective_silence_ms = (
            queued_capture.silence_ms
            if queued_capture is not None
            else silence_ms
            if silence_ms is not None
            else self.config.stt.silence_ms
        )
        if effective_timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        if effective_silence_ms <= 0:
            raise ValueError("silence_ms must be positive")

        started_at = (
            queued_capture.started_at if queued_capture is not None else time.monotonic()
        )
        deadline = started_at + (effective_timeout_ms / 1000)
        first_attempt = True
        pending_result = queued_capture.result if queued_capture is not None else None
        transcript = ""
        transcription_s = 0.0
        discarded_empty_segments = 0
        speech_detected = False
        end_reason = "timeout"
        error = None

        try:
            while True:
                if pending_result is not None:
                    result = pending_result
                    pending_result = None
                else:
                    remaining_s = deadline - time.monotonic()
                    if remaining_s <= 0:
                        break
                    result = listen(
                        self._stt.sample_rate,
                        silence_ms=effective_silence_ms,
                        max_listen_ms=max(1, int(remaining_s * 1000)),
                        input_device=self.config.audio.input_device,
                        output_device=self.config.audio.output_device,
                        start_chime=first_attempt,
                        end_chime=False,
                    )
                first_attempt = False
                end_reason = result.end_reason
                error = result.error

                if result.end_reason == "device_error":
                    speech_detected = result.speech_detected
                    break

                if result.speech_detected and result.audio.size > 0:
                    transcription_started_at = time.monotonic()
                    candidate = self._stt.transcribe(result.audio).strip()
                    transcription_s += time.monotonic() - transcription_started_at
                    if candidate:
                        transcript = candidate
                        speech_detected = True
                        break
                    discarded_empty_segments += 1

                if result.end_reason != "silence":
                    break
        finally:
            try:
                with audio_lock:
                    play_chime_end(self.config.audio.output_device)
            except Exception as exc:
                end_reason = "device_error"
                error = error or str(exc)

        if discarded_empty_segments and not transcript and end_reason != "device_error":
            speech_detected = False
            end_reason = "timeout"

        return {
            "transcript": transcript,
            "duration_ms": int((time.monotonic() - started_at) * 1000),
            "transcription_ms": int(transcription_s * 1000),
            "speech_detected": speech_detected,
            "end_reason": end_reason,
            "error": error,
            "silence_ms": effective_silence_ms,
            "timeout_ms": effective_timeout_ms,
            "discarded_empty_segments": discarded_empty_segments,
            "capture_queued": False,
        }

    def _acquire_session_lock(self) -> None:
        if self._session_lock_file is not None:
            return

        SESSION_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock_file = SESSION_LOCK_PATH.open("a+")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            lock_file.close()
            raise VoiceSessionBusy(
                "another VoiceBridge session is already using this Mac's audio devices"
            ) from exc
        self._session_lock_file = lock_file

    def _is_first_run(self) -> bool:
        return not (self.data_dir / _ONBOARDING_MARKER).exists()

    def _mark_onboarding_complete(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / _ONBOARDING_MARKER).write_text(
            f"voicebridge {__version__}\n",
            encoding="utf-8",
        )

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
