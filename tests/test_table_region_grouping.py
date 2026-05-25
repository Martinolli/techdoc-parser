"""Tests for grouped table-region candidates."""

from techdoc_parser.core import (
    Block,
    BoundingBox,
    Document,
    DocumentMetadata,
    Page,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
    TableRegionBlock,
)
from techdoc_parser.exporters import document_to_semantic_markdown
from techdoc_parser.structure import (
    create_table_region_blocks_for_page,
    get_semantic_blocks_for_page,
)


def _source(
    *,
    y0: float = 10.0,
    x0: float = 10.0,
) -> SourceLocation:
    return SourceLocation(
        document_path="manual.pdf",
        page_number=1,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x0 + 100.0, y1=y0 + 10.0),
        extraction_method="pymupdf",
        confidence=1.0,
    )


def _table(
    id: str,
    text: str,
    source_text_block_ids: list[str],
    *,
    y0: float = 10.0,
) -> TableBlock:
    return TableBlock(
        id=id,
        source=_source(y0=y0),
        text=text,
        normalized_text=text,
        rows=[[line] for line in text.splitlines() if line.strip()],
        source_text_block_ids=source_text_block_ids,
    )


def _paragraph(
    id: str,
    text: str,
    source_text_block_ids: list[str],
    *,
    y0: float = 10.0,
) -> ParagraphBlock:
    return ParagraphBlock(
        id=id,
        source=_source(y0=y0),
        text=text,
        normalized_text=text,
        source_text_block_ids=source_text_block_ids,
    )


def _table_region(
    *,
    source_text_block_ids: list[str],
    source_table_block_ids: list[str],
    source_paragraph_block_ids: list[str] | None = None,
) -> TableRegionBlock:
    text = "TABLE I. Severity categories\nSEVERITY CATEGORIES"
    return TableRegionBlock(
        id="table-region-1",
        source=_source(),
        text=text,
        normalized_text=text,
        caption="TABLE I. Severity categories",
        rows=[["TABLE I. Severity categories"], ["SEVERITY CATEGORIES"]],
        source_text_block_ids=source_text_block_ids,
        source_table_block_ids=source_table_block_ids,
        source_paragraph_block_ids=source_paragraph_block_ids or [],
        is_candidate=True,
    )


def _document(blocks: list[Block]) -> Document:
    return Document(
        id="manual",
        source_path="manual.pdf",
        metadata=DocumentMetadata(title="Manual"),
        pages=[Page(page_number=1, blocks=blocks, has_native_text=True)],
    )


def test_table_region_block_serialization() -> None:
    """TableRegionBlock should serialize grouped table metadata."""
    block = _table_region(
        source_text_block_ids=["text-1", "text-2"],
        source_table_block_ids=["table-1"],
        source_paragraph_block_ids=["paragraph-1"],
    )

    data = block.to_dict()

    assert data["block_type"] == "table_region"
    assert data["caption"] == "TABLE I. Severity categories"
    assert data["rows"] == [["TABLE I. Severity categories"], ["SEVERITY CATEGORIES"]]
    assert data["source_text_block_ids"] == ["text-1", "text-2"]
    assert data["source_table_block_ids"] == ["table-1"]
    assert data["source_paragraph_block_ids"] == ["paragraph-1"]
    assert data["is_candidate"] is True


def test_table_region_groups_simple_caption_header_and_rows() -> None:
    """A caption followed by table-like blocks should become one region."""
    caption = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    title = _table("table-2", "SEVERITY CATEGORIES", ["text-2"], y0=25.0)
    header = _table(
        "table-3",
        "Description\nSeverity\nCategory\nMishap Result Criteria",
        ["text-3"],
        y0=40.0,
    )
    row = _table(
        "table-4",
        "Catastrophic\n1\nCould result in death",
        ["text-4"],
        y0=60.0,
    )
    page = Page(page_number=1, blocks=[caption, title, header, row])

    regions = create_table_region_blocks_for_page(page)

    assert len(regions) == 1
    assert regions[0].caption == "TABLE I. Severity categories"
    assert regions[0].source_table_block_ids == [
        "table-1",
        "table-2",
        "table-3",
        "table-4",
    ]
    assert "Catastrophic" in (regions[0].normalized_text or "")


