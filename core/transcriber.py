"""
core/transcriber.py — Lightweight cloud transcription via AssemblyAI
(FINAL CLEAN VERSION — NO ERRORS)
"""

import io
import wave
import time
import logging
import threading
from dataclasses import dataclass
from typing import Optional, List
import numpy as np

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────

@dataclass
class TranscriptChunk:
    text: str
    speaker: str = "Speaker"
    timestamp: float = 0.0
    language: str = "en"
    original_text: str = ""

    @property
    def time_label(self) -> str:
        m, s = divmod(int(self.timestamp), 60)
        return f"{m:02d}:{s:02d}"


class LiveTranscript:
    def __init__(self):
        self._chunks: List[TranscriptChunk] = []
        self._lock = threading.Lock()

    def add(self, chunk: TranscriptChunk):
        with self._lock:
            self._chunks.append(chunk)

    def get_all(self) -> List[TranscriptChunk]:
        with self._lock:
            return list(self._chunks)

    def to_text(self) -> str:
        return "\n".join(
            f"[{c.time_label}] {c.speaker}: {c.text}"
            for c in self.get_all()
        )

    def to_dict_list(self):
        return [
            {
                "text": c.text,
                "speaker": c.speaker,
                "timestamp": c.timestamp,
                "language": c.language,
            }
            for c in self.get_all()
        ]

    def get_full_text(self) -> str:
        return "\n".join(c.text for c in self.get_all())

    def clear(self):
        with self._lock:
            self._chunks.clear()


# ─────────────────────────────────────────────
# ASSEMBLY AI TRANSCRIBER
# ─────────────────────────────────────────────

class AssemblyAITranscriber:

    def __init__(
        self,
        api_key: str,
        language_code: str = "hi",
        translate_to_english: bool = True,
        speaker_labels: bool = True,
    ):
        try:
            import assemblyai as aai
        except ImportError:
            raise ImportError("Run: pip install assemblyai")

        self.aai = aai
        self.aai.settings.api_key = api_key

        self.language_code = language_code
        self.translate = translate_to_english
        self.speaker_labels = speaker_labels

        self._last_chunks: List[TranscriptChunk] = []
        self._session_start = time.time()

        logger.info("AssemblyAI Transcriber initialized")
        

    # ✅ CORRECT METHOD (FIXED)
    def transcribe_file(self, audio_path: str) -> List[TranscriptChunk]:
        config = self.aai.TranscriptionConfig(
            speech_models=["universal"],   # ✅ correct new API
            language_code=self.language_code,  # ✅ do NOT use language_detection
            speaker_labels=self.speaker_labels,
        )

        transcriber = self.aai.Transcriber(config=config)
        transcript = transcriber.transcribe(audio_path)

        if transcript.status == self.aai.TranscriptStatus.error:
            logger.error(f"AssemblyAI error: {transcript.error}")
            return []

        chunks: List[TranscriptChunk] = []

        if self.speaker_labels and transcript.utterances:
            for utt in transcript.utterances:
                if not utt.text:
                    continue

                chunks.append(
                    TranscriptChunk(
                        text=utt.text.strip(),
                        speaker=f"Speaker {utt.speaker}",
                        timestamp=utt.start / 1000.0,
                        language=transcript.language_code or self.language_code,
                    )
                )
        else:
            for sent in transcript.get_sentences() or []:
                chunks.append(
                    TranscriptChunk(
                        text=sent.text.strip(),
                        speaker="Speaker",
                        timestamp=sent.start / 1000.0,
                        language=transcript.language_code or self.language_code,
                    )
                )

        self._last_chunks = chunks
        return chunks
    
    def rename_speaker(self, old_name: str, new_name: str):
        """Rename speaker in stored chunks"""
        for chunk in self._last_chunks:
            if chunk.speaker == old_name:
                chunk.speaker = new_name

    def transcribe_numpy(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        timestamp: float = 0.0,
    ) -> Optional[TranscriptChunk]:

        import tempfile
        import os

        buf = io.BytesIO()
        pcm = (audio * 32768).astype(np.int16)

        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm.tobytes())

        buf.seek(0)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(buf.read())
            tmp_path = tmp.name

        try:
            chunks = self.transcribe_file(tmp_path)

            if chunks:
                return TranscriptChunk(
                    text=" ".join(c.text for c in chunks),
                    speaker=chunks[0].speaker,
                    timestamp=timestamp,
                    language=chunks[0].language,
                )
        finally:
            os.unlink(tmp_path)

        return None

    def transcribe(self, audio: np.ndarray, timestamp: float = 0.0):
        return self.transcribe_numpy(audio, timestamp=timestamp)

    def get_speakers(self) -> List[str]:
        return sorted(list({c.speaker for c in self._last_chunks}))


# ─────────────────────────────────────────────
# FACTORY
# ─────────────────────────────────────────────

def get_transcriber(config=None):
    if config is None:
        from core.config import config as cfg
        config = cfg

    engine = config.SPEECH_ENGINE.lower()

    if engine == "assemblyai":
        if not config.ASSEMBLYAI_API_KEY:
            raise ValueError("Set ASSEMBLYAI_API_KEY in .env")

        return AssemblyAITranscriber(
            api_key=config.ASSEMBLYAI_API_KEY,
            language_code=getattr(config, "LANGUAGE_CODE", "hi"),
            translate_to_english=getattr(config, "TRANSLATE_TO_ENGLISH", True),
            speaker_labels=getattr(config, "SPEAKER_DIARIZATION", True),
        )

    else:
        raise ValueError("Only 'assemblyai' is supported")