"""
summarizer.py — NLP summarization and key point extraction.

Given a transcript, this module produces:
  • A concise meeting summary
  • A list of key action items
  • Important highlighted sentences
  • (Optional) speaker breakdown

Backends:
  1. HuggingFace Transformers — local, uses BART / T5 / Pegasus
  2. OpenAI GPT            — cloud, very high quality
  3. Claude (Anthropic)    — cloud, great at structured output
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from core.config import config

logger = logging.getLogger(__name__)


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class MeetingSummary:
    summary:       str
    action_items:  list[str]      = field(default_factory=list)
    key_points:    list[str]      = field(default_factory=list)
    highlights:    list[str]      = field(default_factory=list)
    word_count:    int            = 0
    model_used:    str            = ""

    def to_dict(self) -> dict:
        return {
            "summary":      self.summary,
            "action_items": self.action_items,
            "key_points":   self.key_points,
            "highlights":   self.highlights,
            "word_count":   self.word_count,
            "model_used":   self.model_used,
        }


# ── HuggingFace backend ────────────────────────────────────────────────────────

class TransformersSummarizer:
    """
    Local summarization using HuggingFace Transformers.

    Setup:
        pip install transformers torch sentencepiece
        # Model downloads automatically on first use (~1.5 GB for BART-large)
    """

    def __init__(self, model_name: str = None):
        self.model_name = model_name or config.SUMMARIZER_MODEL
        self._pipeline  = None

    def _load_pipeline(self):
        if self._pipeline is None:
            logger.info(f"Loading summarization model '{self.model_name}'...")
            from transformers import pipeline
            self._pipeline = pipeline("summarization", model=self.model_name)
            logger.info("Summarization model loaded.")

    def summarize(self, transcript: str) -> MeetingSummary:
        self._load_pipeline()

        if len(transcript.split()) < 30:
            return MeetingSummary(
                summary="Transcript too short to summarize.",
                model_used=self.model_name,
            )

        # Truncate to 1024 tokens (BART limit)
        truncated = " ".join(transcript.split()[:900])

        result = self._pipeline(
            truncated,
            max_length=200,
            min_length=40,
            do_sample=False,
        )
        summary_text = result[0]["summary_text"]

        return MeetingSummary(
            summary=summary_text,
            action_items=self._extract_action_items(transcript),
            key_points=self._extract_key_points(transcript),
            highlights=self._extract_highlights(transcript),
            word_count=len(transcript.split()),
            model_used=self.model_name,
        )

    @staticmethod
    def _extract_action_items(text: str) -> list[str]:
        """
        Heuristic extraction: sentences containing action-item keywords.
        For better results, use OpenAI/Claude backend.
        """
        action_keywords = [
            "will", "should", "need to", "must", "action:", "todo:",
            "follow up", "next step", "assign", "responsible", "deadline",
            "by next", "send", "review", "prepare", "schedule", "confirm",
        ]
        sentences = re.split(r'[.!?]\s+', text)
        items = []
        for sentence in sentences:
            s_lower = sentence.lower()
            if any(kw in s_lower for kw in action_keywords):
                clean = sentence.strip()
                if 10 < len(clean) < 200:
                    items.append(clean)
        return items[:8]  # Cap at 8

    @staticmethod
    def _extract_key_points(text: str) -> list[str]:
        """Extract sentences that mention important named entities or decisions."""
        decision_keywords = [
            "decided", "agreed", "approved", "rejected", "proposed",
            "announced", "confirmed", "discussed", "conclusion",
        ]
        sentences = re.split(r'[.!?]\s+', text)
        points = []
        for sentence in sentences:
            s_lower = sentence.lower()
            if any(kw in s_lower for kw in decision_keywords):
                clean = sentence.strip()
                if 10 < len(clean) < 200:
                    points.append(clean)
        return points[:6]

    @staticmethod
    def _extract_highlights(text: str) -> list[str]:
        """Return longer, substantive sentences as highlights."""
        sentences = re.split(r'[.!?]\s+', text)
        # Pick sentences of medium length that aren't questions
        highlights = [
            s.strip() for s in sentences
            if 50 < len(s.strip()) < 180 and "?" not in s
        ]
        return highlights[:5]


# ── spaCy-based NLP extras ─────────────────────────────────────────────────────

class SpacyExtractor:
    """
    Uses spaCy to extract named entities and noun phrases from the transcript.
    Useful for identifying people, organizations, and topics discussed.

    Setup:
        pip install spacy
        python -m spacy download en_core_web_sm
    """

    def __init__(self):
        self._nlp = None

    def _load(self):
        if self._nlp is None:
            try:
                import spacy
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")
                self._nlp = None

    def extract_entities(self, text: str) -> dict:
        self._load()
        if not self._nlp:
            return {}

        doc = self._nlp(text)
        entities = {}
        for ent in doc.ents:
            label = ent.label_
            if label not in entities:
                entities[label] = []
            if ent.text not in entities[label]:
                entities[label].append(ent.text)

        return entities

    def extract_topics(self, text: str) -> list[str]:
        """Return the most common noun chunks as topic candidates."""
        self._load()
        if not self._nlp:
            return []

        doc = self._nlp(text)
        from collections import Counter
        chunks = [chunk.text.lower() for chunk in doc.noun_chunks if len(chunk.text) > 3]
        most_common = Counter(chunks).most_common(10)
        return [c[0] for c in most_common]


# ── OpenAI backend ─────────────────────────────────────────────────────────────

class OpenAISummarizer:
    """
    High-quality summarization using GPT-4.
    Returns structured output: summary + action items + key points.

    Setup:
        pip install openai
        Set OPENAI_API_KEY in your .env
    """

    PROMPT_TEMPLATE = """You are an expert meeting assistant. Analyze the following meeting transcript and produce structured notes.

