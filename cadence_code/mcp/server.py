from mcp.server.fastmcp import FastMCP

from cadence_code.mcp.runtime import VoiceRuntime, VoiceSessionNotStarted

mcp = FastMCP(
    "cadence-code",
    instructions=(
        "Local speech input and output for explicit Cadence Code conversations. "
        "Model configuration tools may be used during explicit Cadence Code setup. "
        "Only call audio tools after the user explicitly asks to start or continue "
        "a Cadence Code voice conversation."
    ),
)
runtime = VoiceRuntime()


def _error(exc: Exception) -> dict:
    result = {"ok": False, "error": str(exc)}
    if isinstance(exc, VoiceSessionNotStarted):
        result["error_code"] = exc.error_code
    return result


@mcp.tool()
def voice_models() -> dict:
    """List local TTS and STT choices from lightest to heaviest.

    Returns stable selection IDs, resource tiers, download sizes, defaults, and
    the current configured pair. This tool does not download or load a model."""
    return {"ok": True, **runtime.models()}


@mcp.tool()
def voice_configure(tts: str, stt: str) -> dict:
    """Persist a TTS and STT selection before voice_start.

    Use IDs returned by voice_models. Existing audio and capture settings are
    preserved. Models cannot be changed during an active voice conversation."""
    try:
        return {"ok": True, **runtime.configure_models(tts, stt)}
    except Exception as exc:
        return _error(exc)


@mcp.tool()
def voice_start(wait: bool = False) -> dict:
    """Start a local voice conversation and load the TTS and STT models.

    Call only after an explicit user request for a Cadence Code conversation,
    once before the first voice_speak. Returns immediately by default and loads
    the models in the background: poll voice_status until ready is true, or
    until start_error is set. This keeps a first-run model download from
    outliving any host's MCP tool deadline. Later turns reuse the warm models
    and return ready at once. Set wait true only to block until loading
    finishes. Only one conversation can be active per Mac."""
    try:
        return {"ok": True, **runtime.start(wait=wait)}
    except Exception as exc:
        return _error(exc)


@mcp.tool()
def voice_speak(
    text: str,
    voice: str | None = None,
    listen_after: bool = False,
) -> dict:
    """Speak the host agent's exact text aloud through local TTS.

    Keep text to 1-3 short conversational sentences. Do not include code,
    bullet lists, or file paths. The text is spoken verbatim and is never
    summarized or rewritten locally. Returns once playback starts so the host
    can stream its written response while speech continues. Set listen_after
    when this speech ends a turn: Cadence Code will open the mic immediately
    after playback, and the subsequent voice_listen call collects that queued
    capture instead of starting late. Leave it false for progress updates that
    are followed by work rather than a user reply. Requires a successful
    voice_start; this tool never starts a session or loads models implicitly."""
    try:
        return {
            "ok": True,
            **runtime.speak(text, voice=voice, listen_after=listen_after),
        }
    except Exception as exc:
        return _error(exc)


@mcp.tool()
def voice_listen(
    timeout_ms: int | None = None,
    silence_ms: int | None = None,
) -> dict:
    """Listen via microphone and return the user's transcribed instruction.

    Capture ends after the configured pause (one second by default) or overall
    timeout. If the preceding voice_speak queued capture, this collects that
    already-running listen and its configured timing; otherwise optional
    arguments override config for this call. Noise segments that transcribe to
    no words are discarded while the original timeout remains. Check
    speech_detected and end_reason; a timeout may still contain valid speech.
    Playback and recording are serialized because there is no echo
    cancellation. Requires a successful voice_start; this tool never starts a
    session or loads models implicitly."""
    try:
        return {"ok": True, **runtime.listen(timeout_ms, silence_ms)}
    except Exception as exc:
        return _error(exc)


@mcp.tool()
def voice_interrupt(
    timeout_ms: int | None = None,
    silence_ms: int | None = None,
) -> dict:
    """Interrupt current Cadence Code audio and capture added guidance.

    Use after the user interrupts the host's current turn. Any active speech or
    queued microphone capture is cancelled, the warmed models remain loaded,
    and one fresh microphone capture is returned as guidance for continuing or
    redirecting the interrupted task."""
    try:
        return {"ok": True, **runtime.interrupt(timeout_ms, silence_ms)}
    except Exception as exc:
        return _error(exc)


@mcp.tool()
def voice_stop(wait_for_speech: bool = False) -> dict:
    """End voice mode and release its local TTS and STT model memory.

    Set wait_for_speech after starting a short final voice_speak with
    listen_after false. The goodbye is allowed to finish before the models are
    released. Leave it false when stopping should silence audio immediately."""
    try:
        return {"ok": True, **runtime.stop(wait_for_speech=wait_for_speech)}
    except Exception as exc:
        return _error(exc)


@mcp.tool()
def voice_status() -> dict:
    """Report host, first-run state, version, capture settings, and models."""
    return {"ok": True, **runtime.status()}


def main():
    try:
        mcp.run(transport="stdio")
    finally:
        runtime.stop()


if __name__ == "__main__":
    main()
