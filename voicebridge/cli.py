import json
import shutil
import subprocess
import sys
from pathlib import Path

import click
import httpx

from voicebridge.config import CONFIG_PATH, ensure_config_exists, load_config

MIN_FREE_GB_RECOMMENDED = 10
PID_FILE = CONFIG_PATH.parent / "daemon.pid"

CLAUDE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
CLAUDE_COMMANDS_DIR = Path.home() / ".claude" / "commands"
VOICEBRIDGE_HOOKS_DIR = CONFIG_PATH.parent / "hooks"
REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_HOOKS_DIR = REPO_ROOT / "voicebridge" / "hooks"
REPO_COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"


@click.group()
def main():
    """voicebridge: a fully local voice companion for Claude Code."""


@main.command()
def doctor():
    """Check that this machine can run voicebridge (audio I/O, Metal, disk space)."""
    ok = True

    path = ensure_config_exists()
    click.echo(f"[ok]   config file: {path}")

    try:
        import sounddevice as sd

        devices = sd.query_devices()
        default_in, default_out = sd.default.device
        if default_in is None or default_out is None:
            click.echo("[warn] sounddevice loaded, but no default input/output device is set")
        else:
            click.echo(
                f"[ok]   audio I/O: input={devices[default_in]['name']!r}, "
                f"output={devices[default_out]['name']!r}"
            )
    except Exception as e:
        click.echo(f"[fail] sounddevice/PortAudio not available: {e}")
        ok = False

    try:
        import mlx.core as mx

        device = mx.default_device()
        click.echo(f"[ok]   mlx default device: {device}")
        if "gpu" not in str(device).lower():
            click.echo("[warn] mlx is not reporting a GPU (Metal) device — check your mlx install")
    except Exception as e:
        click.echo(f"[fail] mlx not available: {e}")
        ok = False

    try:
        import mlx_audio  # noqa: F401

        click.echo("[ok]   mlx-audio importable")
    except Exception as e:
        click.echo(f"[fail] mlx-audio not available: {e}")
        ok = False

    try:
        import mlx_lm  # noqa: F401

        click.echo("[ok]   mlx-lm importable")
    except Exception as e:
        click.echo(f"[fail] mlx-lm not available: {e}")
        ok = False

    if shutil.which("espeak-ng") is None:
        click.echo(
            "[warn] espeak-ng not found — Kokoro TTS will skip out-of-dictionary "
            "words instead of phonemizing them. Fix: brew install espeak-ng"
        )
    else:
        click.echo("[ok]   espeak-ng found")

    total, used, free = shutil.disk_usage(str(CONFIG_PATH.parent))
    free_gb = free / (1024**3)
    if free_gb < MIN_FREE_GB_RECOMMENDED:
        click.echo(
            f"[warn] only {free_gb:.1f}GB free on this volume — model downloads "
            f"(summarizer + Kokoro + Parakeet) can total several GB"
        )
    else:
        click.echo(f"[ok]   disk space: {free_gb:.1f}GB free")

    if ok:
        click.echo("\nAll critical checks passed.")
    else:
        click.echo("\nSome checks failed — install missing dependencies before continuing.")
        raise SystemExit(1)


