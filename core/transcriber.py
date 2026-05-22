"""
transcriber.py — Speech-to-text with speaker identification.

Backends:
  1. Whisper      — local, free, no speaker names (uses pyannote for Speaker 1/2/3)
  2. AssemblyAI   — cloud API, best speaker labels out of the box
  3. Google Speech — free tier, no speaker names
"""

import logging
import time
import io
import wave
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional
import numpy as np

from core.config import config

logger = logging.getLogger(__name__)


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class TranscriptChunk:
    text:          str
    timestamp:     float
    speaker:       str = "Unknown"
    confidence:    float = 1.0
    duration:      float = 0.0
    detected_lang: str = "en"   # original language before translation

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


# ── Whisper backend ────────────────────────────────────────────────────────────

class WhisperTranscriber:
    """
    Transcribes with Whisper + optional local speaker diarization.
    Speaker diarization uses pyannote.audio to label Speaker 1, Speaker 2, etc.
    """

    def __init__(self, model_size: str = None):
        self.model_size = model_size or config.WHISPER_MODEL
        self._model     = None
        self._lock      = threading.Lock()
        self._diarizer  = None
        self._init_diarizer()

    def _init_diarizer(self):
        """Set up speaker diarizer based on config."""
        mode = config.SPEAKER_DIARIZATION
        if mode == "off":
            logger.info("Speaker diarization disabled.")
            return
        if mode == "local":
            try:
                from core.speaker_diarization import SpeakerDiarizer
                self._diarizer = SpeakerDiarizer(hf_token=config.HUGGINGFACE_TOKEN)
                logger.info("Local speaker diarizer ready (pyannote).")
            except Exception as e:
                logger.warning(f"Could not init local diarizer: {e}")

    def _load_model(self):
        if self._model is None:
            logger.info(f"Loading Whisper model '{self.model_size}'...")
            import whisper
            self._model = whisper.load_model(self.model_size)
            logger.info("Whisper model loaded.")

    def transcribe(self, audio: np.ndarray, timestamp: float) -> Optional[TranscriptChunk]:
        self._load_model()

        if np.abs(audio).mean() < 0.005:
            return None

        with self._lock:
            import whisper
            result = self._model.transcribe(
                audio,
                fp16=False,
                task="translate",   # auto-detect any language, output English
                verbose=False,
            )

        text = result["text"].strip()
        detected_lang = result.get("language", "unknown")
        if detected_lang != "en":
            logger.info(f"Detected language: {detected_lang} — translated to English")

        if not text:
            return None

        # Identify speaker
        speaker = "Unknown"
        if self._diarizer:
            try:
                speaker = self._diarizer.identify_speaker(audio, config.SAMPLE_RATE)
            except Exception as e:
                logger.debug(f"Diarization error: {e}")

        return TranscriptChunk(
            text=text,
            timestamp=timestamp,
            speaker=speaker,
            duration=len(audio) / config.SAMPLE_RATE,
            confidence=1.0,
            detected_lang=detected_lang,
        )

    def reset_speakers(self):
        """Call at session start to clear speaker memory."""
        if self._diarizer:
            self._diarizer.reset()

    def rename_speaker(self, old_label: str, new_name: str):
        """Rename 'Speaker 1' to a real name."""
        if self._diarizer:
            self._diarizer.rename_speaker(old_label, new_name)

    def get_speakers(self) -> list[str]:
        if self._diarizer:
            return self._diarizer.get_speaker_list()
        return []


# ── AssemblyAI backend ─────────────────────────────────────────────────────────

class AssemblyAITranscriber:
    """
    Cloud transcription with built-in speaker diarization.
    Returns Speaker A, Speaker B, etc. automatically.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.ASSEMBLYAI_KEY
        if not self.api_key:
            raise ValueError("ASSEMBLYAI_API_KEY is required. Set it in your .env file.")

    def transcribe(self, audio: np.ndarray, timestamp: float) -> Optional[TranscriptChunk]:
        try:
            import assemblyai as aai
        except ImportError:
            raise RuntimeError("assemblyai not installed. Run: pip install assemblyai")

        aai.settings.api_key = self.api_key
        wav_bytes  = _array_to_wav_bytes(audio)
        cfg        = aai.TranscriptionConfig(speaker_labels=True)
        transcript = aai.Transcriber().transcribe(wav_bytes, config=cfg)

        if transcript.status == aai.TranscriptStatus.error:
            logger.error(f"AssemblyAI error: {transcript.error}")
            return None

        text    = (transcript.text or "").strip()
        speaker = "Unknown"
        if transcript.utterances:
            speaker = f"Speaker {transcript.utterances[0].speaker}"

        return TranscriptChunk(
            text=text,
            timestamp=timestamp,
            speaker=speaker,
            duration=len(audio) / config.SAMPLE_RATE,
        )

    def get_speakers(self) -> list[str]:
        return []


# ── Google Speech backend ──────────────────────────────────────────────────────

class GoogleSpeechTranscriber:
    def transcribe(self, audio: np.ndarray, timestamp: float) -> Optional[TranscriptChunk]:
        try:
            import speech_recognition as sr
        except ImportError:
            raise RuntimeError("SpeechRecognition not installed. Run: pip install SpeechRecognition")

        recognizer = sr.Recognizer()
        wav_bytes  = _array_to_wav_bytes(audio)

        with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
            audio_data = recognizer.record(source)

        try:
            text = recognizer.recognize_google(audio_data)
            return TranscriptChunk(text=text.strip(), timestamp=timestamp)
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logger.error(f"Google Speech API error: {e}")
            return None

    def get_speakers(self) -> list[str]:
        return []


# ── Shared utility ─────────────────────────────────────────────────────────────

def _array_to_wav_bytes(audio: np.ndarray, sample_rate: int = None) -> bytes:
    rate = sample_rate or config.SAMPLE_RATE
    pcm  = (audio * 32768).astype(np.int16)
    buf  = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


# ── Factory ────────────────────────────────────────────────────────────────────

def get_transcriber(engine: str = None):
    engine = engine or config.SPEECH_ENGINE
    if engine == "whisper":
        return WhisperTranscriber()
    elif engine == "assemblyai":
        return AssemblyAITranscriber()
    elif engine == "google":
        return GoogleSpeechTranscriber()
    else:
        raise ValueError(f"Unknown engine: '{engine}'. Choose: whisper, assemblyai, google")


# ── Live transcript manager ────────────────────────────────────────────────────

class LiveTranscript:
    def __init__(self):
        self._chunks: list[TranscriptChunk] = []
        self._lock    = threading.Lock()
        self.on_update: Optional[Callable[[], None]] = None

    def add(self, chunk: TranscriptChunk) -> None:
        with self._lock:
            self._chunks.append(chunk)
        logger.debug(f"[{chunk.time_label}] {chunk.speaker}: {chunk.text}")
        if self.on_update:
            self.on_update()

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

    def to_dict_list(self) -> list[dict]:
        return [c.to_dict() for c in self.get_all()]
