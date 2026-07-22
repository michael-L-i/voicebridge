import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

try:
    import webrtcvad  # noqa: F401
except ImportError:
    sys.modules["webrtcvad"] = SimpleNamespace(Vad=lambda *args: None)

from voicebridge.audio import capture as capture_module
from voicebridge.audio import playback as playback_module
from voicebridge import config as config_module
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
    def setUp(self):
        # Runtime tests use fake providers and never load MLX. Avoid importing
        # the native extension during cleanup; repeated native registration can
        # abort an otherwise pure unit-test process on some MLX builds.
        self._mlx_core = SimpleNamespace(clear_cache=Mock())
        self._mlx = ModuleType("mlx")
        self._mlx.core = self._mlx_core
        self._mlx_patch = patch.dict(
            sys.modules,
            {"mlx": self._mlx, "mlx.core": self._mlx_core},
        )
        self._mlx_patch.start()

    def tearDown(self):
        self._mlx_patch.stop()

    def test_models_reports_catalog_without_loading_models(self):
        runtime = runtime_module.VoiceRuntime(Config())

        result = runtime.models()

        self.assertFalse(runtime.ready)
        self.assertEqual(result["defaults"], {"tts": "pocket", "stt": "parakeet-110m"})
        self.assertEqual(result["current"], result["defaults"])
        self.assertEqual(
            [item["id"] for item in result["tts"]],
            ["pocket", "kokoro", "chatterbox", "qwen"],
        )
        self.assertEqual(
            [item["id"] for item in result["stt"]],
            ["moonshine", "parakeet-110m", "parakeet"],
        )

    def test_configure_models_persists_selection_without_loading(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "config.toml"
            with (
                patch.object(config_module, "CONFIG_DIR", root),
                patch.object(config_module, "CONFIG_PATH", config_path),
            ):
                runtime = runtime_module.VoiceRuntime(
                    Config(
                        tts={"speed": 1.2},
                        stt={"silence_ms": 900, "max_listen_ms": 45000},
                    ),
                    data_dir=root,
                )
                result = runtime.configure_models("kokoro", "moonshine")
                persisted = config_module.load_config()

        self.assertFalse(runtime.ready)
        self.assertEqual(result["selection"], {"tts": "kokoro", "stt": "moonshine"})
        self.assertEqual(persisted.tts.provider, "kokoro")
        self.assertEqual(persisted.tts.voice, "af_heart")
        self.assertEqual(persisted.tts.speed, 1.2)
        self.assertEqual(persisted.stt.provider, "moonshine")
        self.assertEqual(persisted.stt.silence_ms, 900)
        self.assertEqual(persisted.stt.max_listen_ms, 45000)

    def test_configure_models_rejects_active_session(self):
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
                runtime = runtime_module.VoiceRuntime(Config(), data_dir=root / "data")
                runtime.start()
                try:
                    with self.assertRaisesRegex(RuntimeError, "voice_stop"):
                        runtime.configure_models("kokoro", "moonshine")
                finally:
                    runtime.stop()

    def test_speak_requires_explicit_start_without_session_side_effects(self):
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
                ) as preflight,
                patch.object(playback_module, "play_async") as play_async,
            ):
                runtime = runtime_module.VoiceRuntime(Config(), data_dir=root / "data")
                for text in ("Do not start implicitly.", "   "):
                    with self.subTest(text=text), self.assertRaisesRegex(
                        runtime_module.VoiceSessionNotStarted,
                        "voice session is not started; call voice_start first",
                    ):
                        runtime.speak(text)

            self.assertFalse((root / "session.lock").exists())
            self.assertFalse((root / "data" / "onboarding-v1.complete").exists())

        self.assertFalse(runtime.ready)
        preflight.assert_not_called()
        registry.get_tts_provider.assert_not_called()
        registry.get_stt_provider.assert_not_called()
        play_async.assert_not_called()

    def test_listen_requires_explicit_start_without_session_side_effects(self):
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
                ) as preflight,
                patch.object(capture_module, "listen") as listen,
            ):
                runtime = runtime_module.VoiceRuntime(Config(), data_dir=root / "data")
                with self.assertRaisesRegex(
                    runtime_module.VoiceSessionNotStarted,
                    "voice session is not started; call voice_start first",
                ):
                    runtime.listen()

            self.assertFalse((root / "session.lock").exists())
            self.assertFalse((root / "data" / "onboarding-v1.complete").exists())

        self.assertFalse(runtime.ready)
        preflight.assert_not_called()
        registry.get_tts_provider.assert_not_called()
        registry.get_stt_provider.assert_not_called()
        listen.assert_not_called()

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
                patch.object(playback_module, "play_async") as play_async,
            ):
                playback = Mock()
                play_async.return_value = playback
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
        self.assertEqual(first_start["capture"]["silence_ms"], 1000)
        self.assertEqual(first_start["capture"]["timeout_ms"], 30000)
        self.assertTrue(second_start["already_ready"])
        self.assertFalse(second_start["first_run"])
        self.assertFalse(status["first_run"])
        self.assertEqual(tts.load_count, 1)
        self.assertEqual(stt.load_count, 1)
        self.assertEqual(tts.spoken, [("Exactly this sentence.", None)])
        self.assertEqual(spoken["spoken_text"], "Exactly this sentence.")
        self.assertTrue(spoken["playback_started"])
        preflight.assert_called_once()
        play_async.assert_called_once()
        playback.wait.assert_called_once()
        self.assertTrue(stopped["stopped"])
        self.assertFalse(runtime.ready)
        self._mlx_core.clear_cache.assert_called_once()

    def test_listen_after_opens_mic_as_soon_as_playback_finishes(self):
        stt = _FakeSTT()
        transcribe_threads = []

        def transcribe(audio):
            transcribe_threads.append(threading.current_thread().name)
            return "heard"

        stt.transcribe = transcribe
        registry = _fake_registry(_FakeTTS(), stt)
        playback_waiting = threading.Event()
        playback_finished = threading.Event()
        capture_started = threading.Event()

        class _BlockingPlayback:
            def wait(self):
                playback_waiting.set()
                if not playback_finished.wait(timeout=1):
                    raise TimeoutError("test playback did not finish")

        capture_result = SimpleNamespace(
            audio=np.ones(8, dtype=np.float32),
            speech_detected=True,
            end_reason="silence",
            error=None,
        )

        def capture_listen(*args, **kwargs):
            capture_started.set()
            return capture_result

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
                patch.object(
                    playback_module,
                    "play_async",
                    return_value=_BlockingPlayback(),
                ),
                patch.object(capture_module, "listen", side_effect=capture_listen),
                patch.object(playback_module, "play_chime_end"),
            ):
                runtime = runtime_module.VoiceRuntime(Config(), data_dir=root / "data")
                runtime.start()
                spoken = runtime.speak("Your result is ready.", listen_after=True)

                self.assertTrue(playback_waiting.wait(timeout=1))
                self.assertFalse(capture_started.is_set())
                playback_finished.set()
                self.assertTrue(capture_started.wait(timeout=1))

                heard = runtime.listen()
                runtime.stop()

        self.assertTrue(spoken["listen_queued"])
        self.assertEqual(heard["transcript"], "heard")
        self.assertTrue(heard["capture_queued"])
        self.assertEqual(transcribe_threads, [threading.current_thread().name])

    def test_interrupt_cancels_queued_audio_and_captures_fresh_guidance(self):
        stt = _FakeSTT()
        registry = _fake_registry(_FakeTTS(), stt)
        playback_cancelled = threading.Event()
        capture_calls = []

        class _CancellablePlayback:
            def wait(self, timeout=None):
                if not playback_cancelled.wait(timeout=timeout or 1):
                    raise TimeoutError("test playback did not stop")

            def cancel(self):
                playback_cancelled.set()

        cancelled_capture = SimpleNamespace(
            audio=np.zeros(0, dtype=np.float32),
            speech_detected=False,
            end_reason="cancelled",
            error=None,
        )
        guidance_capture = SimpleNamespace(
            audio=np.ones(8, dtype=np.float32),
            speech_detected=True,
            end_reason="silence",
            error=None,
        )

        def capture_listen(*args, **kwargs):
            cancel_event = kwargs["cancel_event"]
            capture_calls.append(cancel_event)
            return cancelled_capture if cancel_event.is_set() else guidance_capture

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
                patch.object(
                    playback_module,
                    "play_async",
                    return_value=_CancellablePlayback(),
                ),
                patch.object(capture_module, "listen", side_effect=capture_listen),
                patch.object(playback_module, "play_chime_end"),
            ):
                runtime = runtime_module.VoiceRuntime(Config(), data_dir=root / "data")
                runtime.start()
                runtime.speak("Still talking.", listen_after=True)

                result = runtime.interrupt(timeout_ms=5000, silence_ms=750)
                ready_after_interrupt = runtime.ready
                runtime.stop()

        self.assertTrue(playback_cancelled.is_set())
        self.assertGreaterEqual(len(capture_calls), 2)
        self.assertTrue(capture_calls[0].is_set())
        self.assertFalse(capture_calls[-1].is_set())
        self.assertEqual(result["transcript"], "heard")
        self.assertTrue(result["interrupted"])
        self.assertTrue(ready_after_interrupt)

    def test_stop_preempts_active_capture_before_waiting_for_operation_lock(self):
        registry = _fake_registry(_FakeTTS(), _FakeSTT())
        capture_started = threading.Event()
        listen_result = {}

        def capture_listen(*args, **kwargs):
            capture_started.set()
            cancel_event = kwargs["cancel_event"]
            if not cancel_event.wait(timeout=1):
                raise TimeoutError("test capture was not cancelled")
            return SimpleNamespace(
                audio=np.zeros(0, dtype=np.float32),
                speech_detected=False,
                end_reason="cancelled",
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
                patch.object(capture_module, "listen", side_effect=capture_listen),
                patch.object(playback_module, "play_chime_end"),
            ):
                runtime = runtime_module.VoiceRuntime(Config(), data_dir=root / "data")
                runtime.start()
                listener = threading.Thread(
                    target=lambda: listen_result.update(runtime.listen()),
                    daemon=True,
                )
                listener.start()
                self.assertTrue(capture_started.wait(timeout=1))

                started_at = time.monotonic()
                stopped = runtime.stop()
                elapsed = time.monotonic() - started_at
                listener.join(timeout=1)

        self.assertFalse(listener.is_alive())
        self.assertLess(elapsed, 0.5)
        self.assertTrue(stopped["stopped"])
        self.assertEqual(listen_result["end_reason"], "cancelled")
        self.assertFalse(runtime.ready)

    def test_interrupt_requires_an_active_session(self):
        runtime = runtime_module.VoiceRuntime(Config())

        with self.assertRaisesRegex(RuntimeError, "start Voice Code first"):
            runtime.interrupt()

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
                patch.object(
                    capture_module, "listen", return_value=capture_result
                ) as listen,
                patch.object(playback_module, "play_chime_end"),
            ):
                runtime = runtime_module.VoiceRuntime(config, data_dir=root / "data")
                runtime.start()
                configured = runtime.listen()
                overridden = runtime.listen(timeout_ms=12000, silence_ms=750)
                runtime.stop()

        self.assertEqual(configured["silence_ms"], 2000)
        self.assertEqual(configured["timeout_ms"], 30000)
        self.assertEqual(overridden["silence_ms"], 750)
        self.assertEqual(overridden["timeout_ms"], 12000)
        self.assertEqual(listen.call_args_list[0].kwargs["silence_ms"], 2000)
        self.assertEqual(listen.call_args_list[1].kwargs["silence_ms"], 750)

    def test_empty_transcription_keeps_listening_for_real_speech(self):
        stt = _FakeSTT()
        stt.transcribe = Mock(side_effect=["   ", "stop"])
        registry = _fake_registry(_FakeTTS(), stt)
        empty_noise = SimpleNamespace(
            audio=np.ones(8, dtype=np.float32),
            speech_detected=True,
            end_reason="silence",
            error=None,
        )
        real_speech = SimpleNamespace(
            audio=np.ones(8, dtype=np.float32),
            speech_detected=True,
            end_reason="silence",
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
                patch.object(
                    capture_module,
                    "listen",
                    side_effect=[empty_noise, real_speech],
                ) as listen,
                patch.object(playback_module, "play_chime_end") as play_chime_end,
            ):
                runtime = runtime_module.VoiceRuntime(Config(), data_dir=root / "data")
                runtime.start()
                result = runtime.listen()
                runtime.stop()

        self.assertEqual(result["transcript"], "stop")
        self.assertTrue(result["speech_detected"])
        self.assertEqual(result["end_reason"], "silence")
        self.assertEqual(result["discarded_empty_segments"], 1)
        self.assertEqual(stt.transcribe.call_count, 2)
        self.assertEqual(listen.call_count, 2)
        self.assertTrue(listen.call_args_list[0].kwargs["start_chime"])
        self.assertFalse(listen.call_args_list[0].kwargs["end_chime"])
        self.assertFalse(listen.call_args_list[1].kwargs["start_chime"])
        self.assertFalse(listen.call_args_list[1].kwargs["end_chime"])
        play_chime_end.assert_called_once()

    def test_empty_transcription_then_no_speech_is_a_timeout(self):
        stt = _FakeSTT()
        stt.transcribe = Mock(return_value="")
        registry = _fake_registry(_FakeTTS(), stt)
        empty_noise = SimpleNamespace(
            audio=np.ones(8, dtype=np.float32),
            speech_detected=True,
            end_reason="silence",
            error=None,
        )
        no_speech = SimpleNamespace(
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
                patch.object(
                    capture_module,
                    "listen",
                    side_effect=[empty_noise, no_speech],
                ) as listen,
                patch.object(playback_module, "play_chime_end"),
            ):
                runtime = runtime_module.VoiceRuntime(Config(), data_dir=root / "data")
                runtime.start()
                result = runtime.listen()
                runtime.stop()

        self.assertEqual(result["transcript"], "")
        self.assertFalse(result["speech_detected"])
        self.assertEqual(result["end_reason"], "timeout")
        self.assertEqual(result["discarded_empty_segments"], 1)
        self.assertEqual(stt.transcribe.call_count, 1)
        self.assertEqual(listen.call_count, 2)

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
