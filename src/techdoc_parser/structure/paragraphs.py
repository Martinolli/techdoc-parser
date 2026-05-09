"""Conservative paragraph grouping helpers."""

from __future__ import annotations

from techdoc_parser.core import HeadingBlock, Page, ParagraphBlock, TextBlock


def create_paragraph_blocks_for_page(page: Page) -> list[ParagraphBlock]:
    """Create paragraph blocks from meaningful page text blocks."""
    heading_texts = _heading_texts_for_page(page)
    paragraphs: list[ParagraphBlock] = []

    for text_block in page.text_blocks:
        if _should_skip_text_block(text_block, heading_texts):
            continue

        text = text_block.text
        if text is None:
            continue

        paragraphs.append(
            ParagraphBlock(
                id=f"page-{page.page_number}-paragraph-{len(paragraphs) + 1}",
                text=text,
                source=text_block.source,
                normalized_text=text_block.normalized_text,
                source_text_block_ids=[text_block.id],
            )
        )

    return paragraphs


def _should_skip_text_block(
    text_block: TextBlock,
    heading_texts: set[str],
) -> bool:
    text = text_block.text
    if text is None or not text.strip():
        return True
    if text_block.is_page_furniture:
        return True
    if (
        text_block.is_page_header
        or text_block.is_page_footer
        or text_block.is_page_number
    ):
        return True
    return _normalized_text_for_block(text_block) in heading_texts


def _heading_texts_for_page(page: Page) -> set[str]:
    heading_texts: set[str] = set()
    for block in page.blocks:
        if isinstance(block, HeadingBlock):
            heading_texts.add(_normalize_for_match(block.normalized_text or block.text))
    return heading_texts


def _normalized_text_for_block(text_block: TextBlock) -> str:
    return _normalize_for_match(text_block.normalized_text or text_block.text)


def _normalize_for_match(text: str | None) -> str:
    return " ".join((text or "").split())
