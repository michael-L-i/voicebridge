from abc import ABC, abstractmethod

import numpy as np


class TTSProvider(ABC):
    sample_rate: int

    @abstractmethod
    def synthesize(self, text: str, voice: str | None = None) -> np.ndarray:
        """Return mono float32 PCM audio at self.sample_rate for the given text."""


class STTProvider(ABC):
    sample_rate: int

    @abstractmethod
    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe mono float32 PCM audio at self.sample_rate to text."""
