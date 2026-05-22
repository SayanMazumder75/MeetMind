"""
config.py — Central configuration loader
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


class Config:
    # Paths
    BASE_DIR    = Path(__file__).parent.parent
    DATA_DIR    = BASE_DIR / os.getenv("DATA_DIR", "data")
    REC_DIR     = DATA_DIR / "recordings"
    TRANS_DIR   = DATA_DIR / "transcripts"
    SUMMARY_DIR = DATA_DIR / "summaries"

    # Speech Recognition
    SPEECH_ENGINE   = os.getenv("SPEECH_ENGINE", "whisper")
    WHISPER_MODEL   = os.getenv("WHISPER_MODEL", "base")
    ASSEMBLYAI_KEY  = os.getenv("ASSEMBLYAI_API_KEY", "")

    # NLP
    SUMMARIZER       = os.getenv("SUMMARIZER", "transformers")
    SUMMARIZER_MODEL = os.getenv("SUMMARIZER_MODEL", "facebook/bart-large-cnn")
    OPENAI_KEY       = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_KEY    = os.getenv("ANTHROPIC_API_KEY", "")

    # Audio
    SAMPLE_RATE         = int(os.getenv("AUDIO_SAMPLE_RATE", 16000))
    CHUNK_SECONDS       = int(os.getenv("AUDIO_CHUNK_SECONDS", 2))  # 2s chunks = fast like Google Translate
    DEVICE_INDEX        = int(os.getenv("AUDIO_DEVICE_INDEX", -1))
    SYSTEM_DEVICE_INDEX = int(os.getenv("AUDIO_SYSTEM_DEVICE_INDEX", -1))

    # Speaker diarization
    # Options: "off" | "local" (pyannote, free) | "assemblyai" (needs API key)
    SPEAKER_DIARIZATION = os.getenv("SPEAKER_DIARIZATION", "local").lower()
    HUGGINGFACE_TOKEN   = os.getenv("HUGGINGFACE_TOKEN", "")

    # App
    APP_NAME  = os.getenv("APP_NAME", "AI Meeting Notes")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def ensure_dirs(cls):
        for d in [cls.REC_DIR, cls.TRANS_DIR, cls.SUMMARY_DIR]:
            d.mkdir(parents=True, exist_ok=True)


config = Config()
config.ensure_dirs()
