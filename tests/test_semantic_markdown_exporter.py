"""Tests for semantic Markdown document export."""

from pathlib import Path

from techdoc_parser.core import (
    Block,
    BoundingBox,
    Document,
    DocumentMetadata,
    FigureBlock,
    HeadingBlock,
    Page,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
    TextBlock,
)
from techdoc_parser.exporters import (
    document_to_semantic_markdown,
    export_document_semantic_markdown,
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


def _document(blocks: list[Block], text_blocks: list[TextBlock]) -> Document:
    page = Page(
        page_number=1,
        has_native_text=True,
        requires_ocr=False,
        blocks=blocks,
        text_blocks=text_blocks,
    )
    return Document(
        id="manual",
        source_path="manual.pdf",
        metadata=DocumentMetadata(title="Manual", author="Author"),
        pages=[page],
    )


def _text_block(id: str, text: str, *, y0: float = 10.0) -> TextBlock:
    return TextBlock(
        id=id,
        text=text,
        source=_source(y0=y0),
        normalized_text=text,
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
        text=text,
        source=_source(y0=y0),
        normalized_text=text,
        source_text_block_ids=source_text_block_ids,
    )


def _table(id: str, text: str, source_text_block_ids: list[str]) -> TableBlock:
    return TableBlock(
        id=id,
        source=_source(),
        text=text,
        normalized_text=text,
        source_text_block_ids=source_text_block_ids,
    )


def _figure(id: str, caption: str, source_text_block_ids: list[str]) -> FigureBlock:
    return FigureBlock(
        id=id,
        source=_source(),
        text=caption,
        normalized_text=caption,
        caption=caption,
        source_text_block_ids=source_text_block_ids,
    )


def _heading(id: str, text: str) -> HeadingBlock:
    return HeadingBlock(
        id=id,
        source=_source(),
        text=text,
        normalized_text=text,
        level=1,
    )


def test_semantic_markdown_excludes_raw_text_blocks() -> None:
    """Semantic Markdown should render paragraphs without raw TextBlock debug output."""
    text = _text_block("text-1", "Body paragraph.")
    paragraph = _paragraph("paragraph-1", "Body paragraph.", ["text-1"])
    document = _document([text, paragraph], [text])

    markdown = document_to_semantic_markdown(document)

    assert "Body paragraph." in markdown
    assert markdown.count("Body paragraph.") == 1
    assert "bbox" not in markdown


def test_semantic_markdown_suppresses_duplicate_table_paragraph() -> None:
    """Table candidates should render without duplicate paragraph text."""
    text = _text_block("text-1", "Column A    Column B")
    paragraph = _paragraph("paragraph-1", "Column A    Column B", ["text-1"])
    table = _table("table-1", "Column A    Column B", ["text-1"])
    document = _document([text, paragraph, table], [text])

    markdown = document_to_semantic_markdown(document)

    assert "**Table candidate**" in markdown
    assert markdown.count("Column A    Column B") == 1
    assert "paragraph-1" not in markdown


def test_semantic_markdown_suppresses_duplicate_figure_paragraph() -> None:
    """Figure candidates should render without duplicate paragraph text."""
    text = _text_block("text-1", "FIGURE B-1. Assessing software risk")
    paragraph = _paragraph(
        "paragraph-1",
        "FIGURE B-1. Assessing software risk",
        ["text-1"],
    )
    figure = _figure("figure-1", "FIGURE B-1. Assessing software risk", ["text-1"])
    document = _document([text, paragraph, figure], [text])

    markdown = document_to_semantic_markdown(document)

    assert "**Figure candidate:**" in markdown
    assert markdown.count("FIGURE B-1. Assessing software risk") == 1
    assert "paragraph-1" not in markdown


def test_semantic_markdown_suppresses_duplicate_heading_paragraph() -> None:
    """Headings should render without duplicate paragraph text."""
    heading = _heading("heading-1", "1. SCOPE")
    paragraph = _paragraph("paragraph-1", "1. SCOPE", ["text-1"])
    document = _document([heading, paragraph], [])

    markdown = document_to_semantic_markdown(document)

    assert "# 1. SCOPE" in markdown
    assert markdown.count("1. SCOPE") == 1
    assert "paragraph-1" not in markdown


def test_semantic_markdown_preserves_ordinary_body_paragraph() -> None:
    """Ordinary paragraphs should remain in semantic Markdown."""
    paragraph = _paragraph(
        "paragraph-1",
        "This body paragraph remains.",
        ["text-1"],
    )
    document = _document([paragraph], [])

    markdown = document_to_semantic_markdown(document)

    assert "This body paragraph remains." in markdown
    assert "_Source: page 1, block paragraph-1_" in markdown


def test_export_document_semantic_markdown_writes_file(tmp_path: Path) -> None:
    """Semantic Markdown exporter should write output and create directories."""
    paragraph = _paragraph("paragraph-1", "Semantic output.", ["text-1"])
    document = _document([paragraph], [])
    output_path = tmp_path / "nested" / "semantic.md"

    export_document_semantic_markdown(document, output_path)

    assert output_path.exists()
    assert "Semantic output." in output_path.read_text(encoding="utf-8")
