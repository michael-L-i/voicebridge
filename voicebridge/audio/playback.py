import threading

import numpy as np
import sounddevice as sd

# One global lock covers both TTS playback and mic capture. Without echo
# cancellation, serializing them prevents VoiceBridge from hearing itself.
audio_lock = threading.Lock()

_CHIME_SAMPLE_RATE = 24000
_CHIME_TONE_S = 0.1
_CHIME_FADE_S = 0.01
_CHIME_TRAILING_SILENCE_S = 0.05


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
    tone_samples = int(_CHIME_SAMPLE_RATE * _CHIME_TONE_S)
    fade_samples = int(_CHIME_SAMPLE_RATE * _CHIME_FADE_S)
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)

    tones = []
    for freq in frequencies:
        t = np.linspace(0, _CHIME_TONE_S, tone_samples, endpoint=False)
        tone = (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        tone[:fade_samples] *= fade_in
        tone[-fade_samples:] *= fade_out
        tones.append(tone)

    trailing_silence = np.zeros(
        int(_CHIME_SAMPLE_RATE * _CHIME_TRAILING_SILENCE_S), dtype=np.float32
    )
    return np.concatenate(tones + [trailing_silence])


# A short audible cue marking exactly when listening starts/ends. Without
# this, whether the mic is actually on is invisible to the user -- a big
# part of why a voice interface stops feeling like a live conversation.
# Ascending tones for "now listening", descending for "done listening",
# matching the convention voicemode uses.
def play_chime_start(device: str | int | None = None) -> None:
    """Caller must already hold audio_lock -- this doesn't acquire it, so it
    can be sequenced immediately before mic capture within one lock hold."""
    sd.play(
        _generate_chime([800, 1000], device),
        samplerate=_CHIME_SAMPLE_RATE,
        blocking=True,
        device=_device_arg(device),
    )


def play_chime_end(device: str | int | None = None) -> None:
    """Caller must already hold audio_lock."""
    sd.play(
        _generate_chime([1000, 800], device),
        samplerate=_CHIME_SAMPLE_RATE,
        blocking=True,
        device=_device_arg(device),
    )
