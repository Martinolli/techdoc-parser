"""Conservative figure candidate detection helpers."""

from __future__ import annotations

import re

from techdoc_parser.core import FigureBlock, Page, TextBlock

_FIGURE_CAPTION_RE = re.compile(
    r"^FIGURE\s+(?:\d+|[A-Z]-\d+)\.\s+\S.+$",
    re.IGNORECASE,
)


def is_figure_caption_text(text: str) -> bool:
    """Return whether text is a clear figure caption."""
    normalized_text = _normalize_for_match(text)
    if not normalized_text:
        return False
    return _FIGURE_CAPTION_RE.fullmatch(normalized_text) is not None


def create_figure_blocks_for_page(page: Page) -> list[FigureBlock]:
    """Create conservative figure candidates from page text blocks."""
    figures: list[FigureBlock] = []

    for text_block in page.text_blocks:
        text = text_block.text
        if text is None or _should_skip_text_block(text_block):
            continue

        normalized_text = text_block.normalized_text or text
        caption = _normalize_for_match(normalized_text)
        figures.append(
            FigureBlock(
                id=f"page-{page.page_number}-figure-{len(figures) + 1}",
                source=text_block.source,
                text=text,
                normalized_text=text_block.normalized_text,
                caption=caption,
                source_text_block_ids=[text_block.id],
                is_candidate=True,
            )
        )

    return figures


def _should_skip_text_block(text_block: TextBlock) -> bool:
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
    return not is_figure_caption_text(text_block.normalized_text or text)


def _normalize_for_match(text: str | None) -> str:
    return " ".join((text or "").split())