def test_table_region_splits_two_tables() -> None:
    """A second table caption should start a separate table region."""
    table_one = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    row_one = _table("table-2", "Critical\n2", ["text-2"], y0=30.0)
    body = _paragraph(
        "paragraph-1",
        "b. To determine the appropriate probability level, use Table II.",
        ["text-3"],
        y0=60.0,
    )
    table_two = _table("table-3", "TABLE II. Probability levels", ["text-4"], y0=90.0)
    row_two = _table("table-4", "Frequent\nA", ["text-5"], y0=110.0)
    page = Page(page_number=1, blocks=[table_one, row_one, body, table_two, row_two])

    regions = create_table_region_blocks_for_page(page)

    assert len(regions) == 2
    assert regions[0].caption == "TABLE I. Severity categories"
    assert regions[1].caption == "TABLE II. Probability levels"
    assert "paragraph-1" not in regions[0].source_paragraph_block_ids


def test_table_region_includes_nearby_paragraph_row_fragments() -> None:
    """Paragraph fragments between table candidates should be included."""
    caption = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    row_label = _table("table-2", "Critical\n2", ["text-2"], y0=30.0)
    row_text = _paragraph(
        "paragraph-1",
        "Could result in severe injury or occupational illness.",
        ["text-3"],
        y0=45.0,
    )
    next_row = _table("table-3", "Marginal\n3", ["text-4"], y0=65.0)
    page = Page(page_number=1, blocks=[caption, row_label, row_text, next_row])

    regions = create_table_region_blocks_for_page(page)

    assert len(regions) == 1
    assert regions[0].source_paragraph_block_ids == ["paragraph-1"]
    assert "Could result in severe injury" in (regions[0].normalized_text or "")


def test_table_region_does_not_absorb_normal_paragraph_after_table() -> None:
    """Normal body paragraphs should stop a table region."""
    caption = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    row = _table("table-2", "Critical\n2", ["text-2"], y0=30.0)
    body = _paragraph(
        "paragraph-1",
        "b. To determine the appropriate probability level, use Table II.",
        ["text-3"],
        y0=50.0,
    )
    next_caption = _table(
        "table-3",
        "TABLE II. Probability levels",
        ["text-4"],
        y0=80.0,
    )
    next_row = _table("table-4", "Frequent\nA", ["text-5"], y0=100.0)
    page = Page(page_number=1, blocks=[caption, row, body, next_caption, next_row])

    regions = create_table_region_blocks_for_page(page)

    assert len(regions) == 2
    assert "paragraph-1" not in regions[0].source_paragraph_block_ids
    assert "To determine the appropriate probability" not in (
        regions[0].normalized_text or ""
    )


def test_table_region_does_not_group_unrelated_single_candidate() -> None:
    """A lone table candidate without caption should not be forced into a region."""
    table = _table("table-1", "Critical\n2", ["text-1"], y0=10.0)
    page = Page(page_number=1, blocks=[table])

    assert create_table_region_blocks_for_page(page) == []


def test_semantic_blocks_table_region_suppresses_low_level_duplicates() -> None:
    """TableRegionBlock should win over low-level table and paragraph fragments."""
    table = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    duplicate_table = _table("table-2", "Critical\n2", ["text-2"], y0=30.0)
    fragment = _paragraph(
        "paragraph-1",
        "Could result in severe injury.",
        ["text-3"],
        y0=45.0,
    )
    body = _paragraph("paragraph-2", "Ordinary body paragraph.", ["text-4"], y0=90.0)
    region = _table_region(
        source_text_block_ids=["text-1", "text-2", "text-3"],
        source_table_block_ids=["table-1", "table-2"],
        source_paragraph_block_ids=["paragraph-1"],
    )
    page = Page(
        page_number=1,
        blocks=[table, duplicate_table, fragment, body, region],
    )

    semantic_blocks = get_semantic_blocks_for_page(page)

    assert region in semantic_blocks
    assert table not in semantic_blocks
    assert duplicate_table not in semantic_blocks
    assert fragment not in semantic_blocks
    assert body in semantic_blocks


def test_semantic_markdown_renders_table_region_without_low_level_duplicates() -> None:
    """Semantic Markdown should prefer table regions over low-level table blocks."""
    table = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    row = _table("table-2", "Critical\n2", ["text-2"], y0=30.0)
    body = _paragraph("paragraph-1", "Ordinary body paragraph.", ["text-3"], y0=90.0)
    region = _table_region(
        source_text_block_ids=["text-1", "text-2"],
        source_table_block_ids=["table-1", "table-2"],
    )
    document = _document([table, row, body, region])

    markdown = document_to_semantic_markdown(document)

    assert "**Table region candidate**" in markdown
    assert "TABLE I. Severity categories\nSEVERITY CATEGORIES" in markdown
    assert "**Table candidate**" not in markdown
    assert "Ordinary body paragraph." in markdown
