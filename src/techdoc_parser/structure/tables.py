"""Conservative table candidate detection helpers."""

from __future__ import annotations

import re

from techdoc_parser.core import HeadingBlock, Page, TableBlock, TextBlock
from techdoc_parser.structure.headings import is_heading_text

_TABLE_TITLE_RE = re.compile(
    r"^TABLE\s+(?:\d+|[A-Z]-?[IVXLCDM]+|[IVXLCDM]+)\.?\s+\S.+$",
    re.IGNORECASE,
)
_ROMAN_TABLE_LABEL_RE = re.compile(
    r"^(?:[IVXLCDM]+|[A-Z]-[IVXLCDM]+)\.\s+\S.+$",
    re.IGNORECASE,
)
_FIGURE_CAPTION_RE = re.compile(r"^Figure\s+\d+[\.:]\s+\S.+$", re.IGNORECASE)
_TOC_DOT_LEADER_RE = re.compile(r"\.{5,}\s*(?:[ivxlcdm]+|\d+)$", re.IGNORECASE)
_TABLE_HEADER_WORDS = {
    "category",
    "criteria",
    "description",
    "entity",
    "key links",
    "level",
    "probability",
    "purpose",
    "severity",
    "task",
    "why it matters",
}


def is_table_candidate_text(text: str) -> bool:
    """Return whether text conservatively looks like a table candidate."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text:
        return False
    if _is_obvious_false_positive(normalized_text):
        return False

    lines = _non_empty_lines(text)
    if len(lines) == 1:
        return _is_table_title(lines[0]) or _is_roman_table_label(lines[0])

    if _has_table_header_words(normalized_text) and len(lines) >= 2:
        return True
    if _count_column_like_lines(lines) >= 2:
        return True
    return _has_multiple_short_row_like_lines(lines)


def create_table_blocks_for_page(page: Page) -> list[TableBlock]:
    """Create conservative table candidate blocks from page text blocks."""
    heading_texts = _heading_texts_for_page(page)
    tables: list[TableBlock] = []

    for text_block in page.text_blocks:
        text = text_block.text
        if text is None or _should_skip_text_block(text_block, heading_texts):
            continue
        if not is_table_candidate_text(text_block.normalized_text or text):
            continue

        rows = [[line] for line in _non_empty_lines(text_block.normalized_text or text)]
        tables.append(
            TableBlock(
                id=f"page-{page.page_number}-table-{len(tables) + 1}",
                source=text_block.source,
                text=text,
                normalized_text=text_block.normalized_text,
                rows=rows,
                source_text_block_ids=[text_block.id],
                is_candidate=True,
            )
        )

    return tables


def _should_skip_text_block(
    text_block: TextBlock,
    heading_texts: set[str],
) -> bool:
    if text_block.is_page_furniture:
        return True
    if (
        text_block.is_page_header
        or text_block.is_page_footer
        or text_block.is_page_number
    ):
        return True
    text = text_block.text
    if text is None or not text.strip():
        return True
    return _normalize_for_match(text_block.normalized_text or text) in heading_texts


def _is_obvious_false_positive(text: str) -> bool:
    if _TOC_DOT_LEADER_RE.search(text):
        return True
    if _FIGURE_CAPTION_RE.fullmatch(text):
        return True
    if is_heading_text(text):
        return True
    return len(_non_empty_lines(text)) == 1 and _looks_like_sentence(text)


def _is_table_title(line: str) -> bool:
    return _TABLE_TITLE_RE.search(line) is not None


def _is_roman_table_label(line: str) -> bool:
    return _ROMAN_TABLE_LABEL_RE.fullmatch(line) is not None


def _has_table_header_words(text: str) -> bool:
    lower = text.casefold()
    matches = sum(1 for word in _TABLE_HEADER_WORDS if word in lower)
    return matches >= 2


def _count_column_like_lines(lines: list[str]) -> int:
    return sum(1 for line in lines if re.search(r"\S(?: {2,}|\t+)\S", line))


def _has_multiple_short_row_like_lines(lines: list[str]) -> bool:
    short_lines = [line for line in lines if 2 <= len(line.split()) <= 8]
    return len(lines) >= 3 and len(short_lines) >= 3


def _looks_like_sentence(text: str) -> bool:
    words = text.split()
    if len(words) < 8:
        return False
    return text.endswith((".", "!", "?"))


def _heading_texts_for_page(page: Page) -> set[str]:
    heading_texts: set[str] = set()
    for block in page.blocks:
        if isinstance(block, HeadingBlock):
            heading_texts.add(_normalize_for_match(block.normalized_text or block.text))
    return heading_texts


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _normalize_for_match(text: str | None) -> str:
    return " ".join((text or "").split())
