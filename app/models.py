from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ReviewCategory(str, Enum):
    SPELLING = "spelling"
    UNUSUAL = "unusual"
    TYPOGRAPHY = "typography"


class ReviewItem(BaseModel):
    text: str = Field(description="Exact phrase from the chapter to flag")
    category: ReviewCategory
    note: str = Field(default="", description="Brief reason for human review")


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


class ProcessOptions(BaseModel):
    closing_heading: str | None = None
    chapter_heading_styles: list[str] | None = Field(
        default=None,
        description="Word heading style names that mark chapter boundaries (e.g. Heading 1)",
    )
