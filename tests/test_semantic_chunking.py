"""Tests for semantic RAG chunk creation."""

from techdoc_parser.chunking import create_semantic_chunks
from techdoc_parser.core import (
    BoundingBox,
    Document,
    DocumentMetadata,
    FigureBlock,
    Page,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
    TableRegionBlock,
    TextBlock,
)


def _source(
    *,
    page_number: int = 1,
    y0: float = 10.0,
) -> SourceLocation:
    return SourceLocation(
        document_path="manual.pdf",
        page_number=page_number,
        bbox=BoundingBox(x0=10.0, y0=y0, x1=100.0, y1=y0 + 10.0),
        extraction_method="unit-test",
        confidence=1.0,
    )


def _document(page: Page) -> Document:
    return Document(
        id="manual",
        source_path="manual.pdf",
        metadata=DocumentMetadata(title="Manual Title"),
        pages=[page],
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
        source_text_block_ids=source_text_block_ids,
    )


def _table_region() -> TableRegionBlock:
    text = "TABLE I. Severity categories\nCritical\n2"
    return TableRegionBlock(
        id="table-region-1",
        source=_source(y0=10.0),
        text=text,
        normalized_text=text,
        caption="TABLE I. Severity categories",
        rows=[["TABLE I. Severity categories"], ["Critical"], ["2"]],
        source_text_block_ids=["text-1", "text-2"],
        source_table_block_ids=["table-1"],
        source_paragraph_block_ids=["paragraph-1"],
    )


def test_create_semantic_chunks_creates_basic_paragraph_chunk() -> None:
    """A paragraph semantic block should produce one chunk with sources."""
    paragraph = _paragraph("paragraph-1", "Body paragraph.", ["text-1"])
    page = Page(page_number=1, blocks=[paragraph])

    chunks = create_semantic_chunks(_document(page))

    assert len(chunks) == 1
    assert chunks[0].text == "Body paragraph."
    assert chunks[0].source_page_numbers == [1]
    assert chunks[0].source_block_ids == ["paragraph-1"]
    assert chunks[0].source_text_block_ids == ["text-1"]


def test_create_semantic_chunks_excludes_raw_text_blocks() -> None:
    """Chunking should use semantic blocks and avoid raw TextBlock duplicates."""
    text = TextBlock(
        id="text-1",
        source=_source(),
        text="Body paragraph.",
        normalized_text="Body paragraph.",
    )
    paragraph = _paragraph("paragraph-1", "Body paragraph.", ["text-1"])
    page = Page(page_number=1, blocks=[text, paragraph], text_blocks=[text])

    chunks = create_semantic_chunks(_document(page))

    assert len(chunks) == 1
    assert chunks[0].text.count("Body paragraph.") == 1
    assert chunks[0].source_block_ids == ["paragraph-1"]


def test_create_semantic_chunks_prefers_table_region_block() -> None:
    """TableRegionBlock should suppress duplicate low-level table fragments."""
    table = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    paragraph = _paragraph("paragraph-1", "Critical\n2", ["text-2"], y0=30.0)
    region = _table_region()
    page = Page(page_number=1, blocks=[table, paragraph, region])

    chunks = create_semantic_chunks(_document(page))

    assert len(chunks) == 1
    assert "[Table region candidate]" in chunks[0].text
    assert chunks[0].text.count("TABLE I. Severity categories") == 1
    assert chunks[0].source_block_ids == ["table-region-1"]
    assert chunks[0].source_text_block_ids == ["text-1", "text-2"]


def test_create_semantic_chunks_renders_figure_candidate() -> None:
    """Figure candidates should include a label and caption text."""
    figure = FigureBlock(
        id="figure-1",
        source=_source(),
        text="Figure 1. System overview",
        normalized_text="Figure 1. System overview",
        caption="Figure 1. System overview",
        source_text_block_ids=["text-1"],
    )
    page = Page(page_number=1, blocks=[figure])

    chunks = create_semantic_chunks(_document(page))

    assert chunks[0].text == "[Figure candidate]\nFigure 1. System overview"
    assert chunks[0].source_block_ids == ["figure-1"]


def test_create_semantic_chunks_respects_max_chars_between_blocks() -> None:
    """Small max_chars should split chunks between semantic blocks."""
    paragraph_one = _paragraph("paragraph-1", "First paragraph.", ["text-1"], y0=10.0)
    paragraph_two = _paragraph("paragraph-2", "Second paragraph.", ["text-2"], y0=30.0)
    paragraph_three = _paragraph("paragraph-3", "Third paragraph.", ["text-3"], y0=50.0)
    page = Page(
        page_number=1,
        blocks=[paragraph_one, paragraph_two, paragraph_three],
    )

    chunks = create_semantic_chunks(_document(page), max_chars=30)

    assert [chunk.id for chunk in chunks] == ["chunk-1", "chunk-2", "chunk-3"]
    assert chunks[0].source_block_ids == ["paragraph-1"]
    assert chunks[1].source_block_ids == ["paragraph-2"]
    assert chunks[2].source_block_ids == ["paragraph-3"]


def test_create_semantic_chunks_keeps_long_single_block_unsplit() -> None:
    """A single block longer than max_chars should remain one chunk."""
    long_text = "Long paragraph " * 20
    paragraph = _paragraph("paragraph-1", long_text, ["text-1"])
    page = Page(page_number=1, blocks=[paragraph])

    chunks = create_semantic_chunks(_document(page), max_chars=40)

    assert len(chunks) == 1
    assert chunks[0].text == long_text
    assert len(chunks[0].text) > 40


def test_create_semantic_chunks_adds_metadata() -> None:
    """Chunks should carry simple RAG metadata."""
    paragraph = _paragraph("paragraph-1", "Body paragraph.", ["text-1"])
    page = Page(page_number=1, blocks=[paragraph])

    chunks = create_semantic_chunks(_document(page))

    assert chunks[0].metadata["chunk_index"] == "1"
    assert chunks[0].metadata["chunk_type"] == "semantic"
    assert chunks[0].metadata["source_path"] == "manual.pdf"
    assert chunks[0].metadata["title"] == "Manual Title"
    assert chunks[0].chunk_type == "semantic"
    assert chunks[0].document_id == "manual"
