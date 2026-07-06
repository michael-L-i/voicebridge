import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from voicebridge.config import load_config
from voicebridge.daemon.audio_in import listen
from voicebridge.daemon.audio_out import play
from voicebridge.daemon.state import SessionState
from voicebridge.daemon.summarizer import Summarizer, is_already_short
from voicebridge.providers.registry import get_stt_provider, get_tts_provider

_config = load_config()
_summarizer = Summarizer(_config.summarizer)
_tts = get_tts_provider(_config.tts)
_stt = get_stt_provider(_config.stt)
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load once at process startup so voice_speak/voice_listen calls never
    # pay model-load latency mid-conversation.
    _summarizer.load()
    _tts.load()
    _stt.load()
    yield


app = FastAPI(lifespan=lifespan)


class SpeakRequest(BaseModel):
    session_id: str
    text: str
    compress: bool = True
    voice: str | None = None


class SpeakResponse(BaseModel):
    spoken_text: str
    duration_ms: int


class ListenRequest(BaseModel):
    session_id: str
    timeout_ms: int | None = None
    silence_ms: int | None = None


class ListenResponse(BaseModel):
    transcript: str
    duration_ms: int
    timed_out: bool


@app.get("/health")
def health():
    return {
        "status": "ok",
        "models": {
            "summarizer": _config.summarizer.model,
            "tts": _config.tts.model,
            "stt": _config.stt.model,
        },
        "uptime_s": time.time() - _start_time,
    }


@app.post("/speak", response_model=SpeakResponse)
def speak(req: SpeakRequest):
    state = SessionState(req.session_id)

    t0 = time.time()
    if req.compress and not is_already_short(req.text):
        spoken_text = _summarizer.summarize(req.text, prior_summaries=state.prior_summaries)
    else:
        spoken_text = req.text.strip()

    audio = _tts.synthesize(spoken_text, voice=req.voice)
    play(audio, _tts.sample_rate)
    duration_ms = int((time.time() - t0) * 1000)

    state.record_summary(spoken_text, keep=_config.summarizer.context_window_summaries)

    return SpeakResponse(spoken_text=spoken_text, duration_ms=duration_ms)


@app.post("/listen", response_model=ListenResponse)
def listen_route(req: ListenRequest):
    t0 = time.time()
    audio, timed_out = listen(
        _stt.sample_rate,
        silence_ms=req.silence_ms or _config.stt.silence_ms,
        max_listen_ms=req.timeout_ms or _config.stt.max_listen_ms,
    )
    duration_ms = int((time.time() - t0) * 1000)

    transcript = _stt.transcribe(audio) if audio.size > 0 else ""
    return ListenResponse(transcript=transcript, duration_ms=duration_ms, timed_out=timed_out)


def main():
    uvicorn.run(app, host=_config.daemon.host, port=_config.daemon.port)


if __name__ == "__main__":
    main()
