"""Conservative grouping for fragmented table candidate regions."""

from __future__ import annotations

import re

from techdoc_parser.core import (
    Block,
    BoundingBox,
    FigureBlock,
    HeadingBlock,
    Page,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
    TableRegionBlock,
)
from techdoc_parser.structure.tables import is_table_caption_text

_MAX_TABLE_GAP = 120.0
_MAX_PARAGRAPH_GAP = 70.0
_MAX_ROW_FRAGMENT_GAP = 140.0
_LETTERED_BODY_PARAGRAPH_RE = re.compile(r"^[a-z]\.\s+\S.+$", re.IGNORECASE)
_PAREN_BODY_PARAGRAPH_RE = re.compile(r"^\(\d+\)\s+\S.+$")
_MATRIX_LABEL_RE = re.compile(r"^\([A-F]\)$", re.IGNORECASE)
_ROW_LABEL_TERMS = {
    "catastrophic",
    "critical",
    "marginal",
    "negligible",
    "frequent",
    "probable",
    "occasional",
    "remote",
    "improbable",
    "eliminated",
}
_MATRIX_VALUE_TERMS = {
    "eliminated",
    "high",
    "low",
    "medium",
    "serious",
}


def create_table_region_blocks_for_page(page: Page) -> list[TableRegionBlock]:
    """Create grouped table-region candidates from table and nearby fragments."""
    ordered_blocks = _ordered_region_candidate_blocks(page)
    regions: list[TableRegionBlock] = []
    used_table_block_ids: set[str] = set()

    for index, block in enumerate(ordered_blocks):
        if not isinstance(block, TableBlock) or block.id in used_table_block_ids:
            continue
        has_caption = _is_table_caption_block(block)
        if not has_caption and not _has_adjacent_table_candidate(ordered_blocks, index):
            continue

        grouped_blocks = _collect_region_blocks(ordered_blocks, index)
        table_blocks = [
            grouped_block
            for grouped_block in grouped_blocks
            if isinstance(grouped_block, TableBlock)
        ]
        if not _should_emit_region(grouped_blocks, has_caption):
            continue

        used_table_block_ids.update(table_block.id for table_block in table_blocks)
        regions.append(
            _create_table_region_block(
                page=page,
                region_index=len(regions) + 1,
                grouped_blocks=grouped_blocks,
                caption=_block_text(block) if has_caption else None,
            )
        )

    return regions


def _ordered_region_candidate_blocks(page: Page) -> list[Block]:
    indexed_blocks = [
        (block, index)
        for index, block in enumerate(page.blocks)
        if isinstance(block, HeadingBlock | FigureBlock | ParagraphBlock | TableBlock)
    ]
    return [
        block
        for block, _index in sorted(
            indexed_blocks,
            key=lambda item: _block_sort_key(item[0], item[1]),
        )
    ]


def _collect_region_blocks(
    ordered_blocks: list[Block],
    start_index: int,
) -> list[Block]:
    grouped_blocks = [ordered_blocks[start_index]]
    grouped_source_ids = _source_text_ids(ordered_blocks[start_index])
    last_related_block = ordered_blocks[start_index]

    for block in ordered_blocks[start_index + 1 :]:
        if not should_continue_table_region(
            block=block,
            grouped_blocks=grouped_blocks,
            ordered_blocks=ordered_blocks,
            grouped_source_ids=grouped_source_ids,
            last_related_block=last_related_block,
        ):
            break

        append_unique_grouped_block(grouped_blocks, block)
        grouped_source_ids.update(_source_text_ids(block))
        if _is_table_related_block(block):
            last_related_block = block

    return grouped_blocks


def should_continue_table_region(
    *,
    block: Block,
    grouped_blocks: list[Block],
    ordered_blocks: list[Block],
    grouped_source_ids: set[str],
    last_related_block: Block,
) -> bool:
    """Return whether a block should continue the active table region."""
    if should_stop_table_region_at_block(block, grouped_blocks):
        return False
    if isinstance(block, TableBlock):
        return is_table_region_continuation_block(
            block=block,
            active_region_blocks=grouped_blocks,
            previous_block=last_related_block,
        )
    if not isinstance(block, ParagraphBlock):
        return True
    if _source_text_ids(block) & grouped_source_ids:
        return True
    return is_table_region_continuation_block(
        block=block,
        active_region_blocks=grouped_blocks,
        previous_block=last_related_block,
        ordered_blocks=ordered_blocks,
    )


def should_stop_table_region_at_block(
    block: Block,
    active_region_blocks: list[Block],
) -> bool:
    """Return whether a block is a clear boundary for the active table region."""
    if isinstance(block, HeadingBlock | FigureBlock):
        return True
    if isinstance(block, TableBlock):
        return _is_table_caption_block(block) and bool(active_region_blocks)
    if isinstance(block, ParagraphBlock):
        return is_body_paragraph_between_tables(block)
    return False


