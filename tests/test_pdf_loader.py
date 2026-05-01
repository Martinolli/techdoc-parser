"""Tests for basic PDF ingestion."""

from pathlib import Path

import fitz
import pytest

from techdoc_parser import parse_document
from techdoc_parser.core import Document, TextBlock
from techdoc_parser.ingestion import PDFLoader


def _create_test_pdf(path: Path, text: str = "Hello from PyMuPDF") -> None:
    document = fitz.open()
    page = document.new_page(width=200.0, height=100.0)
    page.insert_text((20.0, 50.0), text)
    document.set_metadata(
        {
            "title": "Generated PDF",
            "author": "techdoc-parser",
            "subject": "PDF ingestion test",
            "keywords": "test, pdf",
            "producer": "PyMuPDF",
            "creator": "pytest",
        }
    )
    document.save(path)
    document.close()


def _create_blank_pdf(path: Path) -> None:
    document = fitz.open()
    document.new_page(width=200.0, height=100.0)
    document.save(path)
    document.close()


def test_pdf_loader_loads_generated_one_page_pdf(tmp_path: Path) -> None:
    """PDFLoader should load native text from a generated PDF."""
    pdf_path = tmp_path / "manual.pdf"
    _create_test_pdf(pdf_path)

    document = PDFLoader(str(pdf_path)).load()

    assert isinstance(document, Document)
    assert document.id == "manual"
    assert document.metadata.title == "Generated PDF"
    assert document.metadata.keywords == ["test", "pdf"]
    assert len(document.pages) == 1

    page = document.pages[0]
    assert page.page_number == 1
    assert page.width is not None
    assert page.height is not None
    assert page.has_native_text is True
    assert page.requires_ocr is False

    matching_blocks = [
        block for block in page.text_blocks if "Hello from PyMuPDF" in block.text
    ]
    assert matching_blocks

    text_block = matching_blocks[0]
    assert text_block.source.document_path == str(pdf_path)
    assert text_block.source.page_number == 1
    assert text_block.source.extraction_method == "pymupdf"
    assert text_block.source.confidence == 1.0
    assert text_block.source.bbox is not None
    assert text_block in page.text_blocks
    assert text_block in page.blocks
    assert isinstance(page.blocks[0], TextBlock)

    page_data = page.to_dict()
    assert page_data["has_native_text"] is True
    assert page_data["requires_ocr"] is False


def test_pdf_loader_marks_blank_page_as_requiring_ocr(tmp_path: Path) -> None:
    """PDFLoader should mark blank pages as OCR candidates."""
    pdf_path = tmp_path / "blank.pdf"
    _create_blank_pdf(pdf_path)

    document = PDFLoader(str(pdf_path)).load()
    page = document.pages[0]

    assert page.text_blocks == []
    assert page.has_native_text is False
    assert page.requires_ocr is True


def test_parse_document_loads_generated_pdf(tmp_path: Path) -> None:
    """parse_document should route PDF files through PDFLoader."""
    pdf_path = tmp_path / "manual.pdf"
    _create_test_pdf(pdf_path, text="Loaded through parse_document")

    document = parse_document(str(pdf_path))

    assert isinstance(document, Document)
    assert document.pages[0].page_number == 1
    assert any(
        "Loaded through parse_document" in block.text
        for block in document.pages[0].text_blocks
    )


def test_pdf_loader_raises_file_not_found_for_missing_path(tmp_path: Path) -> None:
    """PDFLoader should reject missing paths."""
    with pytest.raises(FileNotFoundError):
        PDFLoader(str(tmp_path / "missing.pdf"))


def test_parse_document_raises_value_error_for_unsupported_extension(
    tmp_path: Path,
) -> None:
    """parse_document should reject unsupported file extensions."""
    text_path = tmp_path / "notes.txt"
    text_path.write_text("not a PDF", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported file type"):
        parse_document(str(text_path))
