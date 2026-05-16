"""Conservative table candidate detection helpers."""

from __future__ import annotations

import re

from techdoc_parser.core import FigureBlock, HeadingBlock, Page, TableBlock, TextBlock
from techdoc_parser.structure.headings import is_heading_text

_TABLE_TITLE_RE = re.compile(
    r"^TABLE\s+(?:\d+|[A-Z]-?[IVXLCDM]+|[IVXLCDM]+)\.?(?:\s+\S.+)?$",
    re.IGNORECASE,
)
_ROMAN_TABLE_LABEL_RE = re.compile(
    r"^(?:[IVXLCDM]+|[A-Z]-[IVXLCDM]+)\.\s+\S.+$",
)
_LETTERED_LIST_ITEM_RE = re.compile(r"^[a-z]\.\s+\S.+$", re.IGNORECASE)
_PAREN_NUMBERED_ITEM_RE = re.compile(r"^\(\d+\)$")
_DEFINITION_ENTRY_RE = re.compile(
    r"^\d+(?:\.\d+){2,}\s+(?P<term>[^.\n]{1,80})\.\s+(?P<body>\S.+)$"
)
_SECTION_PROSE_START_RE = re.compile(r"^\d+(?:\.\d+)+\s+\S[^.]{1,80}\.\s+\S.+$")
_NUMBERED_PROSE_START_RE = re.compile(
    r"^\d+\.\s+(?:This|These|The|DoD|Comments|Since|When|If|A|An)\b",
    re.IGNORECASE,
)
_TABLE_REFERENCE_RE = re.compile(r"\bTables?\s+[A-Z0-9][A-Z0-9.-]*\b", re.IGNORECASE)
_FIGURE_CAPTION_RE = re.compile(
    r"^Figure\s+(?:\d+|[A-Z]-?\d+)[\.:]\s+\S.+$", re.IGNORECASE
)
_FIGURE_REFERENCE_RE = re.compile(
    r"\bFigures?\s+(?:\d+|[A-Z]-?\d+)[A-Z0-9.-]*\b", re.IGNORECASE
)
_PROCESS_DIAGRAM_START_RE = re.compile(
    r"^(?:Element|Process Step|Step)\s+\d+:\s*$", re.IGNORECASE
)
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
    "specific individual item",
    "fleet or inventory",
    "why it matters",
}
_SEVERITY_ROW_TERMS = {
    "catastrophic",
    "critical",
    "frequent",
    "marginal",
    "negligible",
    "probable",
    "occasional",
    "remote",
    "improbable",
}
_KNOWN_TABLE_HEADING_LINES = {
    "probability levels",
    "severity categories",
}
_DIAGRAM_NODE_WORDS = {
    "decision",
    "end",
    "input",
    "output",
    "start",
}
_FIGURE_CONTEXT_DIAGRAM_NODE_WORDS = _DIAGRAM_NODE_WORDS | {"process"}
_FORM_LABEL_TERMS = {
    "approved",
    "by",
    "causes",
    "date",
    "description",
    "hazard",
    "id",
    "log",
    "prepared",
    "report",
    "title",
    "tracking",
}
_SECTION_PROSE_TABLE_WORDS = {
    "category",
    "description",
    "details",
    "level",
    "probability",
    "purpose",
    "severity",
    "specified",
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
    if len(lines) == 1:
        return _is_known_table_heading_line(normalized_text)
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


def is_lettered_or_numbered_list_item(text: str) -> bool:
    """Return whether text is a lettered or parenthesized numbered list item."""
    lines = _non_empty_lines(text)
    if not lines:
        return False
    if _LETTERED_LIST_ITEM_RE.match(lines[0]):
        return True
    parenthesized_markers = sum(
        1 for line in lines if _PAREN_NUMBERED_ITEM_RE.match(line)
    )
    if parenthesized_markers >= 2:
        return True
    return parenthesized_markers == 1 and len(lines) <= 3


def is_definition_entry_text(text: str) -> bool:
    """Return whether text looks like a numbered glossary definition entry."""
    normalized_text = _normalize_for_match(text)
    match = _DEFINITION_ENTRY_RE.match(normalized_text)
    if match is None:
        return False
    if is_table_caption_text(normalized_text) or _has_structured_table_layout(text):
        return False

    term = match.group("term")
    body = match.group("body")
    term_words = term.split()
    body_words = body.split()
    if not term_words or len(term_words) > 8 or len(body_words) < 5:
        return False

    lowercase_words = sum(1 for word in body_words if word[:1].islower())
    lowercase_ratio = lowercase_words / len(body_words)
    return lowercase_ratio >= 0.35 and any(mark in body for mark in ".;:,")


def is_table_reference_paragraph(text: str) -> bool:
    """Return whether prose merely references a table without being table data."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text or is_table_caption_text(normalized_text):
        return False
    return _TABLE_REFERENCE_RE.search(normalized_text) is not None and not (
        _has_structured_table_layout(text)
    )


def is_figure_caption_or_reference_text(text: str) -> bool:
    """Return whether text is a figure caption or figure-reference paragraph."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text or is_table_caption_text(normalized_text):
        return False
    if _FIGURE_CAPTION_RE.match(normalized_text):
        return True
    return _FIGURE_REFERENCE_RE.search(normalized_text) is not None and not (
        _has_structured_table_layout(text)
    )


def is_process_diagram_label_text(text: str) -> bool:
    """Return whether text looks like a short process-flow node label."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text or is_table_caption_text(normalized_text):
        return False
    if _has_structured_table_layout(text):
        return False

    lines = _non_empty_lines(text)
    if not lines:
        return False
    if _PROCESS_DIAGRAM_START_RE.match(lines[0]):
        return 2 <= len(lines) <= 4 and all(
            _is_short_title_line(line) for line in lines
        )
    return _is_compact_diagram_keyword_cluster(lines)


def is_form_or_template_label_group_text(text: str) -> bool:
    """Return whether text looks like compact form/template labels."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text or is_table_caption_text(normalized_text):
        return False
    if _has_structured_table_layout(text):
        return False

    lines = _non_empty_lines(text)
    if not 3 <= len(lines) <= 8:
        return False
    if not all(_is_short_title_line(line) for line in lines):
        return False

    words = [
        word.casefold() for line in lines for word in re.findall(r"[A-Za-z]+", line)
    ]
    if not words:
        return False
    form_label_words = sum(1 for word in words if word in _FORM_LABEL_TERMS)
    return form_label_words / len(words) >= 0.75


def is_section_prose_with_table_like_words(text: str) -> bool:
    """Return whether numbered section prose only mentions table-like terms."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text or is_table_caption_text(normalized_text):
        return False
    if _has_structured_table_layout(text):
        return False
    if _SECTION_PROSE_START_RE.match(normalized_text) is None:
        return False

    lower = normalized_text.casefold()
    if not any(word in lower for word in _SECTION_PROSE_TABLE_WORDS):
        return False

    words = normalized_text.split()
    lowercase_words = sum(1 for word in words if word[:1].islower())
    lowercase_ratio = lowercase_words / len(words) if words else 0.0
    return lowercase_ratio >= 0.35 and any(mark in normalized_text for mark in ".;:,")


def should_reject_table_candidate(text: str) -> bool:
    """Return whether a table candidate should be rejected as a false positive."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text:
        return True
    if _TOC_DOT_LEADER_RE.search(normalized_text):
        return True
    if "http://" in normalized_text or "https://" in normalized_text:
        return True
    if normalized_text.casefold().startswith("source:"):
        return True
    if is_table_caption_text(normalized_text):
        return False
    if is_definition_entry_text(text):
        return True
    if is_table_reference_paragraph(text):
        return True
    if is_figure_caption_or_reference_text(text):
        return True
    if is_process_diagram_label_text(text):
        return True
    if is_form_or_template_label_group_text(text):
        return True
    if is_section_prose_with_table_like_words(text):
        return True
    if is_lettered_or_numbered_list_item(text):
        return True
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
        if should_suppress_table_candidate_due_to_figure_context(text_block, page):
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


def has_figure_caption_on_page(page: Page) -> bool:
    """Return whether the page has figure candidate blocks."""
    return any(isinstance(block, FigureBlock) for block in page.blocks)


def is_likely_figure_internal_text(text: str) -> bool:
    """Return whether text looks like labels inside a figure or diagram."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text or _has_strong_table_evidence(text):
        return False
    if is_process_diagram_label_text(text) or is_form_or_template_label_group_text(
        text
    ):
        return True
    lines = _non_empty_lines(text)
    return _is_compact_figure_context_diagram_keyword_cluster(
        lines
    ) or _has_repeated_label_prefix(lines)


def is_near_figure_caption(text_block: TextBlock, page: Page) -> bool:
    """Return whether a text block is plausibly adjacent to a figure caption."""
    text_bbox = text_block.source.bbox if text_block.source is not None else None
    if text_bbox is None:
        return False

    vertical_window = max((page.height or 0.0) * 0.45, 180.0)
    for figure_block in _figure_blocks_for_page(page):
        caption_bbox = (
            figure_block.source.bbox if figure_block.source is not None else None
        )
        if caption_bbox is None:
            continue
        vertical_gap = min(
            abs(text_bbox.y1 - caption_bbox.y0),
            abs(caption_bbox.y1 - text_bbox.y0),
        )
        overlaps_horizontally = text_bbox.x0 <= caption_bbox.x1 and (
            caption_bbox.x0 <= text_bbox.x1
        )
        if vertical_gap <= vertical_window and overlaps_horizontally:
            return True
    return False


def should_suppress_table_candidate_due_to_figure_context(
    text_block: TextBlock,
    page: Page,
) -> bool:
    """Return whether figure context should prevent table candidate creation."""
    if not has_figure_caption_on_page(page):
        return False
    text = text_block.normalized_text or text_block.text
    if text is None or not is_likely_figure_internal_text(text):
        return False
    if _has_strong_table_evidence(text):
        return False
    if is_near_figure_caption(text_block, page):
        return True
    return not _has_usable_figure_context_bbox(text_block, page)


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


def _is_known_table_heading_line(text: str) -> bool:
    return text.casefold() in _KNOWN_TABLE_HEADING_LINES


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
    if second_line.isdigit() or second_line.casefold() in {"i", "ii", "iii", "iv"}:
        return True
    return len(second_line) == 1 and second_line.isalpha() and second_line.isupper()


def _is_severity_row_fragment(lines: list[str]) -> bool:
    if not _is_label_value_row(lines[:2]):
        return False
    return any(len(line.split()) >= 4 for line in lines[2:])


def _has_structured_table_layout(text: str) -> bool:
    lines = _non_empty_lines(text)
    if _count_column_like_lines(lines) >= 2:
        return True
    if _has_compact_vertical_header(lines):
        return True
    return _has_known_table_row_fragment(lines)


def _has_strong_table_evidence(text: str) -> bool:
    normalized_text = _normalize_for_match(text)
    if is_table_caption_text(normalized_text):
        return True
    if has_table_header_terms(text):
        return True
    lines = _non_empty_lines(text)
    if _count_column_like_lines(lines) >= 2:
        return True
    return _has_known_table_row_fragment(lines)


def _is_short_title_line(line: str) -> bool:
    words = _normalize_for_match(line.rstrip(":")).split()
    return 1 <= len(words) <= 6 and all(len(word) <= 18 for word in words)


def _is_compact_diagram_keyword_cluster(lines: list[str]) -> bool:
    if not 2 <= len(lines) <= 4:
        return False
    normalized_lines = {_normalize_for_match(line).casefold() for line in lines}
    return normalized_lines <= _DIAGRAM_NODE_WORDS


def _is_compact_figure_context_diagram_keyword_cluster(lines: list[str]) -> bool:
    if not 2 <= len(lines) <= 4:
        return False
    normalized_lines = {_normalize_for_match(line).casefold() for line in lines}
    return normalized_lines <= _FIGURE_CONTEXT_DIAGRAM_NODE_WORDS


def _has_repeated_label_prefix(lines: list[str]) -> bool:
    if len(lines) < 3:
        return False
    prefixes = [
        _normalize_for_match(line).split()[0].casefold()
        for line in lines
        if _normalize_for_match(line).split()
    ]
    if len(prefixes) != len(lines):
        return False
    return max(prefixes.count(prefix) for prefix in set(prefixes)) >= 3


def _figure_blocks_for_page(page: Page) -> list[FigureBlock]:
    return [block for block in page.blocks if isinstance(block, FigureBlock)]


def _has_any_figure_caption_bbox(page: Page) -> bool:
    return any(
        figure.source is not None and figure.source.bbox is not None
        for figure in _figure_blocks_for_page(page)
    )


def _has_usable_figure_context_bbox(text_block: TextBlock, page: Page) -> bool:
    return (
        text_block.source is not None
        and text_block.source.bbox is not None
        and _has_any_figure_caption_bbox(page)
    )


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
