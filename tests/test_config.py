import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voicebridge import config as config_module


class ConfigMigrationTests(unittest.TestCase):
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
        self.assertIn("config_version = 2", migrated)
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
                    migrated.replace("silence_ms = 2000", "silence_ms = 800"),
                    encoding="utf-8",
                )
                second_load = config_module.load_config()

        self.assertEqual(first_load.stt.silence_ms, 2000)
        self.assertEqual(second_load.stt.silence_ms, 800)


if __name__ == "__main__":
    unittest.main()
