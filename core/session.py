"""
session.py — Coordinates audio capture → transcription → summarization.

This is the main controller. It:
  1. Starts audio capture
  2. Passes each audio chunk to the transcriber
  3. Appends results to a LiveTranscript
  4. Triggers re-summarization periodically
  5. Saves the session to disk

Usage:
    session = MeetingSession()
    session.start()
    # ... meeting happens ...
    session.stop()
    result = session.get_summary()
"""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from core.config import config
from core.audio_capture import AudioCapture
from core.transcriber import LiveTranscript, TranscriptChunk, get_transcriber
from core.summarizer import MeetingSummary, get_summarizer

logger = logging.getLogger(__name__)


class MeetingSession:
    """
    One complete meeting recording session.
    """

    def __init__(
        self,
        speech_engine: str    = None,
        summarizer_engine: str = None,
        on_transcript_update: Optional[Callable] = None,
        on_summary_update: Optional[Callable]    = None,
    ):
        self.speech_engine    = speech_engine
        self.summarizer_engine = summarizer_engine
        self.on_transcript_update = on_transcript_update
        self.on_summary_update    = on_summary_update

        self.started_at: Optional[datetime]  = None
        self.stopped_at: Optional[datetime]  = None
        self.session_id: str                 = ""
        self.recording_path: Optional[Path]  = None

        self.transcript   = LiveTranscript()
        self._summary: Optional[MeetingSummary] = None
        self._lock        = threading.Lock()

        self._capture     = None
        self._transcriber = None
        self._summarizer  = None
        

        self._summarize_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Wire transcript update hook
        self.transcript.on_update = self._on_transcript_updated

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start recording and transcribing."""
        self.started_at = datetime.now()
        self.session_id = self.started_at.strftime("%Y%m%d_%H%M%S")
        self._stop_event.clear()

        logger.info(f"Starting meeting session {self.session_id}")

        # Load transcriber
        from core.config import config
        self._transcriber = get_transcriber(config)
        # Start audio capture
        self._capture = AudioCapture(on_chunk=self._on_audio_chunk)
        self._capture.start(save_recording=True)

        # Start periodic re-summarization (every 60 seconds)
        self._summarize_thread = threading.Thread(
            target=self._periodic_summarize, daemon=True
        )
        self._summarize_thread.start()

        logger.info("Session started. Listening…")

    def stop(self):
        """Stop recording and finalize session safely"""
        try:
            # Stop audio capture
            if self._capture:
                self._capture.stop()

            # Stop streaming transcriber (if any)
            if hasattr(self._transcriber, "stop"):
                self._transcriber.stop()

            # Run summarization
            self._run_summarization()

        except Exception as e:
            print(f"Stop error: {e}")

    def get_summary(self) -> Optional[MeetingSummary]:
        with self._lock:
            return self._summary

    def get_duration(self) -> float:
        """Return session duration in seconds."""
        if not self.started_at:
            return 0.0
        end = self.stopped_at or datetime.now()
        return (end - self.started_at).total_seconds()

    def get_entities(self) -> dict:
        """Return named entities extracted from the transcript."""
        return {}

    def get_topics(self) -> list[str]:
        return []

    # ── Internal ───────────────────────────────────────────────────────────────

    def _on_audio_chunk(self, audio_array, timestamp: float) -> None:
        """Called by AudioCapture for each new audio chunk."""
        if not self._transcriber:
            return

        try:
            chunk: Optional[TranscriptChunk] = self._transcriber.transcribe(audio_array, timestamp)
            if chunk:
                self.transcript.add(chunk)
        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)

    def _on_transcript_updated(self) -> None:
        """Called every time a new transcript chunk arrives."""
        if self.on_transcript_update:
            self.on_transcript_update()

    def _periodic_summarize(self) -> None:
        """Re-summarize every 60 seconds while the session is running."""
        while not self._stop_event.wait(timeout=60):
            if len(self.transcript.get_all()) >= 3:
                self._run_summarization()

    def _run_summarization(self) -> None:
        """Summarize the current transcript."""
        text = self.transcript.get_full_text()
        if len(text.split()) < 20:
            return

        try:
            if not self._summarizer:
                from core.config import config
                self._summarizer = get_summarizer(config)

            summary = self._summarizer.summarize(text)

            with self._lock:
                self._summary = summary

            if self.on_summary_update:
                self.on_summary_update()

        except Exception as e:
            logger.error(f"Summarization error: {e}", exc_info=True)

    def _save_session(self) -> None:
        """Persist the session transcript and summary as JSON."""
        session_data = {
            "session_id":   self.session_id,
            "started_at":   self.started_at.isoformat() if self.started_at else None,
            "stopped_at":   self.stopped_at.isoformat() if self.stopped_at else None,
            "duration_sec": self.get_duration(),
            "recording":    str(self.recording_path) if self.recording_path else None,
            "transcript":   self.transcript.to_dict_list(),
            "summary":      self._summary.to_dict() if self._summary else None,
            "entities":     self.get_entities(),
            "topics":       self.get_topics(),
        }

        # Save transcript
        transcript_path = config.TRANS_DIR / f"session_{self.session_id}.json"
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Session saved: {transcript_path}")

    @classmethod
    def load_session(cls, session_id: str) -> Optional[dict]:
        """Load a saved session from disk."""
        path = config.TRANS_DIR / f"session_{session_id}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def list_sessions(cls) -> list[dict]:
        """List all saved sessions, most recent first."""
        sessions = []
        for path in sorted(config.TRANS_DIR.glob("session_*.json"), reverse=True):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                sessions.append({
                    "session_id": data.get("session_id", ""),
                    "started_at": data.get("started_at", ""),
                    "duration":   data.get("duration_sec", 0),
                    "chunks":     len(data.get("transcript", [])),
                    "has_summary": data.get("summary") is not None,
                    "path":       str(path),
                })
            except Exception:
                pass
        return sessions
