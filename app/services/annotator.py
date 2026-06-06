from docx import Document
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

from app.models import ChapterAnalysis
from app.services.chapter_parser import Chapter
from app.services.docx_helpers import (
    BLOCKQUOTE_COLOR,
    CATEGORY_COLORS,
    EMPHASIS_COLOR,
    highlight_in_range,
)


def _find_insertion_paragraph(
    paragraphs: list[Paragraph],
    start_idx: int,
    end_idx: int,
    anchor: str | None,
) -> int:
    if end_idx <= start_idx:
        return max(0, start_idx)

    if anchor:
        for idx in range(start_idx, end_idx):
            if anchor in paragraphs[idx].text:
                return idx

    for idx in range(end_idx - 1, start_idx - 1, -1):
        if paragraphs[idx].text.strip():
            return idx

    return max(0, end_idx - 1)


def _insert_closing_heading(
    paragraphs: list[Paragraph],
    after_idx: int,
    heading_text: str,
) -> None:
    if after_idx < 0 or after_idx >= len(paragraphs):
        return

    ref = paragraphs[after_idx]
    new_p = OxmlElement("w:p")
    ref._p.addnext(new_p)
    new_paragraph = Paragraph(new_p, ref._parent)

    for style_name in ("Heading 2", "Heading2", "heading 2"):
        try:
            new_paragraph.style = style_name
            break
        except KeyError:
            continue

    new_paragraph.add_run(heading_text)


def _apply_chapter_annotations(
    paragraphs: list[Paragraph],
    chapter: Chapter,
    analysis: ChapterAnalysis,
    closing_heading: str,
) -> None:
    start = chapter.start_para_idx
    end = chapter.end_para_idx

    for item in analysis.review_items:
        highlight_in_range(
            paragraphs,
            start,
            end,
            item.text,
            CATEGORY_COLORS[item.category],
        )

    if chapter.is_odd:
        if analysis.emphasis_sentence:
            highlight_in_range(
                paragraphs,
                start,
                end,
                analysis.emphasis_sentence,
                EMPHASIS_COLOR,
            )
        if analysis.blockquote_sentence:
            highlight_in_range(
                paragraphs,
                start,
                end,
                analysis.blockquote_sentence,
                BLOCKQUOTE_COLOR,
            )

    insert_after = _find_insertion_paragraph(paragraphs, start, end, analysis.closing_anchor)
    _insert_closing_heading(paragraphs, insert_after, closing_heading)


def process_document(
    input_path: str,
    output_path: str,
    analyses: list[tuple[Chapter, ChapterAnalysis]],
    closing_heading: str,
) -> None:
    document = Document(input_path)
    paragraphs = list(document.paragraphs)

    for chapter, analysis in analyses:
        _apply_chapter_annotations(paragraphs, chapter, analysis, closing_heading)

    document.save(output_path)
