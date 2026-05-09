"""Conservative table candidate detection helpers."""

from __future__ import annotations

import re

from techdoc_parser.core import HeadingBlock, Page, TableBlock, TextBlock
from techdoc_parser.structure.headings import is_heading_text

_TABLE_TITLE_RE = re.compile(
    r"^TABLE\s+(?:\d+|[A-Z]-?[IVXLCDM]+|[IVXLCDM]+)\.?(?:\s+\S.+)?$",
    re.IGNORECASE,
)
_ROMAN_TABLE_LABEL_RE = re.compile(
    r"^(?:[IVXLCDM]+|[A-Z]-[IVXLCDM]+)\.\s+\S.+$",
    re.IGNORECASE,
)
_NUMBERED_PROSE_START_RE = re.compile(
    r"^\d+\.\s+(?:This|These|The|DoD|Comments|Since|When|If|A|An)\b",
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
    "mishap result criteria",
    "probability",
    "purpose",
    "severity",
    "why it matters",
}
_SEVERITY_ROW_TERMS = {
    "catastrophic",
    "critical",
    "marginal",
    "negligible",
}


def is_table_candidate_text(text: str) -> bool:
    """Return whether text conservatively looks like a table candidate."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text:
        return False
    if should_reject_table_candidate(text):
        return False

    if is_table_caption_text(normalized_text):
        return True
    if has_table_header_terms(text):
        return True
    return has_table_like_line_structure(text)


def is_table_caption_text(text: str) -> bool:
    """Return whether text is a clear table caption or table label."""
    normalized_text = _normalize_for_match(text)
    return _is_table_title(normalized_text) or _is_roman_table_label(normalized_text)


def has_table_header_terms(text: str) -> bool:
    """Return whether compact text contains multiple table header terms."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text:
        return False
    lines = _non_empty_lines(text)
    if len(lines) > 12 or len(normalized_text) > 240:
        return False
    if _has_table_header_words(normalized_text):
        return True
    return _has_compact_vertical_header(lines)


def has_table_like_line_structure(text: str) -> bool:
    """Return whether text has conservative row-like or column-like structure."""
    lines = _non_empty_lines(text)
    if len(lines) < 2:
        return False
    if _count_column_like_lines(lines) >= 2:
        return True
    if _has_known_table_row_fragment(lines):
        return True
    return _has_multiple_short_row_like_lines(lines)


def is_long_prose_paragraph(text: str) -> bool:
    """Return whether text looks like wrapped prose instead of table content."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text:
        return False
    if is_table_caption_text(normalized_text) or has_table_header_terms(text):
        return False
    if _has_known_table_row_fragment(_non_empty_lines(text)):
        return False

    words = normalized_text.split()
    lowercase_words = sum(1 for word in words if word[:1].islower())
    lowercase_ratio = lowercase_words / len(words) if words else 0.0
    sentence_punctuation_count = sum(normalized_text.count(mark) for mark in ".;:,")
    lines = _non_empty_lines(text)
    average_line_length = (
        sum(len(line) for line in lines) / len(lines) if lines else len(normalized_text)
    )

    if _NUMBERED_PROSE_START_RE.match(normalized_text) and len(words) >= 12:
        return True
    if len(words) >= 24 and lowercase_ratio >= 0.45 and sentence_punctuation_count >= 1:
        return True
    return len(words) >= 18 and average_line_length >= 65 and lowercase_ratio >= 0.4


def should_reject_table_candidate(text: str) -> bool:
    """Return whether a table candidate should be rejected as a false positive."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text:
        return True
    if _TOC_DOT_LEADER_RE.search(normalized_text):
        return True
    if _FIGURE_CAPTION_RE.fullmatch(normalized_text):
        return True
    if "http://" in normalized_text or "https://" in normalized_text:
        return True
    if normalized_text.casefold().startswith("source:"):
        return True
    if is_table_caption_text(normalized_text):
        return False
    if is_heading_text(normalized_text):
        return True
    return is_long_prose_paragraph(text)


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


def _is_table_title(line: str) -> bool:
    return _TABLE_TITLE_RE.search(line) is not None


def _is_roman_table_label(line: str) -> bool:
    return _ROMAN_TABLE_LABEL_RE.fullmatch(line) is not None


def _has_table_header_words(text: str) -> bool:
    lower = text.casefold()
    matches = sum(1 for word in _TABLE_HEADER_WORDS if word in lower)
    return matches >= 2


def _has_compact_vertical_header(lines: list[str]) -> bool:
    if len(lines) < 3 or len(lines) > 8:
        return False
    normalized_lines = {_normalize_for_match(line).casefold() for line in lines}
    matches = sum(1 for word in _TABLE_HEADER_WORDS if word in normalized_lines)
    return matches >= 3


def _count_column_like_lines(lines: list[str]) -> int:
    return sum(1 for line in lines if re.search(r"\S(?: {2,}|\t+)\S", line))


def _has_multiple_short_row_like_lines(lines: list[str]) -> bool:
    if _looks_like_wrapped_prose_lines(lines):
        return False
    short_lines = [line for line in lines if 2 <= len(line.split()) <= 8]
    return len(lines) >= 3 and len(short_lines) >= 3


def _has_known_table_row_fragment(lines: list[str]) -> bool:
    if len(lines) == 2:
        return _is_label_value_row(lines)
    if len(lines) >= 3:
        return _is_severity_row_fragment(lines)
    return False


def _is_label_value_row(lines: list[str]) -> bool:
    first_line = _normalize_for_match(lines[0]).casefold()
    second_line = _normalize_for_match(lines[1])
    if first_line not in _SEVERITY_ROW_TERMS:
        return False
    return second_line.isdigit() or second_line.casefold() in {"i", "ii", "iii", "iv"}


def _is_severity_row_fragment(lines: list[str]) -> bool:
    if not _is_label_value_row(lines[:2]):
        return False
    return any(len(line.split()) >= 4 for line in lines[2:])


def _looks_like_wrapped_prose_lines(lines: list[str]) -> bool:
    if len(lines) < 3:
        return False
    joined_text = _normalize_for_match(" ".join(lines))
    words = joined_text.split()
    if len(words) < 18:
        return False
    lowercase_words = sum(1 for word in words if word[:1].islower())
    lowercase_ratio = lowercase_words / len(words)
    continuation_lines = sum(1 for line in lines[1:] if line[:1].islower())
    return lowercase_ratio >= 0.45 and continuation_lines >= 1


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
