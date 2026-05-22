"""
fast_transcriber.py — Near real-time transcription using faster-whisper.

Why faster-whisper?
  - 4x faster than original Whisper
  - Uses CTranslate2 engine (highly optimized)
  - Works on CPU without GPU
  - Supports streaming word by word

Setup:
    pip install faster-whisper

Chunk size is reduced to 2 seconds (vs 5 seconds before),
so translation appears much faster — similar to Google Translate live mode.
"""

import threading
import logging
import time
import numpy as np
from datetime import datetime
from typing import Callable, Optional
from dataclasses import dataclass

from core.config import config

logger = logging.getLogger(__name__)


@dataclass
class TranscriptChunk:
    text:          str
    timestamp:     float
    speaker:       str = "Unknown"
    confidence:    float = 1.0
    duration:      float = 0.0
    detected_lang: str = "en"

    @property
    def time_label(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")

    def to_dict(self) -> dict:
        return {
            "text":          self.text,
            "timestamp":     self.timestamp,
            "time_label":    self.time_label,
            "speaker":       self.speaker,
            "confidence":    self.confidence,
            "duration":      self.duration,
            "detected_lang": self.detected_lang,
        }


class FastWhisperTranscriber:
    """
    Uses faster-whisper for near real-time transcription.

    Key improvements over original Whisper:
      - 4x faster on CPU (same accuracy)
      - 2-second chunks instead of 5-second (feels much more live)
      - Word-level timestamps available
      - Streams partial results as words come in

    Install: pip install faster-whisper
    """

    def __init__(
        self,
        model_size: str = None,
        chunk_seconds: int = 2,          # 2 sec chunks = much faster feedback
        on_partial: Optional[Callable[[str], None]] = None,  # fires per word
    ):
        self.model_size    = model_size or config.WHISPER_MODEL
        self.chunk_seconds = chunk_seconds
        self.on_partial    = on_partial   # optional: fires as each word arrives
        self._model        = None
        self._lock         = threading.Lock()

    def _load_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise RuntimeError(
                    "faster-whisper not installed.\n"
                    "Run: pip install faster-whisper"
                )
            logger.info(f"Loading faster-whisper model '{self.model_size}'...")
            # compute_type='int8' = fastest CPU mode, tiny memory
            self._model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
            )
            logger.info("faster-whisper model ready.")

    def transcribe(self, audio: np.ndarray, timestamp: float) -> Optional[TranscriptChunk]:
        """
        Transcribe audio and translate to English.
        Returns a TranscriptChunk, or None if audio is silent.
        """
        self._load_model()

        # Skip silent audio
        if np.abs(audio).mean() < 0.005:
            return None

        with self._lock:
            # task='translate' → auto-detect language → output English
            segments, info = self._model.transcribe(
                audio,
                task="translate",
                beam_size=1,          # beam_size=1 is fastest (greedy)
                word_timestamps=True, # enables per-word streaming
                vad_filter=True,      # skip silence automatically
                vad_parameters=dict(
                    min_silence_duration_ms=300,
                ),
                language=None,        # auto-detect
            )

            full_text  = ""
            lang       = info.language
            confidence = info.language_probability

            for segment in segments:
                seg_text = segment.text.strip()
                if not seg_text:
                    continue
                full_text += " " + seg_text

                # Fire partial callback word by word (like Google Translate live)
                if self.on_partial and segment.words:
                    for word in segment.words:
                        if self.on_partial:
                            self.on_partial(word.word.strip())

        full_text = full_text.strip()
        if not full_text:
            return None

        if lang != "en":
            logger.info(f"Detected: {lang} ({confidence:.0%}) → translated to English")

        return TranscriptChunk(
            text=full_text,
            timestamp=timestamp,
            duration=len(audio) / config.SAMPLE_RATE,
            confidence=confidence,
            detected_lang=lang,
        )


class LiveTranscript:
    """Thread-safe growing list of transcript chunks."""

    def __init__(self):
        self._chunks: list[TranscriptChunk] = []
        self._lock    = threading.Lock()
        self._partial = ""                   # current partial word being typed
        self.on_update: Optional[Callable[[], None]] = None

    def add(self, chunk: TranscriptChunk) -> None:
        with self._lock:
            self._chunks.append(chunk)
            self._partial = ""
        logger.debug(f"[{chunk.time_label}] {chunk.speaker}: {chunk.text}")
        if self.on_update:
            self.on_update()

    def set_partial(self, word: str) -> None:
        """Update the live partial word being spoken (for streaming UI)."""
        with self._lock:
            self._partial += " " + word
        if self.on_update:
            self.on_update()

    def get_partial(self) -> str:
        with self._lock:
            return self._partial.strip()

    def get_all(self) -> list[TranscriptChunk]:
        with self._lock:
            return list(self._chunks)

    def get_full_text(self) -> str:
        return "\n".join(
            f"[{c.time_label}] {c.speaker}: {c.text}"
            for c in self.get_all()
        )

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()
            self._partial = ""

    def to_dict_list(self) -> list[dict]:
        return [c.to_dict() for c in self.get_all()]


def get_transcriber(engine: str = None):
    """Return the right transcriber based on config."""
    engine = engine or config.SPEECH_ENGINE

    if engine == "whisper":
        # Use faster-whisper if installed, fall back to original whisper
        try:
            import faster_whisper  # noqa
            logger.info("Using faster-whisper (4x faster than original)")
            return FastWhisperTranscriber()
        except ImportError:
            logger.warning("faster-whisper not installed, using original Whisper.")
            logger.warning("Install it for much faster translation: pip install faster-whisper")
            from core.transcriber import WhisperTranscriber
            return WhisperTranscriber()

    elif engine == "assemblyai":
        from core.transcriber import AssemblyAITranscriber
        return AssemblyAITranscriber()

    elif engine == "google":
        from core.transcriber import GoogleSpeechTranscriber
        return GoogleSpeechTranscriber()

    else:
        raise ValueError(f"Unknown engine: {engine}")
