"""Semantic block filtering helpers for export/RAG views."""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from techdoc_parser.core import (
    Block,
    FigureBlock,
    FormulaBlock,
    HeadingBlock,
    Page,
    ParagraphBlock,
    TableBlock,
    TableRegionBlock,
    TextBlock,
)


@runtime_checkable
class _HasSourceTextBlockIds(Protocol):
    source_text_block_ids: list[str]


_SPECIFIC_SEMANTIC_TYPES = (
    HeadingBlock,
    TableBlock,
    TableRegionBlock,
    FigureBlock,
    FormulaBlock,
)
_SEMANTIC_TYPES = (
    HeadingBlock,
    ParagraphBlock,
    TableBlock,
    TableRegionBlock,
    FigureBlock,
    FormulaBlock,
)
_DATE_ONLY_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
_DOCUMENT_ID_RE = re.compile(r"^(?:[A-Z]{2,}-STD-\d+[A-Z]?|\d{4}\.\d+[A-Z]?)$")
_APPENDIX_HEADER_RE = re.compile(r"^Appendix\s+[A-Z]$", re.IGNORECASE)
_APPENDIX_PAGE_RE = re.compile(r"^[A-Z]-\d+$")
_CHANGE_NOTICE_RE = re.compile(r"^w/CHANGE\s+\d+$", re.IGNORECASE)


def get_semantic_blocks_for_page(page: Page) -> list[Block]:
    """Return semantic page blocks without raw text or duplicate paragraphs."""
    specific_source_ids: set[str] = set()
    table_region_source_ids: set[str] = set()
    heading_texts: set[str] = set()

    for block in page.blocks:
        if should_exclude_from_semantic_output(block):
            continue
        if isinstance(block, _SPECIFIC_SEMANTIC_TYPES):
            specific_source_ids.update(get_block_source_text_ids(block))
        if isinstance(block, TableRegionBlock):
            table_region_source_ids.update(get_block_source_text_ids(block))
        if isinstance(block, HeadingBlock):
            heading_text = get_block_normalized_text(block)
            if heading_text:
                heading_texts.add(heading_text)

    semantic_blocks_with_index: list[tuple[Block, int]] = []
    for fallback_index, block in enumerate(page.blocks):
        if should_exclude_from_semantic_output(block):
            continue
        if not isinstance(block, _SEMANTIC_TYPES):
            continue
        if _is_duplicate_table_block(block, table_region_source_ids):
            continue
        if _is_duplicate_paragraph(block, specific_source_ids, heading_texts):
            continue
        semantic_blocks_with_index.append((block, fallback_index))

    return [
        block
        for block, fallback_index in sorted(
            semantic_blocks_with_index,
            key=lambda item: block_sort_key(item[0], item[1]),
        )
    ]


def get_block_source_text_ids(block: Block) -> set[str]:
    """Return source TextBlock ids carried by a semantic block, if available."""
    if isinstance(block, _HasSourceTextBlockIds):
        return set(block.source_text_block_ids)
    return set()


def get_block_normalized_text(block: Block) -> str:
    """Return whitespace-normalized comparable block text."""
    return " ".join((block.normalized_text or block.text or "").split())


def has_overlapping_source_ids(block: Block, source_ids: set[str]) -> bool:
    """Return whether a block's source TextBlock ids overlap another source set."""
    return bool(get_block_source_text_ids(block) & source_ids)


def should_exclude_from_semantic_output(block: Block) -> bool:
    """Return whether a block is raw/furniture noise for semantic output."""
    if isinstance(block, TextBlock):
        return True
    if _has_furniture_flag(block):
        return True
    if isinstance(block, HeadingBlock | TableBlock | TableRegionBlock | FigureBlock):
        return False
    return is_semantic_furniture_text(get_block_normalized_text(block))


def is_semantic_furniture_text(text: str) -> bool:
    """Return whether text is likely page/document furniture only."""
    normalized_text = " ".join(text.split())
    if not normalized_text:
        return True
    if normalized_text.casefold() == "page intentionally left blank":
        return True
    if _DATE_ONLY_RE.fullmatch(normalized_text):
        return True
    if _DOCUMENT_ID_RE.fullmatch(normalized_text):
        return True
    if _CHANGE_NOTICE_RE.fullmatch(normalized_text):
        return True
    if _APPENDIX_HEADER_RE.fullmatch(normalized_text):
        return True
    return _APPENDIX_PAGE_RE.fullmatch(normalized_text) is not None


def block_sort_key(block: Block, fallback_index: int) -> tuple[int, float, float, int]:
    """Return a stable page-order sort key for semantic blocks."""
    bbox = block.source.bbox if block.source is not None else None
    if bbox is None:
        return (1, float(fallback_index), 0.0, fallback_index)
    return (0, bbox.y0, bbox.x0, fallback_index)


def _is_duplicate_paragraph(
    block: Block,
    specific_source_ids: set[str],
    heading_texts: set[str],
) -> bool:
    if not isinstance(block, ParagraphBlock):
        return False
    if has_overlapping_source_ids(block, specific_source_ids):
        return True
    normalized_text = get_block_normalized_text(block)
    return bool(normalized_text and normalized_text in heading_texts)


def _is_duplicate_table_block(
    block: Block,
    table_region_source_ids: set[str],
) -> bool:
    return isinstance(block, TableBlock) and has_overlapping_source_ids(
        block,
        table_region_source_ids,
    )


def _has_furniture_flag(block: Block) -> bool:
    return bool(
        getattr(block, "is_page_furniture", False)
        or getattr(block, "is_page_header", False)
        or getattr(block, "is_page_footer", False)
        or getattr(block, "is_page_number", False)
    )
