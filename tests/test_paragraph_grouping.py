"""Tests for conservative paragraph grouping."""

from techdoc_parser.core import (
    BoundingBox,
    HeadingBlock,
    Page,
    ParagraphBlock,
    SourceLocation,
    TextBlock,
)
from techdoc_parser.structure import create_paragraph_blocks_for_page


def _source() -> SourceLocation:
    return SourceLocation(
        document_path="manual.pdf",
        page_number=1,
        bbox=BoundingBox(x0=1.0, y0=2.0, x1=3.0, y1=4.0),
    )


def _text_block(
    text: str,
    *,
    id: str = "text-1",
    normalized_text: str | None = None,
) -> TextBlock:
    return TextBlock(
        id=id,
        text=text,
        source=_source(),
        normalized_text=normalized_text,
    )


def test_paragraph_block_serialization() -> None:
    """ParagraphBlock should serialize paragraph-specific fields."""
    source = _source()
    block = ParagraphBlock(
        id="paragraph-1",
        text="Example paragraph.",
        source=source,
        normalized_text="Example paragraph.",
        source_text_block_ids=["text-1"],
    )

    assert block.block_type == "paragraph"
    assert block.to_dict() == {
        "id": "paragraph-1",
        "source": source.to_dict(),
        "block_type": "paragraph",
        "text": "Example paragraph.",
        "normalized_text": "Example paragraph.",
        "source_text_block_ids": ["text-1"],
    }


def test_create_paragraph_blocks_for_normal_body_text() -> None:
    """Normal body text should create a ParagraphBlock."""
    text_block = _text_block(
        "This is body text.",
        normalized_text="This is body text.",
    )
    page = Page(page_number=1, text_blocks=[text_block], blocks=[text_block])

    paragraphs = create_paragraph_blocks_for_page(page)

    assert len(paragraphs) == 1
    assert paragraphs[0].text == "This is body text."
    assert paragraphs[0].normalized_text == "This is body text."
    assert paragraphs[0].source is text_block.source
    assert paragraphs[0].source_text_block_ids == ["text-1"]


def test_create_paragraph_blocks_skips_page_furniture() -> None:
    """Page furniture text should not create paragraph blocks."""
    header = _text_block("MIL-STD-882E", id="header")
    footer = _text_block("Source: https://assist.dla.mil", id="footer")
    page_number = _text_block("1", id="page-number")
    header.is_page_header = True
    footer.is_page_footer = True
    page_number.is_page_number = True
    for block in [header, footer, page_number]:
        block.is_page_furniture = True

    page = Page(
        page_number=1,
        text_blocks=[header, footer, page_number],
        blocks=[header, footer, page_number],
    )

    assert create_paragraph_blocks_for_page(page) == []


def test_create_paragraph_blocks_skips_empty_text_blocks() -> None:
    """Empty text blocks should not create paragraph blocks."""
    text_block = _text_block("   ", id="empty")
    page = Page(page_number=1, text_blocks=[text_block], blocks=[text_block])

    assert create_paragraph_blocks_for_page(page) == []


def test_create_paragraph_blocks_skips_matching_heading_text_block() -> None:
    """Text blocks matching existing headings should not become paragraphs."""
    text_block = _text_block(
        "1. SCOPE",
        id="heading-text",
        normalized_text="1. SCOPE",
    )
    heading = HeadingBlock(
        id="heading-1",
        source=text_block.source,
        text="1. SCOPE",
        normalized_text="1. SCOPE",
        level=1,
    )
    page = Page(
        page_number=1,
        text_blocks=[text_block],
        blocks=[text_block, heading],
    )

    assert create_paragraph_blocks_for_page(page) == []
