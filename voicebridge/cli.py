import shutil
import time

import click
import httpx

from voicebridge.config import CONFIG_PATH, ensure_config_exists, load_config
from voicebridge.daemon import lifecycle

MIN_FREE_GB_RECOMMENDED = 10


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
    pid = lifecycle.read_pid()
    if pid is not None and lifecycle.pid_alive(pid):
        click.echo(f"Daemon already running (pid {pid}).")
        return

    if not background:
        from voicebridge.daemon.server import main as run_daemon

        run_daemon()
        return

    pid = lifecycle.start_background()
    click.echo(f"Started daemon in background (pid {pid}). Logs: {lifecycle.LOG_FILE}")


@main.command()
def stop():
    """Stop a background voicebridge daemon started with `start --background`."""
    pid = lifecycle.read_pid()
    if pid is None:
        click.echo("No pid file found — is the daemon running in the background?")
        return
    if lifecycle.stop_background():
        click.echo(f"Sent SIGTERM to pid {pid}.")
    else:
        click.echo(f"pid {pid} was not running.")


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


@main.command(name="listen-test")
@click.option("--silence-ms", default=None, type=int, help="Override stt.silence_ms from config.")
@click.option("--max-listen-ms", default=None, type=int, help="Override stt.max_listen_ms from config.")
def listen_test(silence_ms: int | None, max_listen_ms: int | None):
    """Record from the mic, transcribe with the configured STT provider, and
    print the result and latency -- for validating mic capture and STT
    accuracy directly, without going through the daemon."""
    from voicebridge.daemon.audio_in import listen
    from voicebridge.providers.registry import get_stt_provider

    cfg = load_config()
    provider = get_stt_provider(cfg.stt).load()

    click.echo(f"Loaded STT provider: {cfg.stt.provider} ({cfg.stt.model})")
    click.echo("Listening... speak now.")

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


if __name__ == "__main__":
    main()
