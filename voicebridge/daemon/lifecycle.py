import os
import signal
import subprocess
import sys
from pathlib import Path

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
    regardless of which path started it.

    Launches the installed `voicebridge-daemon` console script rather than
    `python -m voicebridge.daemon.server`: `-m` inserts the *current working
    directory* at sys.path[0], and since this subprocess inherits whatever
    cwd the caller (the MCP server, itself launched by Claude Code in the
    user's project directory) happens to have, a project that contains its
    own directory literally named `voicebridge` would shadow the real
    installed package -- this actually happened during development. Running
    the console script instead resolves sys.path from the venv, independent
    of cwd. `cwd` is still pinned explicitly, as defense in depth.
    """
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    daemon_bin = Path(sys.executable).parent / "voicebridge-daemon"
    proc = subprocess.Popen(
        [str(daemon_bin)],
        stdout=open(LOG_FILE, "a"),
        stderr=subprocess.STDOUT,
        cwd=str(PID_FILE.parent),
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
