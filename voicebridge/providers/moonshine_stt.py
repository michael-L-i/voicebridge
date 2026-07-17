import numpy as np
from mlx_audio.stt.utils import load_model

from voicebridge.config import STTConfig
from voicebridge.providers.base import STTProvider


class MoonshineSTTProvider(STTProvider):
    sample_rate = 16000

    def __init__(self, config: STTConfig):
        self.config = config
        self._model = None

    def load(self) -> "MoonshineSTTProvider":
        if self._model is None:
            self._model = load_model(self.config.model)
        return self

    def transcribe(self, audio: np.ndarray) -> str:
        self.load()
        result = self._model.generate(audio.astype(np.float32))
        return result.text.strip()
