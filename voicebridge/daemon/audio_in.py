import numpy as np
import sounddevice as sd

from voicebridge.daemon.audio_out import audio_lock

# A fixed RMS threshold is simple and good enough for a single-user local
# tool -- an adaptive/calibrated noise floor would be more robust but isn't
# worth the complexity yet.
_SILENCE_RMS_THRESHOLD = 0.01
_BLOCK_MS = 50
_MIN_LISTEN_MS = 300


def listen(
    sample_rate: int, silence_ms: int = 800, max_listen_ms: int = 30000
) -> tuple[np.ndarray, bool]:
    """Record from the mic until silence_ms of quiet follows some speech, or
    max_listen_ms elapses. Returns (mono float32 PCM at sample_rate, timed_out)
    -- timed_out is True iff max_listen_ms was hit without a natural
    speech-then-silence ending (including the "never said anything" case)."""
    block_samples = int(sample_rate * _BLOCK_MS / 1000)
    max_blocks = max(1, int(max_listen_ms / _BLOCK_MS))
    silence_blocks_needed = max(1, int(silence_ms / _BLOCK_MS))
    min_blocks = max(1, int(_MIN_LISTEN_MS / _BLOCK_MS))

    chunks = []
    consecutive_silence = 0
    has_spoken = False
    timed_out = True

    # Shares the lock with playback: never record and speak at once, and a
    # narration mid-listen just waits its turn instead of talking over you.
    with audio_lock:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
            for i in range(max_blocks):
                block, _overflowed = stream.read(block_samples)
                block = block[:, 0]
                chunks.append(block)

                rms = float(np.sqrt(np.mean(np.square(block))))
                if rms > _SILENCE_RMS_THRESHOLD:
                    has_spoken = True
                    consecutive_silence = 0
                else:
                    consecutive_silence += 1

                if has_spoken and i >= min_blocks and consecutive_silence >= silence_blocks_needed:
                    timed_out = False
                    break

    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    return audio, timed_out
