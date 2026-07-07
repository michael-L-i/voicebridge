import threading

import numpy as np
import sounddevice as sd

# One global lock covers both playback and mic capture -- narration,
# voice_speak, and voice_listen all serialize through it. There's no real use
# case for speaking and listening at the same instant with no echo
# cancellation anyway, so this also solves "a SubagentStop narration fires
# mid voice_speak" for free: it just queues instead of talking over anyone.
audio_lock = threading.Lock()

_CHIME_SAMPLE_RATE = 24000
_CHIME_TONE_S = 0.1
_CHIME_FADE_S = 0.01
_CHIME_TRAILING_SILENCE_S = 0.15


def play(audio: np.ndarray, sample_rate: int) -> None:
    if audio.size == 0:
        return
    with audio_lock:
        sd.play(audio, samplerate=sample_rate, blocking=True)


def _chime_amplitude() -> float:
    """Quieter on built-in speakers, louder on Bluetooth -- ported from
    voicemode, which found Bluetooth output otherwise clips/misses the start
    of quiet sounds while the link wakes up."""
    try:
        default_output = sd.default.device[1]
        if default_output is None:
            return 0.075
        name = sd.query_devices()[default_output]["name"].lower()
        if "airpod" in name or "bluetooth" in name:
            return 0.15
        return 0.075
    except Exception:
        return 0.075


def _generate_chime(frequencies: list[float]) -> np.ndarray:
    amplitude = _chime_amplitude()
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
_CHIME_START = _generate_chime([800, 1000])
_CHIME_END = _generate_chime([1000, 800])


def play_chime_start() -> None:
    """Caller must already hold audio_lock -- this doesn't acquire it, so it
    can be sequenced immediately before mic capture within one lock hold."""
    sd.play(_CHIME_START, samplerate=_CHIME_SAMPLE_RATE, blocking=True)


def play_chime_end() -> None:
    """Caller must already hold audio_lock."""
    sd.play(_CHIME_END, samplerate=_CHIME_SAMPLE_RATE, blocking=True)
