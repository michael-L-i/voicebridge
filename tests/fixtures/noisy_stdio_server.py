from types import SimpleNamespace

import numpy as np

from cadence_code.config import STTConfig, TTSConfig
from cadence_code.mcp import server
from cadence_code.providers import registry


class _NoisyTTSModel:
    def __init__(self, provider: str):
        self.provider = provider

    def generate(self, **kwargs):
        print(f"NOISY {self.provider} inference")
        yield SimpleNamespace(audio=np.array([0.1], dtype=np.float32))


class _NoisySTTModel:
    def __init__(self, provider: str):
        self.provider = provider

    def generate(self, audio):
        print(f"NOISY {self.provider} inference")
        return SimpleNamespace(text="test transcript")


def _loader(provider: str, model_type):
    def load_model(model: str):
        print(f"NOISY {provider} load")
        return model_type(provider)

    return load_model


class _AllProvidersRuntime:
    def start(self, *, wait: bool = True) -> dict:
        assert wait
        invoked = []
        for name, provider_type in registry.TTS_PROVIDERS.items():
            module = __import__(provider_type.__module__, fromlist=["load_model"])
            module.load_model = _loader(name, _NoisyTTSModel)
            provider = provider_type(
                TTSConfig(provider=name, model=f"test/{name}", voice="default")
            )
            provider.load()
            provider.synthesize("Protocol test.")
            invoked.append(name)

        for name, provider_type in registry.STT_PROVIDERS.items():
            module = __import__(provider_type.__module__, fromlist=["load_model"])
            module.load_model = _loader(name, _NoisySTTModel)
            provider = provider_type(STTConfig(provider=name, model=f"test/{name}"))
            provider.load()
            provider.transcribe(np.zeros(8, dtype=np.float32))
            invoked.append(name)

        return {"invoked": invoked}

    def stop(self) -> dict:
        return {"stopped": True}


server.runtime = _AllProvidersRuntime()
server.main()
