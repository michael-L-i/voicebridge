import threading

import numpy as np
import sounddevice as sd

# One global lock covers both playback and (later) mic capture -- narration,
# voice_speak, and voice_listen all serialize through it. There's no real use
# case for speaking and listening at the same instant with no echo
# cancellation anyway, so this also solves "a SubagentStop narration fires
# mid voice_speak" for free: it just queues instead of talking over anyone.
audio_lock = threading.Lock()


def play(audio: np.ndarray, sample_rate: int) -> None:
    if audio.size == 0:
        return
    with audio_lock:
        sd.play(audio, samplerate=sample_rate, blocking=True)
