from dataclasses import dataclass

from docx import Document
from docx.text.paragraph import Paragraph


DEFAULT_CHAPTER_STYLES = ("Heading 1", "Heading1", "heading 1", "Title")


@dataclass
class Chapter:
    index: int
    title: str
    start_para_idx: int
    end_para_idx: int

    @property
    def is_odd(self) -> bool:
        return self.index % 2 == 1


def _paragraph_style_name(paragraph: Paragraph) -> str:
    if paragraph.style and paragraph.style.name:
        return paragraph.style.name
    return ""


def _is_chapter_heading(paragraph: Paragraph, heading_styles: tuple[str, ...]) -> bool:
    style_name = _paragraph_style_name(paragraph)
    if style_name in heading_styles:
        return True
    normalized = style_name.lower().replace(" ", "")
    return normalized in {s.lower().replace(" ", "") for s in heading_styles}


def _extract_chapter_text(paragraphs: list[Paragraph], start: int, end: int) -> str:
    parts: list[str] = []
    for idx in range(start, end):
        text = paragraphs[idx].text.strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def detect_chapters(
    document: Document,
    heading_styles: tuple[str, ...] | None = None,
) -> list[Chapter]:
    styles = heading_styles or DEFAULT_CHAPTER_STYLES
    paragraphs = list(document.paragraphs)
    heading_indices = [
        idx
        for idx, paragraph in enumerate(paragraphs)
        if _is_chapter_heading(paragraph, styles)
    ]

    if not heading_indices:
        non_empty = [p.text.strip() for p in paragraphs if p.text.strip()]
        title = non_empty[0][:80] if non_empty else "Document"
        return [
            Chapter(
                index=1,
                title=title,
                start_para_idx=0,
                end_para_idx=len(paragraphs),
            )
        ]

    chapters: list[Chapter] = []
    for chapter_num, start_idx in enumerate(heading_indices, start=1):
        end_idx = (
            heading_indices[chapter_num]
            if chapter_num < len(heading_indices)
            else len(paragraphs)
        )
        title = paragraphs[start_idx].text.strip() or f"Chapter {chapter_num}"
        chapters.append(
            Chapter(
                index=chapter_num,
                title=title,
                start_para_idx=start_idx,
                end_para_idx=end_idx,
            )
        )

    return chapters


def get_chapter_text(document: Document, chapter: Chapter) -> str:
    return _extract_chapter_text(
        list(document.paragraphs),
        chapter.start_para_idx,
        chapter.end_para_idx,
    )
