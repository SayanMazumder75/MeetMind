import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).parent.parent / ".env")


class Config:
    # ── Base ─────────────────────────────────────────────
    BASE_DIR = Path(__file__).resolve().parent.parent

    # ── App ──────────────────────────────────────────────
    APP_NAME: str = os.getenv("APP_NAME", "AI Meeting Notes")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ── Speech Recognition ───────────────────────────────
    SPEECH_ENGINE: str = os.getenv("SPEECH_ENGINE", "assemblyai")
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "tiny")
    ASSEMBLYAI_API_KEY: str = os.getenv("ASSEMBLYAI_API_KEY", "")
    LANGUAGE_CODE: str = os.getenv("LANGUAGE_CODE", "hi")
    TRANSLATE_TO_ENGLISH: bool = os.getenv("TRANSLATE_TO_ENGLISH", "true").lower() == "true"
    SPEAKER_DIARIZATION: bool = os.getenv("SPEAKER_DIARIZATION", "true").lower() == "true"

    # ── Summarization ────────────────────────────────────
    SUMMARIZER: str = os.getenv("SUMMARIZER", "claude")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # ── Audio ────────────────────────────────────────────
    AUDIO_SAMPLE_RATE: int = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
    AUDIO_CHUNK_SECONDS: int = int(os.getenv("AUDIO_CHUNK_SECONDS", "8"))
    AUDIO_DEVICE_INDEX: int = int(os.getenv("AUDIO_DEVICE_INDEX", "-1"))

    # ── Storage ──────────────────────────────────────────
    DATA_DIR: Path = BASE_DIR / "data"
    RECORDINGS_DIR: Path = DATA_DIR / "recordings"
    TRANSCRIPTS_DIR: Path = DATA_DIR / "transcripts"
    SUMMARIES_DIR: Path = DATA_DIR / "summaries"
    SAMPLE_RATE = AUDIO_SAMPLE_RATE
    CHUNK_SECONDS = AUDIO_CHUNK_SECONDS
    # ✅ Fix for your error
    TRANS_DIR: Path = TRANSCRIPTS_DIR

    # ── Google Docs ──────────────────────────────────────
    GOOGLE_CREDENTIALS_PATH: str = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

    def __init__(self):
        # Create folders
        for d in [self.RECORDINGS_DIR, self.TRANSCRIPTS_DIR, self.SUMMARIES_DIR]:
            d.mkdir(parents=True, exist_ok=True)

        self.TRANS_DIR.mkdir(parents=True, exist_ok=True)

        # Logging
        logging.basicConfig(level=getattr(logging, self.LOG_LEVEL, logging.INFO))

    def validate(self):
        errors = []
        if self.SPEECH_ENGINE == "assemblyai" and not self.ASSEMBLYAI_API_KEY:
            errors.append("ASSEMBLYAI_API_KEY is required")
        if self.SUMMARIZER == "claude" and not self.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY is required")

        if errors:
            raise ValueError("\n".join(errors))

        return True


config = Config()