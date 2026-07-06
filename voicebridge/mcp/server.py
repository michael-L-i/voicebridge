import os
import time

import httpx
from mcp.server.fastmcp import FastMCP

from voicebridge.config import load_config
from voicebridge.daemon import lifecycle

_config = load_config()
_BASE_URL = f"http://{_config.daemon.host}:{_config.daemon.port}"
# Claude Code sets this in every process it spawns, including this MCP
# server -- it's how we know which session a tool call belongs to without
# needing the agent to pass it explicitly.
_SESSION_ID = os.environ.get("CLAUDE_CODE_SESSION_ID", "unknown-session")

# A genuine first-ever cold start downloads and loads Qwen2.5-3B + Kokoro-82M
# + Parakeet (several GB total) inside the daemon's own startup -- 60s isn't
# enough for that, only for a warm restart.
_DAEMON_START_TIMEOUT_S = 300

mcp = FastMCP("voicebridge")


def _ensure_daemon_running() -> None:
    try:
        httpx.get(f"{_BASE_URL}/health", timeout=2).raise_for_status()
        return
    except Exception:
        pass

    lifecycle.start_background()
    for _ in range(_DAEMON_START_TIMEOUT_S):
        time.sleep(1)
        try:
            httpx.get(f"{_BASE_URL}/health", timeout=2).raise_for_status()
            return
        except Exception:
            continue
    raise RuntimeError(
        f"voicebridge daemon did not become healthy within {_DAEMON_START_TIMEOUT_S}s of starting it"
    )


@mcp.tool()
def voice_speak(text: str) -> dict:
    """Speak a short conversational message aloud through local TTS.

    Keep `text` to 1-3 short sentences -- no code, no bullet lists, no file
    paths, this is spoken, not read. Longer text is auto-compressed but
    shorter is better. Blocks until speech finishes (there's no echo
    cancellation, so voice_listen must never overlap with playback)."""
    _ensure_daemon_running()
    resp = httpx.post(
        f"{_BASE_URL}/speak",
        json={"session_id": _SESSION_ID, "text": text},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def voice_listen(timeout_ms: int = 30000, silence_ms: int = 800) -> dict:
    """Listen via microphone and return the transcribed text once the user
    pauses or timeout_ms elapses. Treat the transcript as the user's next
    instruction. Check `timed_out` -- if true, no speech was detected."""
    _ensure_daemon_running()
    resp = httpx.post(
        f"{_BASE_URL}/listen",
        json={"session_id": _SESSION_ID, "timeout_ms": timeout_ms, "silence_ms": silence_ms},
        timeout=(timeout_ms / 1000) + 10,
    )
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def voice_stop() -> dict:
    """Shut down the voicebridge daemon and free the MLX models it holds in
    memory (several GB of RAM). Call this once, at the very end of a
    /voice-code conversation after the final spoken goodbye -- not between
    turns."""
    stopped = lifecycle.stop_background()
    return {"stopped": stopped}


@mcp.tool()
def voice_status() -> dict:
    """Check whether the voicebridge daemon is running and which models are loaded."""
    try:
        resp = httpx.get(f"{_BASE_URL}/health", timeout=2)
        resp.raise_for_status()
        return {"ready": True, **resp.json()}
    except Exception as e:
        return {"ready": False, "error": str(e)}


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
