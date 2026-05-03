"""Tests for basic PDF ingestion."""

from pathlib import Path

import fitz
import pytest

from techdoc_parser import parse_document
from techdoc_parser.core import Document, HeadingBlock, TextBlock
from techdoc_parser.ingestion import PDFLoader
from techdoc_parser.normalization import normalize_text


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


def _create_heading_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=400.0, height=200.0)
    page.insert_text((20.0, 40.0), "CHAPTER 1 - Introduction", fontsize=16.0)
    page.insert_text(
        (20.0, 120.0),
        "This is a normal paragraph ending with punctuation.",
        fontsize=10.0,
    )
    document.save(path)
    document.close()


def _create_embedded_heading_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=400.0, height=240.0)
    page.insert_textbox(
        fitz.Rect(20.0, 20.0, 380.0, 180.0),
        (
            "This paragraph introduces applicable document references.\n\n"
            "2. APPLICABLE DOCUMENTS"
        ),
        fontsize=10.0,
    )
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
    assert text_block.text is not None
    assert "Hello from PyMuPDF" in text_block.text
    assert text_block.normalized_text == normalize_text(text_block.text)
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


def test_pdf_loader_adds_heading_blocks_without_changing_text_blocks(
    tmp_path: Path,
) -> None:
    """PDFLoader should add HeadingBlock objects only to generic page blocks."""
    pdf_path = tmp_path / "heading.pdf"
    _create_heading_pdf(pdf_path)

    document = PDFLoader(str(pdf_path)).load()
    page = document.pages[0]

    assert page.text_blocks
    assert all(isinstance(block, TextBlock) for block in page.text_blocks)
    assert all(block in page.blocks for block in page.text_blocks)

    heading_blocks = [block for block in page.blocks if isinstance(block, HeadingBlock)]

    assert heading_blocks
    assert all(block not in page.text_blocks for block in heading_blocks)
    assert heading_blocks[0].text is not None
    assert heading_blocks[0].text.strip() == "CHAPTER 1 - Introduction"
    assert heading_blocks[0].level == 1


def test_pdf_loader_adds_embedded_heading_blocks_from_text_block(
    tmp_path: Path,
) -> None:
    """PDFLoader should detect headings embedded inside a text block."""
    pdf_path = tmp_path / "embedded-heading.pdf"
    _create_embedded_heading_pdf(pdf_path)

    document = PDFLoader(str(pdf_path)).load()
    page = document.pages[0]

    assert page.text_blocks
    assert all(isinstance(block, TextBlock) for block in page.text_blocks)
    assert all(block in page.blocks for block in page.text_blocks)

    heading_blocks = [block for block in page.blocks if isinstance(block, HeadingBlock)]

    assert any(
        block.normalized_text == "2. APPLICABLE DOCUMENTS" for block in heading_blocks
    )
    assert all(block not in page.text_blocks for block in heading_blocks)


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
