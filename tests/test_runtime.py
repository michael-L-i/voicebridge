import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

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


class _FailingSTT(_FakeSTT):
    def load(self):
        raise RuntimeError("model unavailable")


def _fake_registry(tts, stt):
    module = ModuleType("voicebridge.providers.registry")
    module.get_tts_provider = Mock(return_value=tts)
    module.get_stt_provider = Mock(return_value=stt)
    return module


def _preflight_result():
    return {
        "input_device": {"id": 1, "name": "Mic"},
        "output_device": {"id": 2, "name": "Speakers"},
        "free_disk_gb": 42.0,
        "warnings": [],
    }


class VoiceRuntimeTests(unittest.TestCase):
    def test_models_are_reused_and_onboarding_completes_after_loading(self):
        tts = _FakeTTS()
        stt = _FakeSTT()
        registry = _fake_registry(tts, stt)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(
                    runtime_module, "SESSION_LOCK_PATH", root / "session.lock"
                ),
                patch.dict(os.environ, {"VOICEBRIDGE_HOST": "codex"}),
                patch.dict(sys.modules, {"voicebridge.providers.registry": registry}),
                patch(
                    "voicebridge.audio.preflight.run_preflight",
                    return_value=_preflight_result(),
                ) as preflight,
                patch("voicebridge.audio.playback.play") as play,
            ):
                runtime = runtime_module.VoiceRuntime(Config(), data_dir=root / "codex")
                first_start = runtime.start()
                second_start = runtime.start()
                spoken = runtime.speak("  Exactly this sentence.  ")
                status = runtime.status()
                stopped = runtime.stop()

            marker = root / "codex" / "onboarding-v1.complete"
            self.assertTrue(marker.exists())

        self.assertTrue(first_start["ready"])
        self.assertTrue(first_start["first_run"])
        self.assertEqual(first_start["host"], "codex")
        self.assertEqual(first_start["preflight"], _preflight_result())
        self.assertRegex(first_start["version"], r"^(?:\d+\.\d+\.\d+|development)$")
        self.assertEqual(first_start["backend"], "mlx-audio")
        self.assertEqual(first_start["capture"]["silence_ms"], 2000)
        self.assertEqual(first_start["capture"]["timeout_ms"], 30000)
        self.assertTrue(second_start["already_ready"])
        self.assertFalse(second_start["first_run"])
        self.assertFalse(status["first_run"])
        self.assertEqual(tts.load_count, 1)
        self.assertEqual(stt.load_count, 1)
        self.assertEqual(tts.spoken, [("Exactly this sentence.", None)])
        self.assertEqual(spoken["spoken_text"], "Exactly this sentence.")
        preflight.assert_called_once()
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

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(
                    runtime_module, "SESSION_LOCK_PATH", root / "session.lock"
                ),
                patch.dict(sys.modules, {"voicebridge.providers.registry": registry}),
                patch(
                    "voicebridge.audio.preflight.run_preflight",
                    return_value=_preflight_result(),
                ),
                patch(
                    "voicebridge.audio.capture.listen",
                    return_value=capture_result,
                ) as listen,
            ):
                runtime = runtime_module.VoiceRuntime(config, data_dir=root / "data")
                configured = runtime.listen()
                overridden = runtime.listen(timeout_ms=12000, silence_ms=750)
                runtime.stop()

        self.assertEqual(configured["silence_ms"], 2000)
        self.assertEqual(configured["timeout_ms"], 30000)
        self.assertEqual(overridden["silence_ms"], 750)
        self.assertEqual(overridden["timeout_ms"], 12000)
        self.assertEqual(listen.call_args_list[0].kwargs["silence_ms"], 2000)
        self.assertEqual(listen.call_args_list[1].kwargs["silence_ms"], 750)

    def test_different_hosts_and_data_dirs_share_one_session_lock(self):
        registry = _fake_registry(_FakeTTS(), _FakeSTT())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(
                    runtime_module, "SESSION_LOCK_PATH", root / "session.lock"
                ),
                patch.dict(sys.modules, {"voicebridge.providers.registry": registry}),
                patch(
                    "voicebridge.audio.preflight.run_preflight",
                    return_value=_preflight_result(),
                ),
            ):
                with patch.dict(os.environ, {"VOICEBRIDGE_HOST": "codex"}):
                    first = runtime_module.VoiceRuntime(
                        Config(), data_dir=root / "codex-data"
                    )
                with patch.dict(os.environ, {"VOICEBRIDGE_HOST": "claude-code"}):
                    second = runtime_module.VoiceRuntime(
                        Config(), data_dir=root / "claude-data"
                    )

                first.start()
                try:
                    with self.assertRaises(runtime_module.VoiceSessionBusy):
                        second.start()
                finally:
                    first.stop()

        self.assertEqual(first.host, "codex")
        self.assertEqual(second.host, "claude-code")

    def test_preflight_failure_happens_before_models_and_releases_lock(self):
        registry = _fake_registry(_FakeTTS(), _FakeSTT())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(
                    runtime_module, "SESSION_LOCK_PATH", root / "session.lock"
                ),
                patch.dict(sys.modules, {"voicebridge.providers.registry": registry}),
                patch(
                    "voicebridge.audio.preflight.run_preflight",
                    side_effect=PermissionError("microphone permission denied"),
                ),
            ):
                runtime = runtime_module.VoiceRuntime(
                    Config(), data_dir=root / "failed"
                )
                with self.assertRaisesRegex(
                    RuntimeError, "microphone permission denied"
                ):
                    runtime.start()

            self.assertFalse((root / "failed" / "onboarding-v1.complete").exists())
            registry.get_tts_provider.assert_not_called()
            registry.get_stt_provider.assert_not_called()

            good_registry = _fake_registry(_FakeTTS(), _FakeSTT())
            with (
                patch.object(
                    runtime_module, "SESSION_LOCK_PATH", root / "session.lock"
                ),
                patch.dict(
                    sys.modules, {"voicebridge.providers.registry": good_registry}
                ),
                patch(
                    "voicebridge.audio.preflight.run_preflight",
                    return_value=_preflight_result(),
                ),
            ):
                retry = runtime_module.VoiceRuntime(Config(), data_dir=root / "retry")
                self.assertTrue(retry.start()["ready"])
                retry.stop()

    def test_model_failure_does_not_complete_onboarding(self):
        registry = _fake_registry(_FakeTTS(), _FailingSTT())

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (
                patch.object(
                    runtime_module, "SESSION_LOCK_PATH", root / "session.lock"
                ),
                patch.dict(sys.modules, {"voicebridge.providers.registry": registry}),
                patch(
                    "voicebridge.audio.preflight.run_preflight",
                    return_value=_preflight_result(),
                ),
            ):
                runtime = runtime_module.VoiceRuntime(Config(), data_dir=root / "data")
                with self.assertRaisesRegex(RuntimeError, "model unavailable"):
                    runtime.start()

            self.assertFalse((root / "data" / "onboarding-v1.complete").exists())
            self.assertFalse(runtime.ready)


if __name__ == "__main__":
    unittest.main()