TRANSCRIPT:
{transcript}

Respond ONLY with valid JSON in this exact format:
{{
  "summary": "2-3 sentence overview of the meeting",
  "action_items": ["action 1", "action 2", ...],
  "key_points": ["key point 1", "key point 2", ...],
  "highlights": ["important quote or sentence 1", ...]
}}"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.OPENAI_KEY

    def summarize(self, transcript: str) -> MeetingSummary:
        import json
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

        client = OpenAI(api_key=self.api_key)
        prompt = self.PROMPT_TEMPLATE.format(transcript=transcript[:8000])

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        try:
            data = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            data = {"summary": response.choices[0].message.content}

        return MeetingSummary(
            summary=data.get("summary", ""),
            action_items=data.get("action_items", []),
            key_points=data.get("key_points", []),
            highlights=data.get("highlights", []),
            word_count=len(transcript.split()),
            model_used="gpt-4o-mini",
        )


# ── Claude backend ─────────────────────────────────────────────────────────────

class ClaudeSummarizer:
    """
    High-quality summarization using Anthropic's Claude.

    Setup:
        pip install anthropic
        Set ANTHROPIC_API_KEY in your .env
    """

    PROMPT_TEMPLATE = """Analyze this meeting transcript and return structured notes as JSON only (no markdown, no explanation).

TRANSCRIPT:
{transcript}

JSON format:
{{
  "summary": "2-3 sentence overview",
  "action_items": ["action 1", "action 2"],
  "key_points": ["key point 1", "key point 2"],
  "highlights": ["important sentence 1"]
}}"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.ANTHROPIC_KEY

    def summarize(self, transcript: str) -> MeetingSummary:
        import json
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic not installed. Run: pip install anthropic")

        client  = anthropic.Anthropic(api_key=self.api_key)
        prompt  = self.PROMPT_TEMPLATE.format(transcript=transcript[:8000])
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            data = json.loads(message.content[0].text)
        except json.JSONDecodeError:
            data = {"summary": message.content[0].text}

        return MeetingSummary(
            summary=data.get("summary", ""),
            action_items=data.get("action_items", []),
            key_points=data.get("key_points", []),
            highlights=data.get("highlights", []),
            word_count=len(transcript.split()),
            model_used="claude-sonnet-4-20250514",
        )


# ── Factory ────────────────────────────────────────────────────────────────────

def get_summarizer(engine: str = None):
    """Return the configured summarization backend."""
    engine = engine or config.SUMMARIZER
    if engine == "transformers":
        return TransformersSummarizer()
    elif engine == "openai":
        return OpenAISummarizer()
    elif engine == "claude":
        return ClaudeSummarizer()
    else:
        raise ValueError(f"Unknown summarizer: '{engine}'. Choose: transformers, openai, claude")
