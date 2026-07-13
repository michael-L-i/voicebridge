import queue
import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

import numpy as np
import sounddevice as sd
import webrtcvad

from voicebridge.audio.playback import audio_lock, play_chime_end, play_chime_start

# WebRTC VAD only accepts exactly 10, 20, or 30 ms frames.
_VAD_AGGRESSIVENESS = 1
_CHUNK_MS = 30
_MIN_SPEECH_MS = 500
_PRE_ROLL_MS = 300
# PortAudio still needs a brief stabilization window after opening the input,
# but the start chime has already given the output device time to wake up.
_SETTLE_MS = 100
_SPEECH_START_CHUNKS = 2
_QUEUE_POLL_S = 0.1
_DEVICE_STALL_S = 2.0

_DEVICE_ERROR_MARKERS = (
    "device unavailable",
    "device disconnected",
    "invalid device",
    "unanticipated host error",
    "stream is stopped",
    "portaudio error",
)

EndReason = Literal["silence", "timeout", "device_error"]


@dataclass(frozen=True)
class ListenResult:
    audio: np.ndarray
    speech_detected: bool
    end_reason: EndReason
    error: str | None = None


@dataclass(frozen=True)
class _DeviceError:
    message: str


def _device_arg(device: str | int | None) -> str | int | None:
    return None if device in (None, "default") else device


def listen(
    sample_rate: int,
    silence_ms: int = 800,
    max_listen_ms: int = 30000,
    *,
    input_device: str | int | None = None,
    output_device: str | int | None = None,
) -> ListenResult:
    """Capture one utterance with silence endpointing and a rolling deadline.

    The returned end reason distinguishes a natural pause, the overall
    no-speech deadline, and an audio-device failure. The deadline is refreshed
    whenever speech is detected so it cannot cut off someone who is talking.
    """
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    if silence_ms <= 0:
        raise ValueError("silence_ms must be positive")
    if max_listen_ms <= 0:
        raise ValueError("max_listen_ms must be positive")

    chunk_samples = int(sample_rate * _CHUNK_MS / 1000)
    settle_chunks = max(1, round(_SETTLE_MS / _CHUNK_MS))
    min_speech_chunks = max(1, round(_MIN_SPEECH_MS / _CHUNK_MS))
    pre_roll_chunks = max(1, round(_PRE_ROLL_MS / _CHUNK_MS))
    silence_chunks_needed = max(1, round(silence_ms / _CHUNK_MS))

    vad = webrtcvad.Vad(_VAD_AGGRESSIVENESS)
    audio_queue: queue.Queue[np.ndarray | _DeviceError] = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            status_text = str(status)
            if any(marker in status_text.lower() for marker in _DEVICE_ERROR_MARKERS):
                audio_queue.put(_DeviceError(status_text))
                return
        audio_queue.put(indata[:, 0].copy())

    chunks: list[np.ndarray] = []
    pre_roll: deque[np.ndarray] = deque(maxlen=pre_roll_chunks)
    speech_detected = False
    consecutive_speech = 0
    consecutive_silence = 0
    captured_after_start = 0
    end_reason: EndReason = "timeout"
    error = None

    with audio_lock:
        chime_started = False
        try:
            play_chime_start(output_device)
            chime_started = True
            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocksize=chunk_samples,
                callback=callback,
                device=_device_arg(input_device),
            ):
                settled_chunks = 0
                settle_deadline = time.monotonic() + (_SETTLE_MS / 1000)
                while settled_chunks < settle_chunks and time.monotonic() < settle_deadline:
                    remaining = settle_deadline - time.monotonic()
                    try:
                        item = audio_queue.get(timeout=min(_QUEUE_POLL_S, remaining))
                    except queue.Empty:
                        continue
                    if isinstance(item, _DeviceError):
                        end_reason = "device_error"
                        error = item.message
                        break
                    settled_chunks += 1

                deadline = time.monotonic() + (max_listen_ms / 1000)
                last_audio_at = time.monotonic()
                while end_reason != "device_error" and time.monotonic() < deadline:
                    remaining = deadline - time.monotonic()
                    try:
                        item = audio_queue.get(timeout=min(_QUEUE_POLL_S, remaining))
                    except queue.Empty:
                        if time.monotonic() - last_audio_at >= _DEVICE_STALL_S:
                            end_reason = "device_error"
                            error = "audio input stopped delivering data"
                        continue
                    if isinstance(item, _DeviceError):
                        end_reason = "device_error"
                        error = item.message
                        break
                    last_audio_at = time.monotonic()

                    pcm16 = (np.clip(item, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
                    try:
                        is_speech = vad.is_speech(pcm16, sample_rate)
                    except Exception:
                        # Preserve audio on a classifier hiccup instead of
                        # silently dropping something the user may have said.
                        is_speech = True

                    if is_speech:
                        deadline = time.monotonic() + (max_listen_ms / 1000)

                    if not speech_detected:
                        pre_roll.append(item)
                        consecutive_speech = consecutive_speech + 1 if is_speech else 0
                        if consecutive_speech >= _SPEECH_START_CHUNKS:
                            speech_detected = True
                            chunks.extend(pre_roll)
                            pre_roll.clear()
                        continue

                    chunks.append(item)
                    captured_after_start += 1
                    consecutive_silence = 0 if is_speech else consecutive_silence + 1
                    if (
                        captured_after_start >= min_speech_chunks
                        and consecutive_silence >= silence_chunks_needed
                    ):
                        end_reason = "silence"
                        break
        except Exception as exc:
            end_reason = "device_error"
            error = str(exc)
        finally:
            if chime_started:
                try:
                    play_chime_end(output_device)
                except Exception as exc:
                    end_reason = "device_error"
                    error = error or str(exc)

    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    return ListenResult(
        audio=audio,
        speech_detected=speech_detected,
        end_reason=end_reason,
        error=error,
    )