def is_table_region_continuation_block(
    *,
    block: Block,
    active_region_blocks: list[Block],
    previous_block: Block,
    ordered_blocks: list[Block] | None = None,
) -> bool:
    """Return whether a block is a conservative table-region continuation."""
    gap = _vertical_gap(previous_block, block)
    if isinstance(block, TableBlock):
        return _should_continue_with_table_block(block, active_region_blocks, gap)
    if not isinstance(block, ParagraphBlock):
        return True
    if gap > _MAX_ROW_FRAGMENT_GAP:
        return False
    if _is_table_fragment_text(_block_normalized_text(block), previous_block):
        return True
    if gap > _MAX_PARAGRAPH_GAP:
        return False
    if _is_short_row_or_cell_fragment(block):
        return True
    return ordered_blocks is not None and _is_between_table_blocks(
        ordered_blocks,
        block,
    )


def append_unique_grouped_block(grouped_blocks: list[Block], block: Block) -> None:
    """Append a grouped block unless the same block id is already present."""
    if any(grouped_block.id == block.id for grouped_block in grouped_blocks):
        return
    grouped_blocks.append(block)


def _should_include_paragraph_fragment(
    ordered_blocks: list[Block],
    paragraph: ParagraphBlock,
    previous_block: Block,
) -> bool:
    if is_body_paragraph_between_tables(paragraph):
        return False
    if is_table_row_continuation_fragment(paragraph, previous_block):
        return True
    if _is_short_row_or_cell_fragment(paragraph):
        return True
    return _is_between_table_blocks(ordered_blocks, paragraph)


def _should_continue_with_table_block(
    block: TableBlock,
    grouped_blocks: list[Block],
    gap: float,
) -> bool:
    if gap > _MAX_ROW_FRAGMENT_GAP:
        return False
    if is_table_row_continuation_fragment(block):
        return True
    if gap > _MAX_TABLE_GAP:
        return False
    region_bbox = _union_block_bboxes(grouped_blocks)
    block_bbox = _bbox_for_block(block)
    return _horizontally_aligned(region_bbox, block_bbox)


def _is_between_table_blocks(
    ordered_blocks: list[Block],
    paragraph: ParagraphBlock,
) -> bool:
    paragraph_bbox = _bbox_for_block(paragraph)
    if paragraph_bbox is None:
        return False

    has_table_above = False
    has_table_below = False
    for block in ordered_blocks:
        block_bbox = _bbox_for_block(block)
        if block_bbox is None or not isinstance(block, TableBlock):
            continue
        if block_bbox.y1 <= paragraph_bbox.y0:
            has_table_above = (
                has_table_above or paragraph_bbox.y0 - block_bbox.y1 <= _MAX_TABLE_GAP
            )
        if block_bbox.y0 >= paragraph_bbox.y1:
            has_table_below = (
                has_table_below or block_bbox.y0 - paragraph_bbox.y1 <= _MAX_TABLE_GAP
            )
            if has_table_below:
                break

    return has_table_above and has_table_below


def _has_adjacent_table_candidate(
    ordered_blocks: list[Block],
    index: int,
) -> bool:
    block = ordered_blocks[index]
    if not isinstance(block, TableBlock):
        return False
    for candidate in ordered_blocks[index + 1 :]:
        if isinstance(candidate, HeadingBlock | FigureBlock):
            return False
        if isinstance(candidate, ParagraphBlock):
            if _vertical_gap(block, candidate) > _MAX_PARAGRAPH_GAP:
                return False
            continue
        if isinstance(candidate, TableBlock):
            return _vertical_gap(block, candidate) <= _MAX_TABLE_GAP
    return False


def _should_emit_region(grouped_blocks: list[Block], has_caption: bool) -> bool:
    table_count = sum(1 for block in grouped_blocks if isinstance(block, TableBlock))
    if has_caption:
        return len(grouped_blocks) >= 2 and table_count >= 1
    return table_count >= 2


def _create_table_region_block(
    *,
    page: Page,
    region_index: int,
    grouped_blocks: list[Block],
    caption: str | None,
) -> TableRegionBlock:
    text_fragments, normalized_fragments = _deduplicated_region_fragments(
        grouped_blocks
    )
    text = "\n".join(text_fragments)
    normalized_text = "\n".join(normalized_fragments)
    rows = [[line] for line in _non_empty_lines(normalized_text)]

    source_text_block_ids: list[str] = []
    source_table_block_ids: list[str] = []
    source_paragraph_block_ids: list[str] = []
    for block in grouped_blocks:
        if isinstance(block, TableBlock):
            _append_unique_id(source_table_block_ids, block.id)
        if isinstance(block, ParagraphBlock):
            _append_unique_id(source_paragraph_block_ids, block.id)
        for source_text_id in _source_text_id_values(block):
            _append_unique_id(source_text_block_ids, source_text_id)

    return TableRegionBlock(
        id=f"page-{page.page_number}-table-region-{region_index}",
        source=_combined_source(grouped_blocks),
        text=text or None,
        normalized_text=normalized_text or None,
        caption=caption,
        rows=rows,
        source_text_block_ids=source_text_block_ids,
        source_table_block_ids=source_table_block_ids,
        source_paragraph_block_ids=source_paragraph_block_ids,
        is_candidate=True,
    )


