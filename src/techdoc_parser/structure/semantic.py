"""Semantic block filtering helpers for export/RAG views."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from techdoc_parser.core import (
    Block,
    FigureBlock,
    FormulaBlock,
    HeadingBlock,
    Page,
    ParagraphBlock,
    TableBlock,
)


@runtime_checkable
class _HasSourceTextBlockIds(Protocol):
    source_text_block_ids: list[str]


_SPECIFIC_SEMANTIC_TYPES = (HeadingBlock, TableBlock, FigureBlock, FormulaBlock)
_SEMANTIC_TYPES = (
    HeadingBlock,
    ParagraphBlock,
    TableBlock,
    FigureBlock,
    FormulaBlock,
)


def get_semantic_blocks_for_page(page: Page) -> list[Block]:
    """Return semantic page blocks without raw text or duplicate paragraphs."""
    specific_source_ids: set[str] = set()
    heading_texts: set[str] = set()

    for block in page.blocks:
        if isinstance(block, _SPECIFIC_SEMANTIC_TYPES):
            specific_source_ids.update(get_block_source_text_ids(block))
        if isinstance(block, HeadingBlock):
            heading_text = get_block_normalized_text(block)
            if heading_text:
                heading_texts.add(heading_text)

    semantic_blocks_with_index: list[tuple[Block, int]] = []
    for fallback_index, block in enumerate(page.blocks):
        if not isinstance(block, _SEMANTIC_TYPES):
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
