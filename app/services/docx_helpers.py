import re

from docx.enum.text import WD_COLOR_INDEX
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from app.models import ReviewCategory


CATEGORY_COLORS: dict[ReviewCategory, WD_COLOR_INDEX] = {
    ReviewCategory.SPELLING: WD_COLOR_INDEX.YELLOW,
    ReviewCategory.UNUSUAL: WD_COLOR_INDEX.TURQUOISE,
    ReviewCategory.TYPOGRAPHY: WD_COLOR_INDEX.BRIGHT_GREEN,
}

EMPHASIS_COLOR = WD_COLOR_INDEX.PINK
BLOCKQUOTE_COLOR = WD_COLOR_INDEX.GRAY_25


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _build_char_map(paragraph: Paragraph) -> list[tuple[int, int]]:
    mapping: list[tuple[int, int]] = []
    for run_idx, run in enumerate(paragraph.runs):
        for char_idx, _ in enumerate(run.text):
            mapping.append((run_idx, char_idx))
    return mapping


def _find_phrase_span(paragraph_text: str, phrase: str) -> tuple[int, int] | None:
    if not phrase or not phrase.strip():
        return None

    direct = paragraph_text.find(phrase)
    if direct != -1:
        return direct, direct + len(phrase)

    normalized_para = _normalize_whitespace(paragraph_text)
    normalized_phrase = _normalize_whitespace(phrase)
    if not normalized_phrase:
        return None

    norm_start = normalized_para.find(normalized_phrase)
    if norm_start == -1:
        return None

    # Map normalized offset back to original text (best-effort for MVP).
    pattern = re.escape(normalized_phrase).replace(r"\ ", r"\s+")
    match = re.search(pattern, paragraph_text, flags=re.IGNORECASE)
    if match:
        return match.start(), match.end()

    return None


def highlight_phrase_in_paragraph(
    paragraph: Paragraph,
    phrase: str,
    color: WD_COLOR_INDEX,
) -> bool:
    paragraph_text = paragraph.text
    span = _find_phrase_span(paragraph_text, phrase)
    if span is None:
        return False

    start, end = span
    char_map = _build_char_map(paragraph)

    if not char_map or end > len(char_map):
        return False

    run_indices: set[int] = set()
    for position in range(start, end):
        run_indices.add(char_map[position][0])

    for run_idx in run_indices:
        paragraph.runs[run_idx].font.highlight_color = color

    return True


def add_annotation_note(paragraph: Paragraph, note: str) -> None:
    if not note:
        return
    run: Run = paragraph.add_run(f" [{note}]")
    run.font.italic = True
    run.font.highlight_color = WD_COLOR_INDEX.GRAY_25


def highlight_in_range(
    paragraphs: list[Paragraph],
    start_idx: int,
    end_idx: int,
    phrase: str,
    color: WD_COLOR_INDEX,
    note: str = "",
) -> bool:
    for idx in range(start_idx, end_idx):
        if highlight_phrase_in_paragraph(paragraphs[idx], phrase, color):
            if note:
                add_annotation_note(paragraphs[idx], note)
            return True
    return False