@main.command()
@click.option("--background", "-d", is_flag=True, help="Start detached and return immediately.")
def start(background: bool):
    """Start the voicebridge daemon (loads and warms the summarizer + TTS models)."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        if _pid_alive(pid):
            click.echo(f"Daemon already running (pid {pid}).")
            return
        PID_FILE.unlink()

    if not background:
        from voicebridge.daemon.server import main as run_daemon

        run_daemon()
        return

    proc = subprocess.Popen(
        [sys.executable, "-m", "voicebridge.daemon.server"],
        stdout=open(CONFIG_PATH.parent / "daemon.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid))
    click.echo(f"Started daemon in background (pid {proc.pid}). Logs: {CONFIG_PATH.parent / 'daemon.log'}")


@main.command()
def stop():
    """Stop a background voicebridge daemon started with `start --background`."""
    if not PID_FILE.exists():
        click.echo("No pid file found — is the daemon running in the background?")
        return
    pid = int(PID_FILE.read_text().strip())
    if _pid_alive(pid):
        import os
        import signal

        os.kill(pid, signal.SIGTERM)
        click.echo(f"Sent SIGTERM to pid {pid}.")
    else:
        click.echo(f"pid {pid} was not running.")
    PID_FILE.unlink()


@main.command()
def status():
    """Check whether the daemon is running and report loaded models."""
    cfg = load_config()
    url = f"http://{cfg.daemon.host}:{cfg.daemon.port}/health"
    try:
        resp = httpx.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        click.echo(f"[ok] daemon reachable at {url}")
        click.echo(f"     summarizer: {data['models']['summarizer']}")
        click.echo(f"     tts:        {data['models']['tts']}")
        click.echo(f"     stt:        {data['models']['stt']}")
        click.echo(f"     uptime:     {data['uptime_s']:.0f}s")
    except Exception as e:
        click.echo(f"[fail] daemon not reachable at {url}: {e}")
        raise SystemExit(1)


def _pid_alive(pid: int) -> bool:
    import os

    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


@main.command(name="listen-test")
@click.option("--silence-ms", default=None, type=int, help="Override stt.silence_ms from config.")
@click.option("--max-listen-ms", default=None, type=int, help="Override stt.max_listen_ms from config.")
def listen_test(silence_ms: int | None, max_listen_ms: int | None):
    """Record from the mic, transcribe with the configured STT provider, and
    print the result and latency -- for validating mic capture and STT
    accuracy directly, without going through the daemon or a hook."""
    from voicebridge.daemon.audio_in import listen
    from voicebridge.providers.registry import get_stt_provider

    cfg = load_config()
    provider = get_stt_provider(cfg.stt).load()

    click.echo(f"Loaded STT provider: {cfg.stt.provider} ({cfg.stt.model})")
    click.echo("Listening... speak now.")

    import time

    t0 = time.time()
    audio, timed_out = listen(
        provider.sample_rate,
        silence_ms=silence_ms or cfg.stt.silence_ms,
        max_listen_ms=max_listen_ms or cfg.stt.max_listen_ms,
    )
    record_dt = time.time() - t0

    if timed_out:
        click.echo(f"Timed out after {record_dt:.1f}s without detecting speech-then-silence.")
    if audio.size == 0:
        click.echo("No audio captured.")
        return

    t0 = time.time()
    transcript = provider.transcribe(audio)
    transcribe_dt = time.time() - t0

    click.echo(f"\nRecorded {audio.size / provider.sample_rate:.2f}s in {record_dt:.2f}s")
    click.echo(f"Transcribed in {transcribe_dt:.2f}s")
    click.echo(f"\nTranscript: {transcript!r}")


def _relink(target: Path, source: Path) -> bool:
    """Symlink target -> source, replacing any existing file/link at target.
    Returns True if a change was made, False if it already pointed there."""
    if target.is_symlink() and target.resolve() == source.resolve():
        return False
    if target.is_symlink() or target.exists():
        target.unlink()
    target.symlink_to(source)
    return True


@main.command(name="install-hooks")
def install_hooks():
    """Link voicebridge's hook scripts + slash command into place and
    register Stop/SubagentStop in ~/.claude/settings.json. Additive and
    idempotent -- safe to run repeatedly, never touches other hooks/settings."""
    VOICEBRIDGE_HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("on_stop.sh", "on_subagent_stop.sh"):
        changed = _relink(VOICEBRIDGE_HOOKS_DIR / name, REPO_HOOKS_DIR / name)
        suffix = "" if changed else " (already linked)"
        click.echo(f"[ok] {VOICEBRIDGE_HOOKS_DIR / name} -> {REPO_HOOKS_DIR / name}{suffix}")

    CLAUDE_COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
    changed = _relink(CLAUDE_COMMANDS_DIR / "voice-code.md", REPO_COMMANDS_DIR / "voice-code.md")
    click.echo(
        f"[ok] {CLAUDE_COMMANDS_DIR / 'voice-code.md'} -> {REPO_COMMANDS_DIR / 'voice-code.md'}"
        + ("" if changed else " (already linked)")
    )

    settings = {}
    if CLAUDE_SETTINGS_PATH.exists():
        settings = json.loads(CLAUDE_SETTINGS_PATH.read_text())
    hooks = settings.setdefault("hooks", {})

    any_added = False
    for event, script_name in (("Stop", "on_stop.sh"), ("SubagentStop", "on_subagent_stop.sh")):
        command = f"~/.voicebridge/hooks/{script_name}"
        entries = hooks.setdefault(event, [])
        already_present = any(
            h.get("command") == command for entry in entries for h in entry.get("hooks", [])
        )
        if already_present:
            click.echo(f"[ok] {event} hook already registered in settings.json")
            continue
        entries.append({"hooks": [{"type": "command", "command": command, "async": True}]})
        click.echo(f"[ok] registered {event} hook in settings.json")
        any_added = True

    if any_added:
        CLAUDE_SETTINGS_PATH.write_text(json.dumps(settings, indent=2) + "\n")
        click.echo(f"[ok] wrote {CLAUDE_SETTINGS_PATH}")
    else:
        click.echo(f"[ok] {CLAUDE_SETTINGS_PATH} already up to date")


LAUNCHD_LABEL = "com.voicebridge.daemon"
LAUNCHD_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"
PLIST_TEMPLATE_PATH = REPO_ROOT / "config" / "com.voicebridge.daemon.plist.template"


@main.command(name="install-launchd")
def install_launchd():
    """Install (but do not load) a launchd agent that starts the daemon at
    login and restarts it if it crashes. Review the generated plist, then run
    `launchctl load <path>` yourself when you're ready to enable it."""
    template = PLIST_TEMPLATE_PATH.read_text()
    plist = template.format(python=sys.executable, log_path=str(CONFIG_PATH.parent / "daemon.log"))
    LAUNCHD_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAUNCHD_PLIST_PATH.write_text(plist)
    click.echo(f"[ok] wrote {LAUNCHD_PLIST_PATH}")
    click.echo(f"Not loaded yet. To enable auto-start at login:\n  launchctl load {LAUNCHD_PLIST_PATH}")
    click.echo(f"To undo later:\n  launchctl unload {LAUNCHD_PLIST_PATH}\n  voicebridge uninstall-launchd")


@main.command(name="uninstall-launchd")
def uninstall_launchd():
    """Unload and remove the launchd agent installed by install-launchd."""
    if not LAUNCHD_PLIST_PATH.exists():
        click.echo("No launchd plist found — nothing to do.")
        return
    subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST_PATH)], capture_output=True)
    LAUNCHD_PLIST_PATH.unlink()
    click.echo(f"[ok] unloaded and removed {LAUNCHD_PLIST_PATH}")


@main.command(name="install-mcp")
def install_mcp():
    """Register the voicebridge MCP server with Claude Code at user scope.
    Idempotent -- skips if already registered."""
    venv_bin = Path(sys.executable).parent
    mcp_command = str(venv_bin / "voicebridge-mcp")

    result = subprocess.run(["claude", "mcp", "list"], capture_output=True, text=True)
    if "voicebridge" in result.stdout:
        click.echo("[ok] voicebridge MCP server already registered")
        return

    subprocess.run(
        ["claude", "mcp", "add", "--scope", "user", "voicebridge", "--", mcp_command],
        check=True,
    )
    click.echo("[ok] registered voicebridge MCP server with Claude Code (user scope)")


if __name__ == "__main__":
    main()
