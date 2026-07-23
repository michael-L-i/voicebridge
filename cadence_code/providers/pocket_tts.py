import numpy as np
from mlx_audio.tts.utils import load_model

from cadence_code.config import TTSConfig
from cadence_code.providers.base import TTSProvider
from cadence_code.providers.output import model_output_to_stderr


class PocketTTSProvider(TTSProvider):
    sample_rate = 24000

    def __init__(self, config: TTSConfig):
        self.config = config
        self._model = None

    def load(self) -> "PocketTTSProvider":
        if self._model is None:
            with model_output_to_stderr():
                self._model = load_model(self.config.model)
        return self

    def synthesize(self, text: str, voice: str | None = None) -> np.ndarray:
        self.load()
        with model_output_to_stderr():
            chunks = [
                np.array(result.audio, copy=False)
                for result in self._model.generate(
                    text=text,
                    voice=voice or self.config.voice,
                )
            ]
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks).astype(np.float32)
