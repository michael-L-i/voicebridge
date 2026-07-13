from mcp.server.fastmcp import FastMCP

from voicebridge.mcp.runtime import VoiceRuntime

mcp = FastMCP("voicebridge")
runtime = VoiceRuntime()


def _error(exc: Exception) -> dict:
    return {"ok": False, "error": str(exc)}


@mcp.tool()
def voice_start() -> dict:
    """Start a local voice conversation and load the TTS and STT models.

    Call once before the first voice_speak. The initial call may take a while
    while local model files are downloaded or loaded; later turns reuse the
    warm models. Only one voicebridge conversation can be active per Mac."""
    try:
        return {"ok": True, **runtime.start()}
    except Exception as exc:
        return _error(exc)


@mcp.tool()
def voice_speak(text: str, voice: str | None = None) -> dict:
    """Speak Claude Code's exact text aloud through local TTS.

    Keep text to 1-3 short conversational sentences. Do not include code,
    bullet lists, or file paths. The text is spoken verbatim and is never
    summarized or rewritten locally. Blocks until playback finishes."""
    try:
        return {"ok": True, **runtime.speak(text, voice=voice)}
    except Exception as exc:
        return _error(exc)


@mcp.tool()
def voice_listen(timeout_ms: int = 30000, silence_ms: int = 800) -> dict:
    """Listen via microphone and return the user's transcribed instruction.

    Capture ends after the user pauses or timeout_ms elapses. Playback and
    recording are serialized because voicebridge has no echo cancellation."""
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
    """Report whether this Claude Code session has local voice models loaded."""
    return {"ok": True, **runtime.status()}


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
