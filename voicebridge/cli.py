import shutil
import time

import click

from voicebridge.config import CONFIG_PATH, ensure_config_exists, load_config

MIN_FREE_GB_RECOMMENDED = 10


@click.group()
def main():
    """voicebridge: a fully local voice companion for coding agents."""


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
            f"can total several GB for the heaviest speech pair"
        )
    else:
        click.echo(f"[ok]   disk space: {free_gb:.1f}GB free")

    if ok:
        click.echo("\nAll critical checks passed.")
    else:
        click.echo("\nSome checks failed — install missing dependencies before continuing.")
        raise SystemExit(1)


@main.command(name="listen-test")
@click.option("--silence-ms", default=None, type=int, help="Override stt.silence_ms from config.")
@click.option("--max-listen-ms", default=None, type=int, help="Override stt.max_listen_ms from config.")
def listen_test(silence_ms: int | None, max_listen_ms: int | None):
    """Record from the mic, transcribe with the configured STT provider, and
    print the result and latency -- for validating mic capture and STT
    accuracy directly, without going through the MCP server."""
    from voicebridge.audio.capture import listen
    from voicebridge.providers.registry import get_stt_provider

    cfg = load_config()
    provider = get_stt_provider(cfg.stt).load()

    click.echo(f"Loaded STT provider: {cfg.stt.provider} ({cfg.stt.model})")
    click.echo("Listening... speak now.")

    t0 = time.time()
    result = listen(
        provider.sample_rate,
        silence_ms=silence_ms or cfg.stt.silence_ms,
        max_listen_ms=max_listen_ms or cfg.stt.max_listen_ms,
        input_device=cfg.audio.input_device,
        output_device=cfg.audio.output_device,
    )
    record_dt = time.time() - t0

    click.echo(f"Capture ended: {result.end_reason}")
    if result.error:
        click.echo(f"Audio error: {result.error}")
    if not result.speech_detected or result.audio.size == 0:
        click.echo("No audio captured.")
        return

    t0 = time.time()
    transcript = provider.transcribe(result.audio)
    transcribe_dt = time.time() - t0

    click.echo(
        f"\nRecorded {result.audio.size / provider.sample_rate:.2f}s "
        f"in {record_dt:.2f}s"
    )
    click.echo(f"Transcribed in {transcribe_dt:.2f}s")
    click.echo(f"\nTranscript: {transcript!r}")


if __name__ == "__main__":
    main()
