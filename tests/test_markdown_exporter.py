"""Tests for Markdown document export."""

from pathlib import Path

from techdoc_parser.core import (
    BoundingBox,
    Document,
    DocumentMetadata,
    Page,
    SourceLocation,
    TextBlock,
)
from techdoc_parser.exporters import document_to_markdown, export_document_markdown


def _document() -> Document:
    source = SourceLocation(
        document_path="manual.pdf",
        page_number=1,
        bbox=BoundingBox(x0=1.0, y0=2.0, x1=3.0, y1=4.0),
        extraction_method="pymupdf",
        confidence=1.0,
    )
    block = TextBlock(id="block-1", text="Example text block", source=source)
    page = Page(
        page_number=1,
        width=200.0,
        height=100.0,
        has_native_text=True,
        requires_ocr=False,
        text_blocks=[block],
        blocks=[block],
    )
    return Document(
        id="manual",
        source_path="manual.pdf",
        metadata=DocumentMetadata(title="Manual", author="Author"),
        pages=[page],
    )


def test_document_to_markdown_renders_document_content() -> None:
    """Markdown rendering should include document, page, and text block content."""
    markdown = document_to_markdown(_document())

    assert isinstance(markdown, str)
    assert "# Manual" in markdown
    assert "Source path: manual.pdf" in markdown
    assert "## Page 1" in markdown
    assert "Example text block" in markdown
    assert "has_native_text: True" in markdown
    assert "requires_ocr: False" in markdown


def test_document_to_markdown_uses_document_id_when_title_missing() -> None:
    """Markdown rendering should fall back to document id when title is missing."""
    document = _document()
    document.metadata.title = None

    markdown = document_to_markdown(document)

    assert "# manual" in markdown


def test_export_document_markdown_writes_file(tmp_path: Path) -> None:
    """Markdown exporter should write output and create parent directories."""
    output_path = tmp_path / "nested" / "manual-output"

    export_document_markdown(_document(), str(output_path))

    assert output_path.parent.is_dir()
    assert output_path.exists()
    assert "Example text block" in output_path.read_text(encoding="utf-8")
