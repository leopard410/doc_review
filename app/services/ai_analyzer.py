import json
import re

import anthropic

from app.config import settings
from app.models import ChapterAnalysis, ReviewCategory, ReviewItem


def _build_system_prompt() -> str:
    return """You are an editorial review assistant for manuscript proofreading.

Your job is to FLAG items for human review. You must NOT rewrite, correct, or suggest replacement text.

Return ONLY valid JSON matching this schema:
{
  "review_items": [
    {"text": "exact phrase from chapter", "category": "spelling|unusual|typography", "note": "brief reason"}
  ],
  "emphasis_sentence": "full sentence or null",
  "blockquote_sentence": "full sentence or null",
  "closing_anchor": "short phrase from near chapter end or null"
}

Rules:
- review_items: flag potential spelling mistakes, unusual/suspicious words, and typographical issues.
- Each "text" value MUST appear verbatim (or nearly verbatim) in the chapter.
- Limit review_items to the most useful 15 items per chapter.
- emphasis_sentence and blockquote_sentence: only provide when requested (odd chapters). Pick one strong sentence each.
- closing_anchor: a short distinctive phrase from the last third of the chapter, marking where a closing section heading should be inserted AFTER that point.
- Do not modify manuscript content in your output — only identify items."""


def _build_user_prompt(
    chapter_title: str,
    chapter_text: str,
    include_emphasis: bool,
    closing_heading: str,
) -> str:
    emphasis_instruction = (
        "This is an odd-numbered chapter. Include emphasis_sentence and blockquote_sentence."
        if include_emphasis
        else "This is an even-numbered chapter. Set emphasis_sentence and blockquote_sentence to null."
    )

    return f"""Analyze this chapter for editorial review.

Chapter title: {chapter_title}
Closing heading to place: "{closing_heading}"
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
    review_items: list[ReviewItem] = []
    for item in payload.get("review_items", []):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        review_items.append(
            ReviewItem(
                text=text,
                category=_parse_category(str(item.get("category", "typography"))),
                note=str(item.get("note", "")).strip(),
            )
        )

    emphasis = payload.get("emphasis_sentence")
    blockquote = payload.get("blockquote_sentence")
    anchor = payload.get("closing_anchor")

    return ChapterAnalysis(
        review_items=review_items,
        emphasis_sentence=str(emphasis).strip() if emphasis else None,
        blockquote_sentence=str(blockquote).strip() if blockquote else None,
        closing_anchor=str(anchor).strip() if anchor else None,
    )


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
            max_tokens=4096,
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
        return _coerce_analysis(payload)
