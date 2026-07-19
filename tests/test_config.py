import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voicebridge import config as config_module


class ConfigMigrationTests(unittest.TestCase):
    def test_new_config_defaults_to_qwen_and_parakeet(self):
        with tempfile.TemporaryDirectory() as data_dir:
            config_path = Path(data_dir) / "config.toml"
            with (
                patch.object(config_module, "CONFIG_DIR", Path(data_dir)),
                patch.object(config_module, "CONFIG_PATH", config_path),
            ):
                loaded = config_module.load_config()

        self.assertEqual(loaded.tts.provider, "qwen")
        self.assertEqual(
            loaded.tts.model,
            "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit",
        )
        self.assertEqual(loaded.tts.voice, "Aiden")
        self.assertEqual(loaded.stt.provider, "parakeet")
        self.assertEqual(
            loaded.stt.model, "mlx-community/parakeet-tdt_ctc-110m"
        )

    def test_model_selection_preserves_existing_settings_and_unknown_sections(self):
        existing = """\
config_version = 2

[tts]
provider = "kokoro"
model = "custom-kokoro"
voice = "af_heart"
speed = 1.2

[stt]
provider = "parakeet"
model = "custom-parakeet"
silence_ms = 900
max_listen_ms = 45000

[narration]
enabled = true

[audio]
input_device = 2
output_device = "default"
"""

        with tempfile.TemporaryDirectory() as data_dir:
            config_path = Path(data_dir) / "config.toml"
            config_path.write_text(existing, encoding="utf-8")
            with (
                patch.object(config_module, "CONFIG_DIR", Path(data_dir)),
                patch.object(config_module, "CONFIG_PATH", config_path),
            ):
                saved = config_module.save_model_selection(
                    config_module.TTSConfig(
                        provider="qwen",
                        model="mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit",
                        voice="Aiden",
                        speed=1.2,
                    ),
                    config_module.STTConfig(
                        provider="whisper",
                        model="mlx-community/whisper-small.en-asr-fp16",
                        silence_ms=900,
                        max_listen_ms=45000,
                    ),
                )
                persisted = config_path.read_text(encoding="utf-8")

        self.assertEqual(saved.tts.provider, "qwen")
        self.assertEqual(saved.tts.voice, "Aiden")
        self.assertEqual(saved.tts.speed, 1.2)
        self.assertEqual(saved.stt.provider, "whisper")
        self.assertEqual(saved.stt.silence_ms, 900)
        self.assertEqual(saved.stt.max_listen_ms, 45000)
        self.assertEqual(saved.audio.input_device, 2)
        self.assertIn("[narration]\nenabled = true", persisted)

    def test_legacy_sections_are_removed_without_losing_voice_settings(self):
        old_config = """\
[daemon]
host = "127.0.0.1"
port = 8756

[summarizer]
model = "mlx-community/Qwen2.5-3B-Instruct-4bit"
max_tokens = 80

[tts]
provider = "kokoro"
model = "custom-kokoro"
voice = "af_heart"
speed = 1.2

[stt]
provider = "parakeet"
model = "custom-parakeet"
silence_ms = 900
max_listen_ms = 45000

[audio]
input_device = 2
output_device = "default"
"""

        with tempfile.TemporaryDirectory() as data_dir:
            config_path = Path(data_dir) / "config.toml"
            config_path.write_text(old_config, encoding="utf-8")
            with (
                patch.object(config_module, "CONFIG_DIR", Path(data_dir)),
                patch.object(config_module, "CONFIG_PATH", config_path),
            ):
                loaded = config_module.load_config()

            migrated = config_path.read_text(encoding="utf-8")

        self.assertNotIn("[daemon]", migrated)
        self.assertNotIn("[summarizer]", migrated)
        self.assertNotIn("Qwen", migrated)
        self.assertIn("config_version = 3", migrated)
        self.assertIn('model = "custom-kokoro"', migrated)
        self.assertIn('model = "custom-parakeet"', migrated)
        self.assertEqual(loaded.tts.model, "custom-kokoro")
        self.assertEqual(loaded.tts.speed, 1.2)
        self.assertEqual(loaded.stt.model, "custom-parakeet")
        self.assertEqual(loaded.stt.silence_ms, 900)
        self.assertEqual(loaded.audio.input_device, 2)

    def test_old_default_silence_is_updated_only_during_migration(self):
        old_config = """\
[stt]
silence_ms = 800
max_listen_ms = 30000
"""

        with tempfile.TemporaryDirectory() as data_dir:
            config_path = Path(data_dir) / "config.toml"
            config_path.write_text(old_config, encoding="utf-8")
            with (
                patch.object(config_module, "CONFIG_DIR", Path(data_dir)),
                patch.object(config_module, "CONFIG_PATH", config_path),
            ):
                first_load = config_module.load_config()
                migrated = config_path.read_text(encoding="utf-8")
                config_path.write_text(
                    migrated.replace("silence_ms = 1000", "silence_ms = 800"),
                    encoding="utf-8",
                )
                second_load = config_module.load_config()

        self.assertEqual(first_load.stt.silence_ms, 1000)
        self.assertEqual(second_load.stt.silence_ms, 800)

    def test_v2_default_silence_is_lowered_without_duplicating_version(self):
        old_config = """\
config_version = 2

[stt]
silence_ms = 2000
max_listen_ms = 30000
"""

        with tempfile.TemporaryDirectory() as data_dir:
            config_path = Path(data_dir) / "config.toml"
            config_path.write_text(old_config, encoding="utf-8")
            with (
                patch.object(config_module, "CONFIG_DIR", Path(data_dir)),
                patch.object(config_module, "CONFIG_PATH", config_path),
            ):
                loaded = config_module.load_config()
            migrated = config_path.read_text(encoding="utf-8")

        self.assertEqual(loaded.stt.silence_ms, 1000)
        self.assertEqual(migrated.count("config_version"), 1)
        self.assertIn("config_version = 3", migrated)

    def test_v2_customized_silence_survives_migration(self):
        old_config = """\
config_version = 2

[stt]
silence_ms = 2500
max_listen_ms = 30000
"""

        with tempfile.TemporaryDirectory() as data_dir:
            config_path = Path(data_dir) / "config.toml"
            config_path.write_text(old_config, encoding="utf-8")
            with (
                patch.object(config_module, "CONFIG_DIR", Path(data_dir)),
                patch.object(config_module, "CONFIG_PATH", config_path),
            ):
                loaded = config_module.load_config()
            migrated = config_path.read_text(encoding="utf-8")

        self.assertEqual(loaded.stt.silence_ms, 2500)
        self.assertIn("config_version = 3", migrated)


if __name__ == "__main__":
    unittest.main()
