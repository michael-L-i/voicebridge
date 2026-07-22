import importlib.metadata
import unittest
from unittest.mock import patch

import spacy
from mlx_audio.tts.models.kokoro.pipeline import KokoroPipeline


class KokoroFrontendTests(unittest.TestCase):
    def test_english_pipeline_is_preinstalled_without_runtime_download(self):
        self.assertEqual(importlib.metadata.version("en-core-web-sm"), "3.8.0")
        self.assertTrue(spacy.util.is_package("en_core_web_sm"))

        with patch(
            "spacy.cli.download",
            side_effect=AssertionError("Kokoro attempted a runtime install"),
        ) as download:
            pipeline = KokoroPipeline(lang_code="a", model=False, repo_id="unused")

        download.assert_not_called()
        self.assertEqual(pipeline.g2p.nlp.meta["name"], "core_web_sm")


if __name__ == "__main__":
    unittest.main()
