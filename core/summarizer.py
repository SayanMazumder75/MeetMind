"""
core/summarizer.py — Lightweight summarization via Claude API.

Replaces the 1.5 GB HuggingFace BART model with a direct Claude API call.
Also handles Hindi/Bengali → English translation of transcripts.

Zero local model download. Works instantly.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MeetingSummary:
    summary: str
    action_items: list[str] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)   # ✅ ADD THIS
    language_detected: str = "en"
    translated: bool = False


# ── Claude summarizer (recommended) ───────────────────────────────────────────

class ClaudeSummarizer:
    """
    Summarizes meeting transcripts using the Claude API.

    Features:
    - Understands Hindi and Bengali transcripts natively
    - Translates + summarizes in one step (no extra API call)
    - Extracts action items and key points automatically
    - ~5x cheaper than running a local GPU model
    - No download, no setup — just an API key
    """

    SYSTEM_PROMPT = """You are an expert meeting notes assistant.
You receive meeting transcripts which may be in Hindi, Bengali, English, or mixed.
Your job:
1. Detect the language(s) used
2. If non-English, translate the full transcript to English first (internally)
3. Write a clear, concise summary in English (3-5 sentences)
4. Extract action items (tasks someone must do) — prefix each with "ACTION:"
5. Extract key discussion points — prefix each with "POINT:"

Format your response EXACTLY like this:
SUMMARY:
<your summary here>

ACTION_ITEMS:
ACTION: <item 1>
ACTION: <item 2>

KEY_POINTS:
POINT: <point 1>
POINT: <point 2>

If there are no action items or key points, write "None" under that section.
Always respond in English regardless of input language."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        # Uses Haiku by default — fastest + cheapest, still very accurate
        self.api_key = api_key
        self.model = model
        logger.info(f"Claude summarizer ready | model={model}")

    def summarize(self, transcript_text: str) -> MeetingSummary:
        """Summarize a transcript. Handles Hindi/Bengali automatically."""
        import anthropic

        if not transcript_text.strip():
            return MeetingSummary(summary="No transcript content to summarize.")

        client = anthropic.Anthropic(api_key=self.api_key)

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"Meeting transcript:\n\n{transcript_text}"
                }]
            )

            raw = response.content[0].text
            return self._parse_response(raw)

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return MeetingSummary(summary=f"Summarization failed: {e}")

    def translate_chunk(self, text: str, source_lang: str = "hi") -> str:
        """Translate a single transcript chunk to English (for live display)."""
        import anthropic

        lang_names = {"hi": "Hindi", "bn": "Bengali", "ta": "Tamil", "te": "Telugu"}
        lang_name = lang_names.get(source_lang, source_lang.upper())

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": f"Translate this {lang_name} text to English. Return only the translation, nothing else:\n\n{text}"
            }]
        )
        return response.content[0].text.strip()

    def _parse_response(self, raw: str) -> MeetingSummary:
        summary = ""
        action_items = []
        key_points = []

        # Extract SUMMARY section
        m = re.search(r"SUMMARY:\s*(.+?)(?=ACTION_ITEMS:|KEY_POINTS:|$)", raw, re.DOTALL)
        if m:
            summary = m.group(1).strip()

        # Extract ACTION_ITEMS
        m = re.search(r"ACTION_ITEMS:\s*(.+?)(?=KEY_POINTS:|$)", raw, re.DOTALL)
        if m:
            block = m.group(1)
            action_items = [
                line.replace("ACTION:", "").strip()
                for line in block.splitlines()
                if line.strip().startswith("ACTION:") and "None" not in line
            ]

        # Extract KEY_POINTS
        m = re.search(r"KEY_POINTS:\s*(.+?)$", raw, re.DOTALL)
        if m:
            block = m.group(1)
            key_points = [
                line.replace("POINT:", "").strip()
                for line in block.splitlines()
                if line.strip().startswith("POINT:") and "None" not in line
            ]

        return MeetingSummary(
            summary=summary or raw.strip(),
            action_items=action_items,
            key_points=key_points,
            highlights=key_points[:2]  
        )


# ── Lightweight local fallback (no heavy models) ───────────────────────────────

class SimpleSummarizer:
    """
    Minimal extractive summarizer — no API key, no downloads.
    Uses sentence scoring heuristics. Good enough for short meetings.
    For best results, use ClaudeSummarizer instead.
    """

    def summarize(self, transcript_text: str) -> MeetingSummary:
        sentences = [s.strip() for s in transcript_text.split(".") if len(s.strip()) > 20]
        # Score sentences by length + position
        scored = [(i, len(s), s) for i, s in enumerate(sentences)]
        scored.sort(key=lambda x: -x[1])
        top = sorted(scored[:3], key=lambda x: x[0])
        summary = ". ".join(s for _, _, s in top)

        # Basic action item detection
        action_keywords = ["will", "should", "must", "need to", "action", "follow up", "by tomorrow", "deadline"]
        action_items = [
            s for s in sentences
            if any(kw in s.lower() for kw in action_keywords)
        ][:5]

        return MeetingSummary(
            summary=summary or "No summary available.",
            action_items=action_items,
        )


# ── Factory ────────────────────────────────────────────────────────────────────

def get_summarizer(config=None):
    """Return the right summarizer based on config."""
    if config is None:
        from core.config import config as cfg
        config = cfg

    engine = getattr(config, "SUMMARIZER", "claude").lower()

    if engine == "claude":
        if not config.ANTHROPIC_API_KEY:
            raise ValueError("Set ANTHROPIC_API_KEY in your .env file")
        return ClaudeSummarizer(api_key=config.ANTHROPIC_API_KEY)

    elif engine == "openai":
        from core.summarizer_openai import OpenAISummarizer
        return OpenAISummarizer(api_key=config.OPENAI_API_KEY)

    elif engine in ("transformers", "simple", "none"):
        logger.warning("Using SimpleSummarizer — no Hindi/Bengali support, limited quality.")
        logger.warning("Set SUMMARIZER=claude in .env for much better results.")
        return SimpleSummarizer()

    else:
        raise ValueError(f"Unknown SUMMARIZER: {engine}. Use 'claude' or 'simple'.")