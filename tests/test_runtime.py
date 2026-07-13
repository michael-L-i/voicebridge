import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import numpy as np

from voicebridge.config import Config
from voicebridge.mcp import runtime as runtime_module


class _FakeTTS:
    sample_rate = 24000

    def __init__(self):
        self.load_count = 0
        self.spoken = []

    def load(self):
        self.load_count += 1
        return self

    def synthesize(self, text, voice=None):
        self.spoken.append((text, voice))
        return np.ones(8, dtype=np.float32)


class _FakeSTT:
    sample_rate = 16000

    def __init__(self):
        self.load_count = 0

    def load(self):
        self.load_count += 1
        return self

    def transcribe(self, audio):
        return "heard"


def _fake_registry(tts, stt):
    module = ModuleType("voicebridge.providers.registry")
    module.get_tts_provider = lambda config: tts
    module.get_stt_provider = lambda config: stt
    return module


class VoiceRuntimeTests(unittest.TestCase):
    def test_models_are_reused_and_spoken_text_is_not_rewritten(self):
        tts = _FakeTTS()
        stt = _FakeSTT()
        registry = _fake_registry(tts, stt)

        with (
            tempfile.TemporaryDirectory() as data_dir,
            patch.object(runtime_module, "CONFIG_DIR", Path(data_dir)),
        ):
            runtime = runtime_module.VoiceRuntime(Config())
            with (
                patch.dict(
                    sys.modules, {"voicebridge.providers.registry": registry}
                ),
                patch("voicebridge.audio.playback.play") as play,
            ):
                first_start = runtime.start()
                second_start = runtime.start()
                spoken = runtime.speak("  Exactly this sentence.  ")
            stopped = runtime.stop()

        self.assertTrue(first_start["ready"])
        self.assertEqual(first_start["backend"], "mlx-audio")
        self.assertTrue(second_start["already_ready"])
        self.assertEqual(tts.load_count, 1)
        self.assertEqual(stt.load_count, 1)
        self.assertEqual(tts.spoken, [("Exactly this sentence.", None)])
        self.assertEqual(spoken["spoken_text"], "Exactly this sentence.")
        play.assert_called_once()
        self.assertTrue(stopped["stopped"])
        self.assertFalse(runtime.ready)

    def test_listen_uses_config_timing_unless_overridden(self):
        tts = _FakeTTS()
        stt = _FakeSTT()
        registry = _fake_registry(tts, stt)
        config = Config(stt={"silence_ms": 2000, "max_listen_ms": 30000})
        capture_result = SimpleNamespace(
            audio=np.zeros(0, dtype=np.float32),
            speech_detected=False,
            end_reason="timeout",
            error=None,
        )

        with (
            tempfile.TemporaryDirectory() as data_dir,
            patch.object(runtime_module, "CONFIG_DIR", Path(data_dir)),
            patch.dict(sys.modules, {"voicebridge.providers.registry": registry}),
            patch(
                "voicebridge.audio.capture.listen",
                return_value=capture_result,
            ) as listen,
        ):
            runtime = runtime_module.VoiceRuntime(config)
            configured = runtime.listen()
            overridden = runtime.listen(timeout_ms=12000, silence_ms=750)
        runtime.stop()

        self.assertEqual(configured["silence_ms"], 2000)
        self.assertEqual(configured["timeout_ms"], 30000)
        self.assertEqual(overridden["silence_ms"], 750)
        self.assertEqual(overridden["timeout_ms"], 12000)
        self.assertEqual(listen.call_args_list[0].kwargs["silence_ms"], 2000)
        self.assertEqual(listen.call_args_list[1].kwargs["silence_ms"], 750)

    def test_second_runtime_cannot_take_an_active_session(self):
        first_registry = _fake_registry(_FakeTTS(), _FakeSTT())
        second_registry = _fake_registry(_FakeTTS(), _FakeSTT())

        with (
            tempfile.TemporaryDirectory() as data_dir,
            patch.object(runtime_module, "CONFIG_DIR", Path(data_dir)),
        ):
            with patch.dict(
                sys.modules, {"voicebridge.providers.registry": first_registry}
            ):
                first = runtime_module.VoiceRuntime(Config())
                first.start()

            try:
                with patch.dict(
                    sys.modules, {"voicebridge.providers.registry": second_registry}
                ):
                    second = runtime_module.VoiceRuntime(Config())
                    with self.assertRaises(runtime_module.VoiceSessionBusy):
                        second.start()
            finally:
                first.stop()


if __name__ == "__main__":
    unittest.main()
