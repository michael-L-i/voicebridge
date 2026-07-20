import unittest

from voicebridge.models import (
    DEFAULT_STT_MODEL,
    DEFAULT_TTS_MODEL,
    STT_MODELS,
    TTS_MODELS,
    get_model_option,
    model_catalog,
)


class ModelCatalogTests(unittest.TestCase):
    def test_options_are_ordered_from_lightest_to_heaviest(self):
        self.assertEqual(
            [item["id"] for item in TTS_MODELS],
            ["pocket", "kokoro", "chatterbox", "qwen"],
        )
        self.assertEqual(
            [item["id"] for item in STT_MODELS],
            ["moonshine", "parakeet-110m", "parakeet"],
        )
        self.assertEqual(
            [item["download_mb"] for item in TTS_MODELS],
            sorted(item["download_mb"] for item in TTS_MODELS),
        )
        self.assertEqual(
            [item["download_mb"] for item in STT_MODELS],
            sorted(item["download_mb"] for item in STT_MODELS),
        )

    def test_defaults_and_current_selection_are_reported(self):
        catalog = model_catalog(
            tts_provider="pocket",
            tts_model="mlx-community/pocket-tts",
            stt_provider="parakeet",
            stt_model="mlx-community/parakeet-tdt_ctc-110m",
        )

        self.assertEqual(DEFAULT_TTS_MODEL, "pocket")
        self.assertEqual(DEFAULT_STT_MODEL, "parakeet-110m")
        self.assertEqual(
            catalog["defaults"], {"tts": "pocket", "stt": "parakeet-110m"}
        )
        self.assertEqual(catalog["current"], catalog["defaults"])
        self.assertTrue(
            next(item for item in catalog["tts"] if item["id"] == "pocket")[
                "default"
            ]
        )
        self.assertTrue(
            next(item for item in catalog["stt"] if item["id"] == "parakeet-110m")[
                "default"
            ]
        )

    def test_unknown_selection_lists_available_ids(self):
        with self.assertRaisesRegex(ValueError, "Available.*kokoro.*qwen"):
            get_model_option("tts", "missing")


if __name__ == "__main__":
    unittest.main()
