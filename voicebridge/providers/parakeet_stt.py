import mlx.core as mx
import numpy as np
from mlx_audio.stt.utils import load_model

from voicebridge.config import STTConfig
from voicebridge.providers.base import STTProvider
from voicebridge.providers.output import model_output_to_stderr


class ParakeetSTTProvider(STTProvider):
    # Parakeet's native rate. mx.array inputs are NOT auto-resampled by
    # mlx-audio (only file-path inputs get that treatment) -- callers must
    # capture/provide audio at this rate directly.
    sample_rate = 16000

    def __init__(self, config: STTConfig):
        self.config = config
        self._model = None

    def load(self) -> "ParakeetSTTProvider":
        if self._model is None:
            with model_output_to_stderr():
                self._model = load_model(self.config.model)
        return self

    def transcribe(self, audio: np.ndarray) -> str:
        self.load()
        with model_output_to_stderr():
            result = self._model.generate(mx.array(audio.astype(np.float32)))
        return result.text.strip()
