import os
import signal
import subprocess
import sys

from voicebridge.config import CONFIG_PATH

PID_FILE = CONFIG_PATH.parent / "daemon.pid"
LOG_FILE = CONFIG_PATH.parent / "daemon.log"


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except ValueError:
        return None


def start_background() -> int:
    """Launch the daemon detached and record its pid. The sole entry point
    both the CLI and the MCP server's lazy auto-start use, so a SessionEnd
    hook (or voice_stop) can always find the daemon to shut it down,
    regardless of which path started it."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [sys.executable, "-m", "voicebridge.daemon.server"],
        stdout=open(LOG_FILE, "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid))
    return proc.pid


def stop_background() -> bool:
    """Stop the daemon if it's running. Returns whether a live process was
    actually signaled (as opposed to just clearing a stale pid file)."""
    pid = read_pid()
    sent = False
    if pid is not None and pid_alive(pid):
        os.kill(pid, signal.SIGTERM)
        sent = True
    if PID_FILE.exists():
        PID_FILE.unlink()
    return sent
