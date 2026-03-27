"""
main.py — Command-line interface for AI Meeting Notes.

Usage examples:
    # Start recording (Ctrl+C to stop)
    python main.py record

    # Record for a fixed duration (seconds)
    python main.py record --duration 300

    # Transcribe an existing WAV file
    python main.py transcribe path/to/audio.wav

    # Summarize an existing transcript JSON
    python main.py summarize data/transcripts/session_20260317_143000.json

    # List all saved sessions
    python main.py sessions

    # List available audio devices
    python main.py devices

    # Launch the Streamlit dashboard
    python main.py dashboard
"""

import sys
import time
import json
import signal
import logging
import argparse
from pathlib import Path

# Make project root importable
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from core.config import config
from core.session import MeetingSession

console = Console()
logging.basicConfig(level=config.LOG_LEVEL)


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_record(args):
    """Start a live recording session."""
    console.rule("[bold red]🎙️ AI Meeting Notes — Recording[/]")
    console.print(f"[dim]Speech engine: {config.SPEECH_ENGINE}  |  Summarizer: {config.SUMMARIZER}[/]")
    console.print("[yellow]Press Ctrl+C to stop recording.[/]\n")

    session = MeetingSession()
    session.start()

    stop_event = False

    def on_stop(sig, frame):
        nonlocal stop_event
        stop_event = True

    signal.signal(signal.SIGINT, on_stop)

    start_time = time.time()
    last_chunk  = 0

    try:
        while not stop_event:
            chunks = session.transcript.get_all()
            if len(chunks) > last_chunk:
                for c in chunks[last_chunk:]:
                    console.print(f"[dim]{c.time_label}[/] [bold blue]{c.speaker}:[/] {c.text}")
                last_chunk = len(chunks)

            elapsed = int(time.time() - start_time)
            if args.duration and elapsed >= args.duration:
                break

            time.sleep(0.5)

    finally:
        console.print("\n[yellow]Stopping session…[/]")
        recording = session.stop()
        summary   = session.get_summary()

        console.rule("[green]Session complete[/]")
        if recording:
            console.print(f"Recording saved: [cyan]{recording}[/]")

        if summary:
            console.print(Panel(summary.summary, title="Summary", border_style="green"))
            if summary.action_items:
                console.print("[bold]Action Items:[/]")
                for item in summary.action_items:
                    console.print(f"  • {item}")

        console.print(f"\n[dim]Session ID: {session.session_id}[/]")


def cmd_transcribe(args):
    """Transcribe a WAV file."""
    import numpy as np
    import wave
    from core.transcriber import get_transcriber

    path = Path(args.file)
    if not path.exists():
        console.print(f"[red]File not found: {path}[/]")
        sys.exit(1)

    console.print(f"Transcribing [cyan]{path}[/] with Whisper ({config.WHISPER_MODEL})…\n")

    # Load WAV
    with wave.open(str(path), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
        rate   = wf.getframerate()

    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

    transcriber = get_transcriber()
    chunk = transcriber.transcribe(audio, timestamp=0)
    if chunk:
        console.print(chunk.text)
    else:
        console.print("[yellow]No speech detected.[/]")


def cmd_summarize(args):
    """Summarize a saved transcript JSON."""
    from core.summarizer import get_summarizer

    path = Path(args.file)
    if not path.exists():
        console.print(f"[red]File not found: {path}[/]")
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    text = "\n".join(
        f"[{c['time_label']}] {c['speaker']}: {c['text']}"
        for c in data.get("transcript", [])
    )

    if not text.strip():
        console.print("[yellow]Transcript is empty.[/]")
        return

    console.print("Summarizing…")
    summarizer = get_summarizer()
    summary    = summarizer.summarize(text)

    console.print(Panel(summary.summary, title="Summary", border_style="green"))
    if summary.action_items:
        console.print("[bold]Action Items:[/]")
        for item in summary.action_items:
            console.print(f"  • {item}")
    if summary.key_points:
        console.print("[bold]Key Points:[/]")
        for pt in summary.key_points:
            console.print(f"  • {pt}")


def cmd_sessions(args):
    """List all saved sessions."""
    sessions = MeetingSession.list_sessions()
    if not sessions:
        console.print("[yellow]No sessions found.[/]")
        return

    table = Table(title="Saved Sessions")
    table.add_column("Session ID", style="cyan")
    table.add_column("Started At")
    table.add_column("Duration")
    table.add_column("Chunks")
    table.add_column("Summary")

    for s in sessions:
        mins = int(s["duration"] / 60)
        secs = int(s["duration"] % 60)
        table.add_row(
            s["session_id"],
            s["started_at"][:16].replace("T", " ") if s["started_at"] else "?",
            f"{mins}m {secs}s",
            str(s["chunks"]),
            "✅" if s["has_summary"] else "—",
        )

    console.print(table)


def cmd_devices(args):
    """List audio input devices."""
    from core.audio_capture import list_audio_devices
    devices = list_audio_devices()
    if not devices:
        console.print("[yellow]No audio devices found.[/]")


def cmd_dashboard(args):
    """Launch the Streamlit dashboard."""
    import subprocess
    app_path = Path(__file__).parent / "dashboard" / "app.py"
    console.print(f"[green]Launching dashboard at http://localhost:8501[/]")
    subprocess.run(["streamlit", "run", str(app_path)], check=True)


# ── CLI setup ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="ai-meeting-notes",
        description="AI Meeting Notes — Real-time transcription and summarization",
    )
    sub = parser.add_subparsers(dest="command")

    # record
    p_record = sub.add_parser("record", help="Start recording a meeting")
    p_record.add_argument("--duration", type=int, default=None, help="Max duration in seconds")

    # transcribe
    p_trans = sub.add_parser("transcribe", help="Transcribe a WAV file")
    p_trans.add_argument("file", help="Path to WAV file")

    # summarize
    p_summ = sub.add_parser("summarize", help="Summarize a saved transcript JSON")
    p_summ.add_argument("file", help="Path to transcript JSON file")

    # sessions
    sub.add_parser("sessions", help="List saved sessions")

    # devices
    sub.add_parser("devices", help="List audio input devices")

    # dashboard
    sub.add_parser("dashboard", help="Launch the Streamlit dashboard")

    args = parser.parse_args()

    commands = {
        "record":     cmd_record,
        "transcribe": cmd_transcribe,
        "summarize":  cmd_summarize,
        "sessions":   cmd_sessions,
        "devices":    cmd_devices,
        "dashboard":  cmd_dashboard,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
