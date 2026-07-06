import numpy as np
import sounddevice as sd

from voicebridge.daemon.audio_out import audio_lock

_BLOCK_MS = 50
_MIN_LISTEN_MS = 500
# Read and discard this much audio right after opening the mic stream, before
# any VAD evaluation starts. Covers two things at once: audio device startup
# transients, and any tail-end echo/reverb still trailing in the room from
# voice_speak's just-finished playback -- sd.play(blocking=True) can return
# slightly before the sound has actually finished decaying acoustically,
# and without this settle window that tail gets misread as the user talking.
_SETTLE_MS = 300
# The speech-vs-silence threshold is calibrated from the settle window's
# ambient noise level instead of a fixed constant, so the same code works
# across different mics/rooms instead of only whatever level was assumed at
# write time. Median (not mean) so one loud transient during settling
# doesn't skew the whole calibration.
_THRESHOLD_MULTIPLIER = 3.0
_MIN_THRESHOLD = 0.008
_MAX_THRESHOLD = 0.05


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
    settle_blocks = max(1, int(_SETTLE_MS / _BLOCK_MS))

    chunks = []
    consecutive_silence = 0
    has_spoken = False
    timed_out = True

    # Shares the lock with playback: never record and speak at once, and a
    # narration mid-listen just waits its turn instead of talking over you.
    with audio_lock:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
            settle_rms = []
            for _ in range(settle_blocks):
                block, _overflowed = stream.read(block_samples)
                settle_rms.append(float(np.sqrt(np.mean(np.square(block[:, 0])))))

            ambient = sorted(settle_rms)[len(settle_rms) // 2] if settle_rms else 0.0
            threshold = min(_MAX_THRESHOLD, max(_MIN_THRESHOLD, ambient * _THRESHOLD_MULTIPLIER))

            for i in range(max_blocks):
                block, _overflowed = stream.read(block_samples)
                block = block[:, 0]
                chunks.append(block)

                rms = float(np.sqrt(np.mean(np.square(block))))
                if rms > threshold:
                    has_spoken = True
                    consecutive_silence = 0
                else:
                    consecutive_silence += 1

                if has_spoken and i >= min_blocks and consecutive_silence >= silence_blocks_needed:
                    timed_out = False
                    break

    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    return audio, timed_out
