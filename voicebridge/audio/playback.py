import threading

import numpy as np
import sounddevice as sd

# One global lock covers both TTS playback and mic capture. Without echo
# cancellation, serializing them prevents VoiceBridge from hearing itself.
audio_lock = threading.Lock()

_CHIME_SAMPLE_RATE = 24000
# Each note rings out with a fast attack and an exponential decay, like a soft
# mallet strike; the second note starts while the first is still ringing.
_CHIME_NOTE_S = 0.16
_CHIME_NOTE_SPACING_S = 0.07
_CHIME_ATTACK_S = 0.005
_CHIME_DECAY_RATE = 18.0
_CHIME_OVERTONE_LEVEL = 0.35
_CHIME_TRAILING_SILENCE_S = 0.05


class PlaybackHandle:
    def __init__(
        self,
        audio: np.ndarray,
        sample_rate: int,
        device: str | int | None,
    ) -> None:
        self._started = threading.Event()
        self._error: Exception | None = None
        self._thread = threading.Thread(
            target=self._run,
            args=(audio, sample_rate, device),
            name="voicebridge-playback",
            daemon=True,
        )
        self._thread.start()
        self._started.wait()
        if self._error is not None:
            raise self._error

    def _run(
        self,
        audio: np.ndarray,
        sample_rate: int,
        device: str | int | None,
    ) -> None:
        try:
            with audio_lock:
                sd.play(
                    audio,
                    samplerate=sample_rate,
                    blocking=False,
                    device=_device_arg(device),
                )
                self._started.set()
                sd.wait()
        except Exception as exc:
            self._error = exc
            self._started.set()

    def wait(self) -> None:
        self._thread.join()
        if self._error is not None:
            raise self._error


def _device_arg(device: str | int | None) -> str | int | None:
    return None if device in (None, "default") else device


def play(
    audio: np.ndarray, sample_rate: int, device: str | int | None = None
) -> None:
    if audio.size == 0:
        return
    with audio_lock:
        sd.play(
            audio,
            samplerate=sample_rate,
            blocking=True,
            device=_device_arg(device),
        )


def play_async(
    audio: np.ndarray,
    sample_rate: int,
    device: str | int | None = None,
) -> PlaybackHandle | None:
    """Start playback and return once the audio device accepts it."""
    if audio.size == 0:
        return None
    return PlaybackHandle(audio, sample_rate, device)


def _chime_amplitude(device: str | int | None) -> float:
    """Quieter on built-in speakers, louder on Bluetooth -- ported from
    voicemode, which found Bluetooth output otherwise clips/misses the start
    of quiet sounds while the link wakes up."""
    try:
        info = sd.query_devices(_device_arg(device), "output")
        name = info["name"].lower()
        if "airpod" in name or "bluetooth" in name:
            return 0.15
        return 0.075
    except Exception:
        return 0.075


def _generate_chime(
    frequencies: list[float], device: str | int | None
) -> np.ndarray:
    amplitude = _chime_amplitude(device)
    note_samples = int(_CHIME_SAMPLE_RATE * _CHIME_NOTE_S)
    spacing_samples = int(_CHIME_SAMPLE_RATE * _CHIME_NOTE_SPACING_S)
    attack_samples = max(1, int(_CHIME_SAMPLE_RATE * _CHIME_ATTACK_S))
    tail_samples = int(_CHIME_SAMPLE_RATE * _CHIME_TRAILING_SILENCE_S)
    chime = np.zeros(
        spacing_samples * (len(frequencies) - 1) + note_samples + tail_samples,
        dtype=np.float32,
    )

    t = np.linspace(0, _CHIME_NOTE_S, note_samples, endpoint=False)
    envelope = np.exp(-t * _CHIME_DECAY_RATE)
    envelope[:attack_samples] *= np.linspace(0, 1, attack_samples)
    for index, freq in enumerate(frequencies):
        note = np.sin(2 * np.pi * freq * t)
        note += _CHIME_OVERTONE_LEVEL * np.sin(2 * np.pi * 2 * freq * t)
        offset = index * spacing_samples
        chime[offset : offset + note_samples] += (note * envelope).astype(
            np.float32
        )

    peak = np.max(np.abs(chime))
    if peak > 0:
        chime *= amplitude / peak
    return chime


# A short audible cue marking exactly when listening starts/ends. Without
# this, whether the mic is actually on is invisible to the user -- a big
# part of why a voice interface stops feeling like a live conversation.
# Two soft mallet-like notes a fifth apart: rising for "now listening",
# falling for "done listening".
def play_chime_start(device: str | int | None = None) -> None:
    """Caller must already hold audio_lock -- this doesn't acquire it, so it
    can be sequenced immediately before mic capture within one lock hold."""
    sd.play(
        _generate_chime([659.26, 987.77], device),
        samplerate=_CHIME_SAMPLE_RATE,
        blocking=True,
        device=_device_arg(device),
    )


def play_chime_end(device: str | int | None = None) -> None:
    """Caller must already hold audio_lock."""
    sd.play(
        _generate_chime([987.77, 659.26], device),
        samplerate=_CHIME_SAMPLE_RATE,
        blocking=True,
        device=_device_arg(device),
    )