def _combined_source(grouped_blocks: list[Block]) -> SourceLocation | None:
    sources = [block.source for block in grouped_blocks if block.source is not None]
    if not sources:
        return None

    first_source = sources[0]
    bboxes = [source.bbox for source in sources if source.bbox is not None]
    bbox = _union_bboxes(bboxes) if bboxes else None
    confidences = [
        source.confidence for source in sources if source.confidence is not None
    ]
    confidence = min(confidences) if confidences else first_source.confidence

    return SourceLocation(
        document_path=first_source.document_path,
        page_number=first_source.page_number,
        bbox=bbox,
        extraction_method=first_source.extraction_method,
        confidence=confidence,
    )


def _union_bboxes(bboxes: list[BoundingBox]) -> BoundingBox:
    return BoundingBox(
        x0=min(bbox.x0 for bbox in bboxes),
        y0=min(bbox.y0 for bbox in bboxes),
        x1=max(bbox.x1 for bbox in bboxes),
        y1=max(bbox.y1 for bbox in bboxes),
    )


def _union_block_bboxes(blocks: list[Block]) -> BoundingBox | None:
    bboxes = [bbox for block in blocks if (bbox := _bbox_for_block(block)) is not None]
    return _union_bboxes(bboxes) if bboxes else None


def _block_sort_key(block: Block, fallback_index: int) -> tuple[int, float, float, int]:
    bbox = _bbox_for_block(block)
    if bbox is None:
        return (1, float(fallback_index), 0.0, fallback_index)
    return (0, bbox.y0, bbox.x0, fallback_index)


def _bbox_for_block(block: Block) -> BoundingBox | None:
    return block.source.bbox if block.source is not None else None


def _vertical_gap(previous_block: Block, block: Block) -> float:
    previous_bbox = _bbox_for_block(previous_block)
    bbox = _bbox_for_block(block)
    if previous_bbox is None or bbox is None:
        return 0.0
    return max(0.0, bbox.y0 - previous_bbox.y1)


def _is_table_caption_block(block: TableBlock) -> bool:
    return is_table_caption_text(_block_normalized_text(block))


def is_body_paragraph_between_tables(block: ParagraphBlock) -> bool:
    """Return whether a paragraph is body prose that should stop grouping."""
    normalized_text = _block_normalized_text(block)
    return is_body_paragraph_after_table(normalized_text)


def is_body_paragraph_after_table(text: str) -> bool:
    """Return whether text looks like body prose following a table."""
    normalized_text = _normalize_text_for_match(text)
    if not normalized_text:
        return True
    if is_table_matrix_value_fragment(normalized_text):
        return False
    if is_table_row_label_fragment(normalized_text):
        return False
    if is_table_cell_description_fragment(normalized_text):
        return False
    if _LETTERED_BODY_PARAGRAPH_RE.match(normalized_text) is not None:
        return True
    if _PAREN_BODY_PARAGRAPH_RE.match(normalized_text) is not None:
        return True
    return _is_long_body_prose(normalized_text)


def is_table_row_continuation_fragment(
    block: Block,
    previous_block: Block | None = None,
) -> bool:
    """Return whether a block looks like a continuation of a table row."""
    text = _block_normalized_text(block)
    if not text:
        return False
    if isinstance(block, ParagraphBlock) and is_body_paragraph_between_tables(block):
        return False
    if is_table_row_label_fragment(text):
        return True
    if is_table_matrix_value_fragment(text):
        return True
    if is_table_cell_description_fragment(text) and previous_block is not None:
        return _is_label_value_block(previous_block) or is_table_row_label_fragment(
            _block_normalized_text(previous_block)
        )
    return previous_block is not None and _is_label_value_block(previous_block)


def is_table_row_label_fragment(text: str) -> bool:
    """Return whether text starts with a known table row label."""
    lines = _non_empty_lines(text)
    return _starts_with_known_row_label(lines)


def is_table_matrix_value_fragment(text: str) -> bool:
    """Return whether text looks like a risk-matrix row or cell fragment."""
    lines = [
        _normalize_text_for_match(line).casefold() for line in _non_empty_lines(text)
    ]
    if not lines:
        return False
    if _MATRIX_LABEL_RE.match(lines[0]) is not None:
        return len(lines) == 1 or all(
            line in _MATRIX_VALUE_TERMS or _MATRIX_LABEL_RE.match(line) is not None
            for line in lines[1:]
        )
    return all(line in _MATRIX_VALUE_TERMS for line in lines) and len(lines) >= 2


