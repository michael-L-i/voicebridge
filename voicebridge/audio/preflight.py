import shutil
import threading
from pathlib import Path

import sounddevice as sd

from voicebridge.audio.playback import audio_lock

MIN_FREE_GB_RECOMMENDED = 10
_MIC_SAMPLE_RATE = 16000
_MIC_BLOCK_SAMPLES = 480
_MIC_CALLBACK_TIMEOUT_S = 3.0
_OUTPUT_SAMPLE_RATE = 24000
_DEVICE_ERROR_MARKERS = (
    "device unavailable",
    "device disconnected",
    "invalid device",
    "unanticipated host error",
    "stream is stopped",
    "portaudio error",
)


def _device_arg(device: str | int | None) -> str | int | None:
    return None if device in (None, "default") else device


def _device_details(
    configured: str | int | None,
    *,
    kind: str,
) -> dict:
    device = _device_arg(configured)
    details = sd.query_devices(device, kind=kind)
    if device is None:
        default_devices = sd.default.device
        index = default_devices[0 if kind == "input" else 1]
    else:
        index = configured
    if hasattr(index, "item"):
        index = index.item()
    return {
        "configured": configured if configured is not None else "default",
        "id": index,
        "name": details["name"],
    }


def run_preflight(
    *,
    input_device: str | int | None,
    output_device: str | int | None,
    data_dir: Path,
) -> dict:
    """Verify audio access before model setup without retaining mic audio."""
    data_dir.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(data_dir).free / (1024**3)
    warnings = []
    if free_gb < MIN_FREE_GB_RECOMMENDED:
        warnings.append(
            f"only {free_gb:.1f}GB free; first-run model downloads can total several GB"
        )

    input_arg = _device_arg(input_device)
    output_arg = _device_arg(output_device)
    input_details = _device_details(input_device, kind="input")
    output_details = _device_details(output_device, kind="output")
    sd.check_input_settings(
        device=input_arg,
        channels=1,
        dtype="float32",
        samplerate=_MIC_SAMPLE_RATE,
    )
    sd.check_output_settings(
        device=output_arg,
        channels=1,
        dtype="float32",
        samplerate=_OUTPUT_SAMPLE_RATE,
    )

    callback_received = threading.Event()
    callback_error: list[str] = []

    def callback(indata, frames, time_info, status):
        if status:
            status_text = str(status)
            if any(marker in status_text.lower() for marker in _DEVICE_ERROR_MARKERS):
                callback_error.append(status_text)
        # Intentionally retain no samples. This callback exists only to prove
        # that PortAudio and macOS microphone permission are working.
        callback_received.set()

    with audio_lock:
        with sd.InputStream(
            samplerate=_MIC_SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=_MIC_BLOCK_SAMPLES,
            callback=callback,
            device=input_arg,
        ):
            if not callback_received.wait(_MIC_CALLBACK_TIMEOUT_S):
                raise RuntimeError(
                    "microphone opened but did not deliver audio within 3 seconds"
                )

    if callback_error:
        raise RuntimeError(callback_error[0])

    return {
        "input_device": input_details,
        "output_device": output_details,
        "free_disk_gb": round(free_gb, 1),
        "warnings": warnings,
    }
