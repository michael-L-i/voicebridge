import re

import numpy as np
from mlx_audio.tts.utils import load_model

from voicebridge.config import TTSConfig
from voicebridge.providers.base import TTSProvider
from voicebridge.providers.output import model_output_to_stderr

# mlx-audio's Kokoro vocoder has a reproducible shape-mismatch bug
# (`broadcast_shapes` in its ISTFT harmonic-source generator) that depends on
# the exact phoneme/duration sequence, not simply on text length: e.g. 30 and
# 40-word inputs succeed but 35 and 80 fail. It's deterministic per input, and
# splitting the text at a different word boundary reliably lands on a
# different (usually safe) frame count -- so on failure we bisect at the
# nearest space to the midpoint and retry each half recursively, rather than
# tuning a length threshold that wouldn't actually be safe.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_MAX_BISECT_DEPTH = 6


class KokoroTTSProvider(TTSProvider):
    sample_rate = 24000

    def __init__(self, config: TTSConfig):
        self.config = config
        self._model = None

    def load(self) -> "KokoroTTSProvider":
        if self._model is None:
            with model_output_to_stderr():
                self._model = load_model(self.config.model)
        return self

    def synthesize(self, text: str, voice: str | None = None) -> np.ndarray:
        self.load()
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]
        with model_output_to_stderr():
            chunks = []
            for sentence in sentences:
                chunks.extend(self._synthesize_resilient(sentence, voice, depth=0))
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks).astype(np.float32)

    def _synthesize_resilient(self, text: str, voice: str | None, depth: int) -> list[np.ndarray]:
        try:
            return [
                np.array(result.audio, copy=False)
                for result in self._model.generate(
                    text=text,
                    voice=voice or self.config.voice,
                    speed=self.config.speed,
                )
            ]
        except ValueError:
            words = text.split()
            if depth >= _MAX_BISECT_DEPTH or len(words) < 2:
                raise
            mid = len(words) // 2
            first_half = " ".join(words[:mid])
            second_half = " ".join(words[mid:])
            return self._synthesize_resilient(
                first_half, voice, depth + 1
            ) + self._synthesize_resilient(second_half, voice, depth + 1)
