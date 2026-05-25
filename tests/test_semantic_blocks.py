"""Tests for semantic block filtering."""

from techdoc_parser.core import (
    BoundingBox,
    FigureBlock,
    HeadingBlock,
    Page,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
    TextBlock,
)
from techdoc_parser.structure import get_semantic_blocks_for_page


def _source(
    *,
    y0: float = 10.0,
    x0: float = 10.0,
) -> SourceLocation:
    return SourceLocation(
        document_path="manual.pdf",
        page_number=1,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x0 + 100.0, y1=y0 + 10.0),
    )


def _text_block(
    id: str,
    text: str,
    *,
    y0: float = 10.0,
    x0: float = 10.0,
) -> TextBlock:
    return TextBlock(
        id=id,
        text=text,
        source=_source(y0=y0, x0=x0),
        normalized_text=text,
    )


def _paragraph(
    id: str,
    text: str,
    source_text_block_ids: list[str],
    *,
    y0: float = 10.0,
    x0: float = 10.0,
) -> ParagraphBlock:
    return ParagraphBlock(
        id=id,
        text=text,
        source=_source(y0=y0, x0=x0),
        normalized_text=text,
        source_text_block_ids=source_text_block_ids,
    )


def _heading(
    id: str,
    text: str,
    *,
    y0: float = 10.0,
    x0: float = 10.0,
) -> HeadingBlock:
    return HeadingBlock(
        id=id,
        source=_source(y0=y0, x0=x0),
        text=text,
        normalized_text=text,
        level=1,
    )


def _table(
    id: str,
    text: str,
    source_text_block_ids: list[str],
    *,
    y0: float = 10.0,
    x0: float = 10.0,
) -> TableBlock:
    return TableBlock(
        id=id,
        source=_source(y0=y0, x0=x0),
        text=text,
        normalized_text=text,
        source_text_block_ids=source_text_block_ids,
    )


def _figure(
    id: str,
    caption: str,
    source_text_block_ids: list[str],
    *,
    y0: float = 10.0,
    x0: float = 10.0,
) -> FigureBlock:
    return FigureBlock(
        id=id,
        source=_source(y0=y0, x0=x0),
        caption=caption,
        text=caption,
        normalized_text=caption,
        source_text_block_ids=source_text_block_ids,
    )


def test_semantic_blocks_exclude_text_blocks() -> None:
    """Raw TextBlock objects should not appear in semantic output."""
    text = _text_block("text-1", "Body paragraph.")
    paragraph = _paragraph("paragraph-1", "Body paragraph.", ["text-1"])
    page = Page(page_number=1, blocks=[text, paragraph], text_blocks=[text])

    semantic_blocks = get_semantic_blocks_for_page(page)

    assert semantic_blocks == [paragraph]
    assert all(not isinstance(block, TextBlock) for block in semantic_blocks)


def test_semantic_blocks_suppress_paragraph_duplicate_for_table() -> None:
    """Table candidates should win over paragraphs from the same source text."""
    text = _text_block("text-1", "Column A    Column B")
    paragraph = _paragraph("paragraph-1", "Column A    Column B", ["text-1"])
    table = _table("table-1", "Column A    Column B", ["text-1"])
    page = Page(page_number=1, blocks=[text, paragraph, table], text_blocks=[text])

    semantic_blocks = get_semantic_blocks_for_page(page)

    assert table in semantic_blocks
    assert paragraph not in semantic_blocks
    assert semantic_blocks == [table]


def test_semantic_blocks_suppress_paragraph_duplicate_for_figure() -> None:
    """Figure candidates should win over paragraphs from the same source text."""
    text = _text_block("text-1", "Figure 1. System overview")
    paragraph = _paragraph("paragraph-1", "Figure 1. System overview", ["text-1"])
    figure = _figure("figure-1", "Figure 1. System overview", ["text-1"])
    page = Page(page_number=1, blocks=[text, paragraph, figure], text_blocks=[text])

    semantic_blocks = get_semantic_blocks_for_page(page)

    assert figure in semantic_blocks
    assert paragraph not in semantic_blocks
    assert semantic_blocks == [figure]


def test_semantic_blocks_suppress_paragraph_duplicate_for_heading() -> None:
    """Headings should win over paragraphs with identical normalized text."""
    text = _text_block("text-1", "1. SCOPE")
    heading = _heading("heading-1", "1. SCOPE")
    paragraph = _paragraph("paragraph-1", "1. SCOPE", ["text-1"])
    page = Page(page_number=1, blocks=[text, heading, paragraph], text_blocks=[text])

    semantic_blocks = get_semantic_blocks_for_page(page)

    assert heading in semantic_blocks
    assert paragraph not in semantic_blocks
    assert semantic_blocks == [heading]


def test_semantic_blocks_keep_mixed_semantic_content_without_duplicates() -> None:
    """Mixed semantic output should keep body content and remove raw text."""
    heading_text = _text_block("text-1", "1. SCOPE", y0=10.0)
    body_text = _text_block("text-2", "Body paragraph remains.", y0=30.0)
    table_text = _text_block("text-3", "Column A    Column B", y0=50.0)
    figure_text = _text_block("text-4", "Figure 1. System overview", y0=70.0)
    heading = _heading("heading-1", "1. SCOPE", y0=10.0)
    duplicate_heading_paragraph = _paragraph("paragraph-1", "1. SCOPE", ["text-1"])
    body_paragraph = _paragraph(
        "paragraph-2",
        "Body paragraph remains.",
        ["text-2"],
        y0=30.0,
    )
    duplicate_table_paragraph = _paragraph(
        "paragraph-3",
        "Column A    Column B",
        ["text-3"],
    )
    table = _table("table-1", "Column A    Column B", ["text-3"], y0=50.0)
    duplicate_figure_paragraph = _paragraph(
        "paragraph-4",
        "Figure 1. System overview",
        ["text-4"],
    )
    figure = _figure("figure-1", "Figure 1. System overview", ["text-4"], y0=70.0)
    page = Page(
        page_number=1,
        blocks=[
            heading_text,
            heading,
            duplicate_heading_paragraph,
            body_text,
            body_paragraph,
            table_text,
            duplicate_table_paragraph,
            table,
            figure_text,
            duplicate_figure_paragraph,
            figure,
        ],
        text_blocks=[heading_text, body_text, table_text, figure_text],
    )

    semantic_blocks = get_semantic_blocks_for_page(page)

    assert [block.id for block in semantic_blocks] == [
        "heading-1",
        "paragraph-2",
        "table-1",
        "figure-1",
    ]
    assert all(not isinstance(block, TextBlock) for block in semantic_blocks)
    assert duplicate_heading_paragraph not in semantic_blocks
    assert duplicate_table_paragraph not in semantic_blocks
    assert duplicate_figure_paragraph not in semantic_blocks


def test_semantic_blocks_use_bbox_page_order_when_available() -> None:
    """Semantic blocks with source bboxes should sort in page order."""
    later_paragraph = _paragraph("paragraph-1", "Later body.", ["text-2"], y0=120.0)
    heading = _heading("heading-1", "1. SCOPE", y0=20.0)
    table = _table("table-1", "Column A    Column B", ["text-3"], y0=80.0)
    page = Page(page_number=1, blocks=[later_paragraph, heading, table])

    semantic_blocks = get_semantic_blocks_for_page(page)

    assert [block.id for block in semantic_blocks] == [
        "heading-1",
        "table-1",
        "paragraph-1",
    ]
