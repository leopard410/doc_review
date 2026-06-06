from enum import Enum

from pydantic import BaseModel, Field


class ReviewCategory(str, Enum):
    SPELLING = "spelling"
    UNUSUAL = "unusual"
    TYPOGRAPHY = "typography"


class ReviewItem(BaseModel):
    text: str
    category: ReviewCategory


class ChapterAnalysis(BaseModel):
    review_items: list[ReviewItem] = Field(default_factory=list)
    emphasis_sentence: str | None = Field(
        default=None,
        description="Sentence suitable for emphasis (odd chapters only)",
    )
    blockquote_sentence: str | None = Field(
        default=None,
        description="Sentence suitable for block quote (odd chapters only)",
    )
    closing_anchor: str | None = Field(
        default=None,
        description="Short text snippet near where the closing heading should be inserted",
    )
