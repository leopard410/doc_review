import json
import re

import anthropic

from app.config import settings
from app.models import ChapterAnalysis, ReviewCategory, ReviewItem

MAX_REVIEW_ITEMS = 12
MAX_FLAG_WORDS = 6
MAX_FLAG_CHARS = 80
MAX_SENTENCE_CHARS = 300


def _build_system_prompt() -> str:
    return """You are an editorial review assistant for a Word manuscript.

Return ONLY valid JSON:
{
  "review_items": [
    {"text": "exact text from chapter", "category": "spelling|unusual|typography", "suggestion": "corrected spelling or null"}
  ],
  "emphasis_sentence": "one sentence or null",
  "blockquote_sentence": "one sentence or null",
  "closing_anchor": "short phrase near chapter end or null"
}

## Editorial review highlights (every chapter)
Find and flag items for human review only. Do NOT rewrite or correct text.

1. spelling — likely misspellings (e.g. "teh", "impotant"). For each, add "suggestion" with the likely correct spelling (e.g. "important"). Do NOT change the manuscript text.
2. unusual — unusual, rare, or suspicious words that may need verification (suggestion: null)
3. typography — typos, doubled spaces, wrong punctuation, stray characters (suggestion: null)

Rules:
- Each "text" must be copied EXACTLY from the chapter (same spelling and punctuation).
- Prefer single words or short phrases (1-6 words).
- Include ALL reasonable candidates you find (up to 12 per chapter).
- If the chapter is clean, return an empty review_items array.

## Editorial emphasis (odd chapters only)
Pick exactly:
- emphasis_sentence: one strong sentence suitable for typographic emphasis
- blockquote_sentence: one different sentence suitable for a block quote
Both must be single sentences copied verbatim from the chapter.

## Closing heading placement (every chapter)
- closing_anchor: a short phrase (3-10 words) from the last third of the chapter, marking where a closing section heading should be inserted after that point.

Do not add explanations. Do not rewrite the manuscript."""


def _build_user_prompt(
    chapter_title: str,
    chapter_text: str,
    include_emphasis: bool,
    closing_heading: str,
) -> str:
    if include_emphasis:
        emphasis_instruction = (
            "This is chapter 1, 3, 5, etc. (odd). "
            "You MUST provide emphasis_sentence and blockquote_sentence."
        )
    else:
        emphasis_instruction = (
            "This is an even chapter. Set emphasis_sentence and blockquote_sentence to null."
        )

    return f"""Analyze this chapter for editorial review.

Chapter: {chapter_title}
Closing heading to insert: "{closing_heading}"
{emphasis_instruction}

Chapter text:
---
{chapter_text}
---"""


def _parse_category(raw: str) -> ReviewCategory:
    normalized = raw.strip().lower()
    if normalized in {"spelling", "spell", "misspelling"}:
        return ReviewCategory.SPELLING
    if normalized in {"unusual", "suspicious", "word"}:
        return ReviewCategory.UNUSUAL
    return ReviewCategory.TYPOGRAPHY


def _word_count(text: str) -> int:
    return len(text.split())


def _first_sentence(text: str) -> str | None:
    text = text.strip()
    if not text:
        return None
    match = re.match(r"^(.{1,500}?[.!?\"'])(?:\s|$)", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip().strip("\"'")
    if len(text) <= MAX_SENTENCE_CHARS and _word_count(text) <= 35:
        return text
    return None


def _is_valid_flag(text: str) -> bool:
    text = text.strip()
    if not text or len(text) > MAX_FLAG_CHARS:
        return False
    if _word_count(text) > MAX_FLAG_WORDS:
        return False
    # Reject full sentences (likely over-flagging), allow words with apostrophes/hyphens.
    if text.endswith((".", "!", "?")) and _word_count(text) > 4:
        return False
    return True


def _is_valid_sentence(text: str | None) -> str | None:
    if not text:
        return None
    sentence = _first_sentence(str(text).strip())
    if not sentence or len(sentence) > MAX_SENTENCE_CHARS:
        return None
    if _word_count(sentence) > 35:
        return None
    return sentence


def _extract_json_payload(raw_text: str) -> dict:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("AI response did not contain valid JSON") from None
        return json.loads(match.group())


def _coerce_analysis(payload: dict) -> ChapterAnalysis:
    seen: set[str] = set()
    review_items: list[ReviewItem] = []

    for item in payload.get("review_items", []):
        if not isinstance(item, dict) or len(review_items) >= MAX_REVIEW_ITEMS:
            continue
        text = str(item.get("text", "")).strip()
        if not _is_valid_flag(text):
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        category = _parse_category(str(item.get("category", "typography")))
        suggestion = _sanitize_suggestion(item.get("suggestion"), text, category)
        review_items.append(
            ReviewItem(text=text, category=category, suggestion=suggestion)
        )

    return ChapterAnalysis(
        review_items=review_items,
        emphasis_sentence=_is_valid_sentence(payload.get("emphasis_sentence")),
        blockquote_sentence=_is_valid_sentence(payload.get("blockquote_sentence")),
        closing_anchor=_sanitize_anchor(payload.get("closing_anchor")),
    )


def _sanitize_suggestion(
    raw: object,
    flagged_text: str,
    category: ReviewCategory,
) -> str | None:
    if category != ReviewCategory.SPELLING or not raw:
        return None
    suggestion = str(raw).strip()
    if not suggestion or len(suggestion) > 40:
        return None
    if suggestion.lower() == flagged_text.lower():
        return None
    return suggestion


def _sanitize_anchor(anchor: object) -> str | None:
    if not anchor:
        return None
    text = str(anchor).strip()
    if not text or len(text) > 80 or _word_count(text) > 10:
        return None
    return text


class AnthropicAnalyzer:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or settings.anthropic_api_key
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model or settings.anthropic_model

    def analyze_chapter(
        self,
        chapter_title: str,
        chapter_text: str,
        *,
        include_emphasis: bool,
        closing_heading: str,
    ) -> ChapterAnalysis:
        if not chapter_text.strip():
            return ChapterAnalysis()

        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=_build_system_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": _build_user_prompt(
                        chapter_title,
                        chapter_text,
                        include_emphasis,
                        closing_heading,
                    ),
                }
            ],
        )

        raw_blocks = [block.text for block in message.content if block.type == "text"]
        payload = _extract_json_payload("\n".join(raw_blocks))
        analysis = _coerce_analysis(payload)

        if not include_emphasis:
            analysis.emphasis_sentence = None
            analysis.blockquote_sentence = None

        return analysis
