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
from voicebridge.daemon.transcript import read_delta
from voicebridge.providers.registry import get_stt_provider, get_tts_provider

_config = load_config()
_summarizer = Summarizer(_config.summarizer)
_tts = get_tts_provider(_config.tts)
_stt = get_stt_provider(_config.stt)
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load once at process startup so hook calls never pay model-load latency.
    _summarizer.load()
    _tts.load()
    _stt.load()
    yield


app = FastAPI(lifespan=lifespan)


class NarrateRequest(BaseModel):
    session_id: str
    event: str
    transcript_path: str
    agent_id: str | None = None
    cwd: str | None = None


class NarrateResponse(BaseModel):
    spoken: bool
    spoken_text: str | None = None
    reason: str | None = None


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


@app.post("/narrate", response_model=NarrateResponse)
def narrate(req: NarrateRequest):
    if req.event == "Stop" and not _config.narration.narrate_stop:
        return NarrateResponse(spoken=False, reason="narrate_stop_disabled")
    if req.event == "SubagentStop" and not _config.narration.narrate_subagent_stop:
        return NarrateResponse(spoken=False, reason="narrate_subagent_stop_disabled")

    # Stop and SubagentStop transcripts are different files with independent
    # lifetimes (a subagent's transcript is one-shot, never revisited), so
    # each gets its own state key -- Stop reuses the plain session_id across
    # the whole session, SubagentStop gets a fresh key per agent_id.
    state_key = req.session_id if req.event == "Stop" else f"{req.session_id}:{req.agent_id}"
    state = SessionState(state_key)

    if req.event == "Stop" and state.voice_active:
        # An active /voice-code loop speaks explicitly via voice_speak;
        # an automatic narration here would talk over/duplicate that.
        return NarrateResponse(spoken=False, reason="voice_active")

    delta_text, new_offset = read_delta(req.transcript_path, state.last_offset)

    if not delta_text.strip():
        state.advance_offset_only(new_offset)
        return NarrateResponse(spoken=False, reason="empty_delta")
    if len(delta_text) < _config.narration.min_narrate_chars:
        state.advance_offset_only(new_offset)
        return NarrateResponse(spoken=False, reason="below_threshold")

    spoken_text = _summarizer.summarize(delta_text, prior_summaries=state.prior_summaries)
    audio = _tts.synthesize(spoken_text)
    play(audio, _tts.sample_rate)

    state.record_narration(new_offset, spoken_text, keep=_config.summarizer.context_window_summaries)

    return NarrateResponse(spoken=True, spoken_text=spoken_text)


@app.post("/speak", response_model=SpeakResponse)
def speak(req: SpeakRequest):
    state = SessionState(req.session_id)
    # An active voice_speak call is what /narrate's voice_active gate defers
    # to -- refresh the TTL here too, not just in /listen, so a conversation
    # made entirely of back-to-back voice_speak calls (no listens yet) still
    # suppresses the passive Stop-hook narration correctly.
    state.mark_voice_active()

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
    state = SessionState(req.session_id)
    # Listening implies an active voice conversation -- refresh the TTL so
    # /narrate's Stop-hook path defers to explicit voice_speak calls instead
    # of narrating over them (wired up fully once M4 adds voice_speak).
    state.mark_voice_active()

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
