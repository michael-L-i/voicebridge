from mcp.server.fastmcp import FastMCP

from voicebridge.mcp.runtime import VoiceRuntime

mcp = FastMCP(
    "voicebridge",
    instructions=(
        "Local speech input and output for explicit VoiceBridge conversations. "
        "Only call audio tools after the user explicitly asks to start or continue "
        "a VoiceBridge voice conversation."
    ),
)
runtime = VoiceRuntime()


def _error(exc: Exception) -> dict:
    return {"ok": False, "error": str(exc)}


@mcp.tool()
def voice_start() -> dict:
    """Start a local voice conversation and load the TTS and STT models.

    Call only after an explicit user request for a VoiceBridge conversation,
    once before the first voice_speak. The initial call checks microphone and
    speaker access before local model files are downloaded or loaded; later
    turns reuse the warm models. Only one conversation can be active per Mac."""
    try:
        return {"ok": True, **runtime.start()}
    except Exception as exc:
        return _error(exc)


@mcp.tool()
def voice_speak(text: str, voice: str | None = None) -> dict:
    """Speak the host agent's exact text aloud through local TTS.

    Keep text to 1-3 short conversational sentences. Do not include code,
    bullet lists, or file paths. The text is spoken verbatim and is never
    summarized or rewritten locally. Blocks until playback finishes."""
    try:
        return {"ok": True, **runtime.speak(text, voice=voice)}
    except Exception as exc:
        return _error(exc)


@mcp.tool()
def voice_listen(
    timeout_ms: int | None = None,
    silence_ms: int | None = None,
) -> dict:
    """Listen via microphone and return the user's transcribed instruction.

    Capture ends after the configured pause (two seconds by default) or overall
    timeout. Optional arguments override config for one call. Check
    speech_detected and end_reason; a timeout may still contain valid speech.
    Playback and recording are serialized because there is no echo cancellation."""
    try:
        return {"ok": True, **runtime.listen(timeout_ms, silence_ms)}
    except Exception as exc:
        return _error(exc)


@mcp.tool()
def voice_stop() -> dict:
    """End voice mode and release its local TTS and STT model memory."""
    try:
        return {"ok": True, **runtime.stop()}
    except Exception as exc:
        return _error(exc)


@mcp.tool()
def voice_status() -> dict:
    """Report host, first-run state, version, capture settings, and models."""
    return {"ok": True, **runtime.status()}


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