def is_table_cell_description_fragment(text: str) -> bool:
    """Return whether text looks like a prose cell within a known table row."""
    normalized_text = _normalize_text_for_match(text)
    lower = normalized_text.casefold()
    if not normalized_text:
        return False
    if _LETTERED_BODY_PARAGRAPH_RE.match(normalized_text) is not None:
        return False
    if _PAREN_BODY_PARAGRAPH_RE.match(normalized_text) is not None:
        return False
    return lower.startswith(
        (
            "could result ",
            "incapable of occurrence",
            "likely to occur",
            "so unlikely",
            "unlikely but possible",
            "will occur",
        )
    )


def _is_short_row_or_cell_fragment(block: ParagraphBlock) -> bool:
    lines = _non_empty_lines(_block_normalized_text(block))
    if not lines or len(lines) > 4:
        return False
    words = " ".join(lines).split()
    if not words or len(words) > 12:
        return False
    return not any(line.endswith((".", "?", "!")) for line in lines)


def is_duplicate_table_region_fragment(
    text: str,
    seen_fragments: set[str],
) -> bool:
    """Return whether fragment text already appears in the region."""
    key = normalize_fragment_for_dedup(text)
    return bool(key and key in seen_fragments)


def normalize_fragment_for_dedup(text: str) -> str:
    """Normalize a whole fragment for table-region deduplication."""
    return _normalize_text_for_match(text).casefold()


def _deduplicated_region_fragments(
    grouped_blocks: list[Block],
) -> tuple[list[str], list[str]]:
    text_fragments: list[str] = []
    normalized_fragments: list[str] = []
    seen_fragments: set[str] = set()

    for block in grouped_blocks:
        normalized_text = _block_normalized_text(block)
        if is_duplicate_table_region_fragment(normalized_text, seen_fragments):
            continue
        key = normalize_fragment_for_dedup(normalized_text)
        if key:
            seen_fragments.add(key)
        text = _block_text(block)
        if text:
            text_fragments.append(text)
        if normalized_text:
            normalized_fragments.append(normalized_text)

    return text_fragments, normalized_fragments


def _append_unique_id(ids: list[str], value: str) -> None:
    if value not in ids:
        ids.append(value)


def _is_table_related_block(block: Block) -> bool:
    return isinstance(block, TableBlock | ParagraphBlock)


def _horizontally_aligned(
    region_bbox: BoundingBox | None,
    block_bbox: BoundingBox | None,
) -> bool:
    if region_bbox is None or block_bbox is None:
        return True
    overlap = min(region_bbox.x1, block_bbox.x1) - max(region_bbox.x0, block_bbox.x0)
    if overlap > 0:
        return True
    return abs(region_bbox.x0 - block_bbox.x0) <= 48.0


def _starts_with_known_row_label(lines: list[str]) -> bool:
    if not lines:
        return False
    first_line = lines[0].casefold()
    return first_line in _ROW_LABEL_TERMS


def _is_label_value_block(block: Block) -> bool:
    lines = _non_empty_lines(_block_normalized_text(block))
    if len(lines) < 2 or not _starts_with_known_row_label(lines):
        return False
    value = lines[1]
    return value.isdigit() or (len(value) == 1 and value.isalpha())


def _is_long_body_prose(text: str) -> bool:
    words = text.split()
    if len(words) < 24:
        return False
    lowercase_words = sum(1 for word in words if word[:1].islower())
    lowercase_ratio = lowercase_words / len(words)
    sentence_marks = sum(text.count(mark) for mark in ".;:")
    return lowercase_ratio >= 0.45 and sentence_marks >= 2


def _is_table_fragment_text(text: str, previous_block: Block | None = None) -> bool:
    return (
        is_table_row_label_fragment(text)
        or is_table_matrix_value_fragment(text)
        or is_table_cell_description_fragment(text)
        or (
            previous_block is not None
            and is_table_row_continuation_fragment(
                Block(id="", source=None, block_type="", text=text),
                previous_block,
            )
        )
    )


def _normalize_text_for_match(text: str | None) -> str:
    return " ".join((text or "").split())


def _source_text_ids(block: Block) -> set[str]:
    return set(_source_text_id_values(block))


def _source_text_id_values(block: Block) -> list[str]:
    if isinstance(block, TableBlock | ParagraphBlock):
        return block.source_text_block_ids
    return []


def _block_text(block: Block) -> str:
    return block.text or block.normalized_text or ""


def _block_normalized_text(block: Block) -> str:
    return block.normalized_text or block.text or ""


def _non_empty_lines(text: str | None) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]
