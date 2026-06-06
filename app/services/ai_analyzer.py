import json
import re

import anthropic

from app.config import settings
from app.models import ChapterAnalysis, ReviewCategory, ReviewItem

MAX_REVIEW_ITEMS = 8
MAX_FLAG_WORDS = 3
MAX_FLAG_CHARS = 40
MAX_SENTENCE_CHARS = 220


def _build_system_prompt() -> str:
    return """You are a simple proofreading assistant. Flag only small issues for human review.

Return ONLY valid JSON:
{
  "review_items": [
    {"text": "word or short phrase", "category": "spelling|unusual|typography"}
  ],
  "emphasis_sentence": "one sentence or null",
  "blockquote_sentence": "one sentence or null",
  "closing_anchor": "3-8 words from near chapter end or null"
}

Rules for review_items:
- Flag ONLY: likely misspellings, odd/unusual words, obvious typos (wrong punctuation, doubled letters).
- Each "text" must be 1-3 words max, copied exactly from the chapter.
- Maximum 8 items per chapter.
- Do NOT flag: story structure, repeated scenes, chapter numbers, placeholders, whole sentences, or paragraphs.
- Do NOT add explanations.

Rules for emphasis_sentence / blockquote_sentence (odd chapters only):
- Pick exactly ONE normal prose sentence each (under 25 words).
- Must appear verbatim in the chapter.
- Do not pick the opening sentence or an entire paragraph.

Rules for closing_anchor:
- A short phrase (3-8 words) from the last third of the chapter.

Do not rewrite or correct anything."""


def _build_user_prompt(
    chapter_title: str,
    chapter_text: str,
    include_emphasis: bool,
    closing_heading: str,
) -> str:
    emphasis_instruction = (
        "Odd chapter: include emphasis_sentence and blockquote_sentence."
        if include_emphasis
        else "Even chapter: set emphasis_sentence and blockquote_sentence to null."
    )

    return f"""Review this chapter.

Title: {chapter_title}
Closing heading: "{closing_heading}"
{emphasis_instruction}

Text:
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
    match = re.match(r"^(.{1,500}?[.!?])(?:\s|$)", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    if len(text) <= MAX_SENTENCE_CHARS:
        return text
    return None


def _is_valid_flag(text: str) -> bool:
    text = text.strip()
    if not text or len(text) > MAX_FLAG_CHARS:
        return False
    if text.count(".") + text.count("!") + text.count("?") > 0:
        return False
    return _word_count(text) <= MAX_FLAG_WORDS


def _is_valid_sentence(text: str | None) -> str | None:
    if not text:
        return None
    sentence = _first_sentence(str(text).strip())
    if not sentence or len(sentence) > MAX_SENTENCE_CHARS:
        return None
    if _word_count(sentence) > 25:
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
        review_items.append(
            ReviewItem(
                text=text,
                category=_parse_category(str(item.get("category", "typography"))),
            )
        )

    return ChapterAnalysis(
        review_items=review_items,
        emphasis_sentence=_is_valid_sentence(payload.get("emphasis_sentence")),
        blockquote_sentence=_is_valid_sentence(payload.get("blockquote_sentence")),
        closing_anchor=_sanitize_anchor(payload.get("closing_anchor")),
    )


def _sanitize_anchor(anchor: object) -> str | None:
    if not anchor:
        return None
    text = str(anchor).strip()
    if not text or len(text) > 60 or _word_count(text) > 8:
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
