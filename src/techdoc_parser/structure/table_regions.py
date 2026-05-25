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

_MAX_TABLE_GAP = 80.0
_MAX_PARAGRAPH_GAP = 55.0
_LETTERED_BODY_PARAGRAPH_RE = re.compile(r"^[a-z]\.\s+\S.+$", re.IGNORECASE)


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
        if isinstance(block, HeadingBlock | FigureBlock):
            break
        if isinstance(block, TableBlock):
            if _is_table_caption_block(block):
                break
            if _vertical_gap(last_related_block, block) > _MAX_TABLE_GAP:
                break
            grouped_blocks.append(block)
            grouped_source_ids.update(_source_text_ids(block))
            last_related_block = block
            continue
        if not isinstance(block, ParagraphBlock):
            continue

        if _source_text_ids(block) & grouped_source_ids:
            continue
        if _vertical_gap(last_related_block, block) > _MAX_PARAGRAPH_GAP:
            break
        if _should_include_paragraph_fragment(
            ordered_blocks=ordered_blocks,
            paragraph=block,
        ):
            grouped_blocks.append(block)
            grouped_source_ids.update(_source_text_ids(block))
            last_related_block = block
            continue
        break

    return grouped_blocks


def _should_include_paragraph_fragment(
    ordered_blocks: list[Block],
    paragraph: ParagraphBlock,
) -> bool:
    if _is_body_paragraph_stop(paragraph):
        return False
    if _is_short_row_or_cell_fragment(paragraph):
        return True
    return _is_between_table_blocks(ordered_blocks, paragraph)


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
    text = "\n".join(
        _block_text(block) for block in grouped_blocks if _block_text(block)
    )
    normalized_text = "\n".join(_normalized_texts(grouped_blocks))
    rows = [[line] for line in _non_empty_lines(normalized_text)]

    source_text_block_ids: list[str] = []
    source_table_block_ids: list[str] = []
    source_paragraph_block_ids: list[str] = []
    for block in grouped_blocks:
        if isinstance(block, TableBlock):
            source_table_block_ids.append(block.id)
        if isinstance(block, ParagraphBlock):
            source_paragraph_block_ids.append(block.id)
        for source_text_id in _source_text_ids(block):
            if source_text_id not in source_text_block_ids:
                source_text_block_ids.append(source_text_id)

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


def _is_body_paragraph_stop(block: ParagraphBlock) -> bool:
    normalized_text = _block_normalized_text(block)
    if not normalized_text:
        return True
    return _LETTERED_BODY_PARAGRAPH_RE.match(normalized_text) is not None


def _is_short_row_or_cell_fragment(block: ParagraphBlock) -> bool:
    lines = _non_empty_lines(_block_normalized_text(block))
    if not lines or len(lines) > 4:
        return False
    words = " ".join(lines).split()
    if not words or len(words) > 12:
        return False
    return not any(line.endswith((".", "?", "!")) for line in lines)


def _source_text_ids(block: Block) -> set[str]:
    if isinstance(block, TableBlock | ParagraphBlock):
        return set(block.source_text_block_ids)
    return set()


def _block_text(block: Block) -> str:
    return block.text or block.normalized_text or ""


def _block_normalized_text(block: Block) -> str:
    return block.normalized_text or block.text or ""


def _normalized_texts(blocks: list[Block]) -> list[str]:
    return [text for block in blocks if (text := _block_normalized_text(block))]


def _non_empty_lines(text: str | None) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]
