import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from voicebridge.audio import preflight


class _CallbackInputStream:
    def __init__(self, callback, *, callback_on_enter=True, error=None, **kwargs):
        self.callback = callback
        self.callback_on_enter = callback_on_enter
        self.error = error

    def __enter__(self):
        if self.error:
            raise self.error
        if self.callback_on_enter:
            self.callback(None, None, None, None)
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class AudioPreflightTests(unittest.TestCase):
    def test_checks_devices_opens_mic_and_warns_on_low_disk(self):
        def query_devices(device, kind):
            return {"name": "Studio Mic" if kind == "input" else "Studio Output"}

        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch.object(preflight.sd, "query_devices", side_effect=query_devices),
                patch.object(preflight.sd, "check_input_settings") as check_input,
                patch.object(preflight.sd, "check_output_settings") as check_output,
                patch.object(preflight.sd, "default", SimpleNamespace(device=(3, 4))),
                patch.object(
                    preflight.sd,
                    "InputStream",
                    lambda **kwargs: _CallbackInputStream(**kwargs),
                ),
                patch.object(
                    preflight.shutil,
                    "disk_usage",
                    return_value=SimpleNamespace(free=5 * 1024**3),
                ),
            ):
                result = preflight.run_preflight(
                    input_device="default",
                    output_device="default",
                    data_dir=Path(temporary),
                )

        self.assertEqual(result["input_device"]["id"], 3)
        self.assertEqual(result["output_device"]["id"], 4)
        self.assertEqual(result["free_disk_gb"], 5.0)
        self.assertEqual(len(result["warnings"]), 1)
        check_input.assert_called_once()
        check_output.assert_called_once()

    def test_callback_stall_fails_quickly(self):
        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch.object(
                    preflight.sd,
                    "query_devices",
                    return_value={"name": "Device"},
                ),
                patch.object(preflight.sd, "check_input_settings"),
                patch.object(preflight.sd, "check_output_settings"),
                patch.object(preflight.sd, "default", SimpleNamespace(device=(1, 2))),
                patch.object(
                    preflight.sd,
                    "InputStream",
                    lambda **kwargs: _CallbackInputStream(
                        callback_on_enter=False, **kwargs
                    ),
                ),
                patch.object(preflight, "_MIC_CALLBACK_TIMEOUT_S", 0.01),
                patch.object(
                    preflight.shutil,
                    "disk_usage",
                    return_value=SimpleNamespace(free=20 * 1024**3),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "did not deliver audio"):
                    preflight.run_preflight(
                        input_device="default",
                        output_device="default",
                        data_dir=Path(temporary),
                    )

    def test_microphone_open_error_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch.object(
                    preflight.sd,
                    "query_devices",
                    return_value={"name": "Device"},
                ),
                patch.object(preflight.sd, "check_input_settings"),
                patch.object(preflight.sd, "check_output_settings"),
                patch.object(preflight.sd, "default", SimpleNamespace(device=(1, 2))),
                patch.object(
                    preflight.sd,
                    "InputStream",
                    lambda **kwargs: _CallbackInputStream(
                        error=PermissionError("permission denied"), **kwargs
                    ),
                ),
                patch.object(
                    preflight.shutil,
                    "disk_usage",
                    return_value=SimpleNamespace(free=20 * 1024**3),
                ),
            ):
                with self.assertRaisesRegex(PermissionError, "permission denied"):
                    preflight.run_preflight(
                        input_device="default",
                        output_device="default",
                        data_dir=Path(temporary),
                    )


if __name__ == "__main__":
    unittest.main()
