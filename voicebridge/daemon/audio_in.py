import queue

import numpy as np
import sounddevice as sd
import webrtcvad

from voicebridge.daemon.audio_out import audio_lock, play_chime_end, play_chime_start

# WebRTC VAD is a real frame classifier (trained on speech vs. non-speech),
# not an amplitude cutoff -- this is the single biggest factor in making
# listening feel reliable across different rooms/mics, ported from
# voicemode's approach after comparing against our original RMS-threshold
# implementation. 0-3, higher = stricter about filtering non-speech;
# 3 (voicemode's own default) works well for a normal room/office.
_VAD_AGGRESSIVENESS = 3
# WebRTC VAD only accepts exactly 10, 20, or 30ms frames.
_CHUNK_MS = 30
_MIN_LISTEN_MS = 500
# Read and discard this much audio right after opening the mic stream, before
# any VAD evaluation starts. Covers two things at once: audio device startup
# transients, and any tail-end echo/reverb still trailing in the room from
# voice_speak's just-finished playback -- sd.play(blocking=True) can return
# slightly before the sound has actually finished decaying acoustically, and
# without this settle window that tail gets misread as the user talking.
_SETTLE_MS = 300

_DEVICE_ERROR_MARKERS = (
    "device unavailable",
    "device disconnected",
    "invalid device",
    "unanticipated host error",
    "stream is stopped",
    "portaudio error",
)


def listen(
    sample_rate: int, silence_ms: int = 800, max_listen_ms: int = 30000
) -> tuple[np.ndarray, bool]:
    """Record from the mic until silence_ms of quiet follows some speech, or
    max_listen_ms elapses. Returns (mono float32 PCM at sample_rate, timed_out)
    -- timed_out is True iff max_listen_ms was hit without a natural
    speech-then-silence ending (including "never said anything" and a
    detected device error).

    Uses a callback-driven stream + queue rather than blocking stream.read():
    a blocking read can hang indefinitely on a device-level hiccup (observed
    in practice -- the Mac going to sleep mid-listen left a read call stuck
    for hours, wedging the whole daemon since nothing else could acquire
    audio_lock). Every queue.get() below is timeout-bounded, so this loop can
    never block longer than that timeout no matter what the hardware does.
    """
    chunk_samples = int(sample_rate * _CHUNK_MS / 1000)
    settle_chunks = max(1, int(_SETTLE_MS / _CHUNK_MS))
    min_chunks = max(1, int(_MIN_LISTEN_MS / _CHUNK_MS))
    silence_chunks_needed = max(1, int(silence_ms / _CHUNK_MS))
    max_chunks = max(1, int(max_listen_ms / _CHUNK_MS))

    vad = webrtcvad.Vad(_VAD_AGGRESSIVENESS)
    audio_queue: queue.Queue = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            status_str = str(status).lower()
            if any(marker in status_str for marker in _DEVICE_ERROR_MARKERS):
                audio_queue.put(None)  # sentinel: treat as a hard device error
                return
        audio_queue.put(indata[:, 0].copy())

    chunks = []
    consecutive_silence = 0
    has_spoken = False
    timed_out = True

    with audio_lock:
        play_chime_start()
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=chunk_samples,
            callback=callback,
        ):
            device_error = False

            for _ in range(settle_chunks):
                try:
                    block = audio_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                if block is None:
                    device_error = True
                    break

            if not device_error:
                for i in range(max_chunks):
                    try:
                        block = audio_queue.get(timeout=1.0)
                    except queue.Empty:
                        continue
                    if block is None:
                        break

                    chunks.append(block)
                    pcm16 = (np.clip(block, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
                    try:
                        is_speech = vad.is_speech(pcm16, sample_rate)
                    except Exception:
                        # Matches voicemode: treat a VAD hiccup as speech
                        # rather than silently discarding what was said.
                        is_speech = True

                    if not has_spoken:
                        if is_speech:
                            has_spoken = True
                            consecutive_silence = 0
                        # No timeout while waiting for speech to start --
                        # only max_chunks bounds this state, so a user
                        # gathering their thoughts before speaking doesn't
                        # get cut off.
                    else:
                        if is_speech:
                            consecutive_silence = 0
                        else:
                            consecutive_silence += 1
                        if i >= min_chunks and consecutive_silence >= silence_chunks_needed:
                            timed_out = False
                            break

        play_chime_end()

    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    return audio, timed_out
