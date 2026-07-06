import numpy as np
from mlx_audio.stt.utils import load_model

from voicebridge.config import STTConfig
from voicebridge.providers.base import STTProvider


class WhisperSTTProvider(STTProvider):
    # Whisper's standard native rate. Unlike Parakeet, mlx-audio's Whisper
    # wrapper accepts a plain numpy array directly (no mx.array conversion
    # needed), but it's still on the caller to provide audio at this rate --
    # there's no automatic resampling for array inputs here either.
    sample_rate = 16000

    def __init__(self, config: STTConfig):
        self.config = config
        self._model = None

    def load(self) -> "WhisperSTTProvider":
        if self._model is None:
            self._model = load_model(self.config.model)
        return self

    def transcribe(self, audio: np.ndarray) -> str:
        self.load()
        result = self._model.generate(audio.astype(np.float32))
        return result.text.strip()
