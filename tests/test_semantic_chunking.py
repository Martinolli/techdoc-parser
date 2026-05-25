"""Tests for semantic RAG chunk creation."""

from techdoc_parser.chunking import create_semantic_chunks
from techdoc_parser.chunking.semantic import clean_chunk_text
from techdoc_parser.core import (
    BoundingBox,
    Document,
    DocumentMetadata,
    FigureBlock,
    HeadingBlock,
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


def _heading(
    id: str,
    text: str,
    *,
    level: int = 1,
    y0: float = 10.0,
) -> HeadingBlock:
    return HeadingBlock(
        id=id,
        source=_source(y0=y0),
        text=text,
        normalized_text=text,
        level=level,
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


def test_create_semantic_chunks_adds_single_heading_context() -> None:
    """Chunks should inherit metadata from the nearest heading."""
    heading = _heading("heading-1", "7. Flight Test Risk Management.", level=1)
    paragraph = _paragraph(
        "paragraph-1",
        "Risk management body paragraph.",
        ["text-1"],
        y0=30.0,
    )
    page = Page(page_number=1, blocks=[heading, paragraph])

    chunks = create_semantic_chunks(_document(page))

    assert len(chunks) == 1
    assert chunks[0].metadata["section_title"] == "7. Flight Test Risk Management."
    assert chunks[0].metadata["section_path"] == "7. Flight Test Risk Management."
    assert chunks[0].metadata["section_level"] == "1"


def test_create_semantic_chunks_adds_nested_heading_context() -> None:
    """Nested headings should produce a simple section path."""
    heading_one = _heading("heading-1", "7. Flight Test Risk Management.", level=1)
    heading_two = _heading("heading-2", "b. Requirements.", level=2, y0=30.0)
    paragraph = _paragraph("paragraph-1", "Requirement body.", ["text-1"], y0=50.0)
    page = Page(page_number=1, blocks=[heading_one, heading_two, paragraph])

    chunks = create_semantic_chunks(_document(page))

    assert len(chunks) == 1
    assert chunks[0].metadata["section_title"] == "b. Requirements."
    assert (
        chunks[0].metadata["section_path"]
        == "7. Flight Test Risk Management. > b. Requirements."
    )
    assert chunks[0].metadata["section_level"] == "2"


def test_create_semantic_chunks_resets_nested_heading_context() -> None:
    """A new shallower heading should clear deeper section metadata."""
    heading_one = _heading("heading-1", "7. Flight Test Risk Management.", level=1)
    heading_two = _heading("heading-2", "b. Requirements.", level=2, y0=30.0)
    paragraph_one = _paragraph(
        "paragraph-1",
        "Requirement body.",
        ["text-1"],
        y0=50.0,
    )
    heading_three = _heading(
        "heading-3",
        "8. Safety Event Reporting and Response.",
        level=1,
        y0=70.0,
    )
    paragraph_two = _paragraph(
        "paragraph-2",
        "Reporting body.",
        ["text-2"],
        y0=90.0,
    )
    page = Page(
        page_number=1,
        blocks=[heading_one, heading_two, paragraph_one, heading_three, paragraph_two],
    )

    chunks = create_semantic_chunks(_document(page))

    assert len(chunks) == 2
    assert (
        chunks[1].metadata["section_path"] == "8. Safety Event Reporting and Response."
    )
    assert "b. Requirements." not in chunks[1].metadata["section_path"]


def test_create_semantic_chunks_starts_new_chunk_at_new_heading() -> None:
    """A heading after body content should start a new section chunk."""
    heading_one = _heading("heading-1", "1. First section.", level=1)
    paragraph_one = _paragraph("paragraph-1", "First body.", ["text-1"], y0=30.0)
    heading_two = _heading("heading-2", "2. Second section.", level=1, y0=50.0)
    paragraph_two = _paragraph("paragraph-2", "Second body.", ["text-2"], y0=70.0)
    page = Page(
        page_number=1,
        blocks=[heading_one, paragraph_one, heading_two, paragraph_two],
    )

    chunks = create_semantic_chunks(_document(page), max_chars=200)

    assert len(chunks) == 2
    assert "2. Second section." not in chunks[0].text
    assert chunks[1].text.startswith("2. Second section.")
    assert chunks[1].metadata["section_title"] == "2. Second section."


def test_create_semantic_chunks_omits_section_metadata_without_heading() -> None:
    """Chunks without an active heading should keep only general metadata."""
    paragraph = _paragraph("paragraph-1", "Body paragraph.", ["text-1"])
    page = Page(page_number=1, blocks=[paragraph])

    chunks = create_semantic_chunks(_document(page))

    assert "section_title" not in chunks[0].metadata
    assert "section_path" not in chunks[0].metadata
    assert "section_level" not in chunks[0].metadata
    assert chunks[0].metadata["chunk_type"] == "semantic"


def test_create_semantic_chunks_keeps_section_metadata_with_cleaned_text() -> None:
    """Furniture cleanup should not remove active section metadata."""
    heading = _heading("heading-1", "7. Flight Test Risk Management.", level=1)
    paragraph = _paragraph(
        "paragraph-1",
        "1/31/2012\n\n4040.26B\n\nAppendix C\n\nHowever, there may be risks...",
        ["text-1"],
        y0=30.0,
    )
    page = Page(page_number=1, blocks=[heading, paragraph])

    chunks = create_semantic_chunks(_document(page))

    assert len(chunks) == 1
    assert "1/31/2012" not in chunks[0].text
    assert "4040.26B" not in chunks[0].text
    assert "However, there may be risks..." in chunks[0].text
    assert chunks[0].metadata["section_title"] == "7. Flight Test Risk Management."


def test_create_semantic_chunks_excludes_page_furniture_text() -> None:
    """Furniture-like semantic blocks should not appear in chunks."""
    furniture_blocks = [
        _paragraph("paragraph-1", "1/31/2012", ["text-1"], y0=10.0),
        _paragraph("paragraph-2", "4040.26B", ["text-2"], y0=20.0),
        _paragraph(
            "paragraph-3",
            "Page intentionally left blank",
            ["text-3"],
            y0=30.0,
        ),
    ]
    body = _paragraph(
        "paragraph-4",
        "This body paragraph remains.",
        ["text-4"],
        y0=40.0,
    )
    page = Page(page_number=1, blocks=[*furniture_blocks, body])

    chunks = create_semantic_chunks(_document(page))

    assert len(chunks) == 1
    assert chunks[0].text == "This body paragraph remains."
    assert "1/31/2012" not in chunks[0].text
    assert "4040.26B" not in chunks[0].text
    assert "Page intentionally left blank" not in chunks[0].text


def test_create_semantic_chunks_preserves_legitimate_appendix_content() -> None:
    """Real appendix headings and body text should remain in chunks."""
    heading = HeadingBlock(
        id="heading-1",
        source=_source(y0=10.0),
        text="APPENDIX C. AIR FLIGHT TEST RISK MANAGEMENT PROCESS",
        normalized_text="APPENDIX C. AIR FLIGHT TEST RISK MANAGEMENT PROCESS",
        level=1,
    )
    appendix_header = _paragraph("paragraph-1", "Appendix C", ["text-1"], y0=20.0)
    body = _paragraph(
        "paragraph-2",
        "This appendix describes the risk management process.",
        ["text-2"],
        y0=30.0,
    )
    page = Page(page_number=1, blocks=[heading, appendix_header, body])

    chunks = create_semantic_chunks(_document(page))

    assert len(chunks) == 1
    assert "APPENDIX C. AIR FLIGHT TEST RISK MANAGEMENT PROCESS" in chunks[0].text
    assert "This appendix describes the risk management process." in chunks[0].text
    assert "Appendix C\n\n" not in chunks[0].text


def test_clean_chunk_text_removes_embedded_furniture_lines() -> None:
    """Chunk cleanup should remove embedded page/document furniture lines."""
    text = "1/31/2012\n\n4040.26B\n\nAppendix C\n\nHowever, there may be risks..."

    cleaned_text = clean_chunk_text(text)

    assert "1/31/2012" not in cleaned_text
    assert "4040.26B" not in cleaned_text
    assert "Appendix C" not in cleaned_text
    assert "However, there may be risks..." in cleaned_text


def test_clean_chunk_text_preserves_full_appendix_heading() -> None:
    """Full appendix headings should remain meaningful chunk content."""
    text = "APPENDIX C. AIR FLIGHT TEST RISK MANAGEMENT PROCESS"

    assert clean_chunk_text(text) == text


def test_clean_chunk_text_preserves_body_appendix_reference() -> None:
    """Body references to appendices should not be removed."""
    text = "See Appendix C for a more detailed description of the process."

    assert clean_chunk_text(text) == text


def test_clean_chunk_text_removes_page_labels() -> None:
    """Standalone appendix-style page labels should be removed."""
    cleaned_text = clean_chunk_text("C-2\n\nMain body text")

    assert "C-2" not in cleaned_text
    assert cleaned_text == "Main body text"


def test_clean_chunk_text_removes_intentionally_blank_page_text() -> None:
    """Intentionally blank page markers should leave no chunk text."""
    assert clean_chunk_text("Page intentionally left blank") == ""


def test_create_semantic_chunks_cleans_embedded_furniture_lines() -> None:
    """Semantic chunks should clean furniture lines embedded in paragraph text."""
    paragraph = _paragraph(
        "paragraph-1",
        "1/31/2012\n\n4040.26B\n\nAppendix C\n\nHowever, there may be risks...",
        ["text-1"],
    )
    page = Page(page_number=1, blocks=[paragraph])

    chunks = create_semantic_chunks(_document(page))

    assert len(chunks) == 1
    assert "1/31/2012" not in chunks[0].text
    assert "4040.26B" not in chunks[0].text
    assert "Appendix C" not in chunks[0].text
    assert "However, there may be risks..." in chunks[0].text
