import os
import subprocess
import sys
import time

import httpx
from mcp.server.fastmcp import FastMCP

from voicebridge.config import load_config

_config = load_config()
_BASE_URL = f"http://{_config.daemon.host}:{_config.daemon.port}"
# Claude Code sets this in every process it spawns, including this MCP
# server -- it's how we know which session a tool call belongs to without
# needing the agent to pass it explicitly.
_SESSION_ID = os.environ.get("CLAUDE_CODE_SESSION_ID", "unknown-session")

mcp = FastMCP("voicebridge")


def _ensure_daemon_running() -> None:
    try:
        httpx.get(f"{_BASE_URL}/health", timeout=2).raise_for_status()
        return
    except Exception:
        pass

    subprocess.Popen(
        [sys.executable, "-m", "voicebridge.daemon.server"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(60):
        time.sleep(1)
        try:
            httpx.get(f"{_BASE_URL}/health", timeout=2).raise_for_status()
            return
        except Exception:
            continue
    raise RuntimeError("voicebridge daemon did not become healthy within 60s of starting it")


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
