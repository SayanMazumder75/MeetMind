"""
speaker_diarization.py — Local speaker diarization using pyannote.audio.

Identifies WHO is speaking in each audio chunk and labels them
Speaker 1, Speaker 2, etc. consistently across the session.

Setup:
    1. pip install pyannote.audio torch
    2. Accept conditions at https://huggingface.co/pyannote/speaker-diarization-3.1
    3. Get a free HuggingFace token at https://huggingface.co/settings/tokens
    4. Set HUGGINGFACE_TOKEN=your_token in .env

How it works:
    - Maintains voice "embeddings" (fingerprints) for each speaker seen so far
    - Each new audio chunk is compared against known speaker fingerprints
    - If it matches a known speaker → reuse their label (Speaker 1, 2...)
    - If it's a new voice → assign the next available label
"""

import logging
import threading
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)


class SpeakerDiarizer:
    """
    Assigns consistent speaker labels across a meeting session.
    Uses pyannote.audio for voice embedding + cosine similarity matching.
    """

    def __init__(self, hf_token: str = None, similarity_threshold: float = 0.75):
        self.hf_token   = hf_token
        self.threshold  = similarity_threshold  # how similar to match same speaker
        self._model     = None
        self._lock      = threading.Lock()

        # Known speakers: list of (label, embedding)
        self._speakers: list[tuple[str, np.ndarray]] = []
        self._speaker_count = 0

    def _load_model(self):
        """Lazy-load pyannote embedding model on first use."""
        if self._model is not None:
            return True
        try:
            from pyannote.audio import Inference, Model
            import torch

            logger.info("Loading speaker embedding model (first run downloads ~300 MB)...")
            token = self.hf_token or _get_token_from_env()

            model = Model.from_pretrained(
                "pyannote/embedding",
                use_auth_token=token,
            )
            self._model = Inference(model, window="whole")
            logger.info("Speaker embedding model loaded.")
            return True
        except ImportError:
            logger.warning("pyannote.audio not installed. Run: pip install pyannote.audio")
            return False
        except Exception as e:
            logger.warning(f"Could not load speaker model: {e}")
            return False

    def identify_speaker(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Given an audio chunk, return a consistent speaker label like 'Speaker 1'.
        Falls back to 'Unknown' if the model isn't available.
        """
        if not self._load_model():
            return "Unknown"

        # Need at least 1 second of audio for reliable embedding
        if len(audio) < sample_rate:
            return "Unknown"

        embedding = self._get_embedding(audio, sample_rate)
        if embedding is None:
            return "Unknown"

        with self._lock:
            return self._match_or_create_speaker(embedding)

    def _get_embedding(self, audio: np.ndarray, sample_rate: int) -> Optional[np.ndarray]:
        """Extract a voice embedding (fingerprint) from the audio."""
        try:
            import torch
            from pyannote.core import Segment
            from pyannote.audio.core.io import AudioFile

            # pyannote expects a dict with waveform tensor + sample_rate
            waveform = torch.tensor(audio).unsqueeze(0).float()  # shape: (1, samples)
            audio_file = {"waveform": waveform, "sample_rate": sample_rate}

            embedding = self._model(audio_file)
            return embedding.squeeze()
        except Exception as e:
            logger.debug(f"Embedding error: {e}")
            return None

    def _match_or_create_speaker(self, embedding: np.ndarray) -> str:
        """
        Compare embedding against known speakers.
        Returns existing label if similarity > threshold, else creates new speaker.
        """
        best_score  = -1.0
        best_label  = None

        for label, known_embedding in self._speakers:
            score = _cosine_similarity(embedding, known_embedding)
            if score > best_score:
                best_score = score
                best_label = label

        if best_score >= self.threshold and best_label:
            # Update the stored embedding with a running average for drift adaptation
            idx = next(i for i, (l, _) in enumerate(self._speakers) if l == best_label)
            old_emb = self._speakers[idx][1]
            updated = (old_emb * 0.8 + embedding * 0.2)  # exponential moving average
            self._speakers[idx] = (best_label, updated)
            return best_label
        else:
            # New speaker
            self._speaker_count += 1
            label = f"Speaker {self._speaker_count}"
            self._speakers.append((label, embedding.copy()))
            logger.info(f"New speaker detected: {label}")
            return label

    def rename_speaker(self, old_label: str, new_name: str) -> None:
        """Allow the user to rename 'Speaker 1' to 'Anushka' etc."""
        with self._lock:
            self._speakers = [
                (new_name if label == old_label else label, emb)
                for label, emb in self._speakers
            ]

    def get_speaker_list(self) -> list[str]:
        """Return all detected speaker labels so far."""
        with self._lock:
            return [label for label, _ in self._speakers]

    def reset(self) -> None:
        """Clear all speaker history (call at session start)."""
        with self._lock:
            self._speakers = []
            self._speaker_count = 0


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors. Returns value in [-1, 1]."""
    a = a.flatten()
    b = b.flatten()
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _get_token_from_env() -> Optional[str]:
    import os
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).parent.parent / ".env")
    return os.getenv("HUGGINGFACE_TOKEN", "")
