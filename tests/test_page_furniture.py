"""Tests for page-furniture detection."""

from techdoc_parser.core import BoundingBox, Page, SourceLocation, TextBlock
from techdoc_parser.structure import (
    classify_text_block_page_furniture,
    is_likely_page_header_text,
    is_page_number_text,
    is_source_footer_text,
)


def _block(text: str, *, y0: float = 100.0, y1: float = 120.0) -> TextBlock:
    source = SourceLocation(
        document_path="manual.pdf",
        page_number=1,
        bbox=BoundingBox(x0=10.0, y0=y0, x1=100.0, y1=y1),
    )
    return TextBlock(id="block-1", text=text, source=source, normalized_text=text)


def test_is_page_number_text() -> None:
    """Only whole page-number-like text should be detected."""
    assert is_page_number_text("1")
    assert is_page_number_text("23")
    assert is_page_number_text("ii")
    assert is_page_number_text("vii")
    assert not is_page_number_text("1.1")
    assert not is_page_number_text("4.3.2")
    assert not is_page_number_text("101.2.8")
    assert not is_page_number_text("MIL-STD-882E")


def test_is_source_footer_text() -> None:
    """Source and verification footer text should be detected."""
    assert is_source_footer_text(
        "Source: https://assist.dla.mil -- Downloaded: 2026-05-03T05:52Z"
    )
    assert is_source_footer_text(
        "Check the source to verify that this is the current version before use."
    )
    assert not is_source_footer_text("This is a normal paragraph.")


def test_is_likely_page_header_text() -> None:
    """Repeated document-title-like header text should be detected."""
    assert is_likely_page_header_text("MIL-STD-882E")
    assert is_likely_page_header_text("MIL-STD-882E\nw/CHANGE 1")
    assert is_likely_page_header_text("FTIAS Manual")
    assert not is_likely_page_header_text("1. SCOPE")
    assert not is_likely_page_header_text("2. APPLICABLE DOCUMENTS")
    assert not is_likely_page_header_text("CONTENTS")
    assert not is_likely_page_header_text("FOREWORD")


def test_classify_marks_source_footer() -> None:
    """Source footer text should be flagged as footer furniture."""
    page = Page(page_number=1, height=800.0)
    block = _block("Source: https://assist.dla.mil -- Downloaded: 2026-05-03T05:52Z")

    classify_text_block_page_furniture(block, page)

    assert block.is_page_footer
    assert block.is_page_furniture
    assert not block.is_page_header
    assert not block.is_page_number


def test_classify_marks_page_number() -> None:
    """Pure page numbers should be flagged as page furniture."""
    page = Page(page_number=1, height=800.0)
    block = _block("23", y0=760.0, y1=780.0)

    classify_text_block_page_furniture(block, page)

    assert block.is_page_number
    assert block.is_page_footer
    assert block.is_page_furniture
    assert not block.is_page_header


def test_classify_marks_top_document_header() -> None:
    """Document title text near the top should be flagged as header furniture."""
    page = Page(page_number=1, height=800.0)
    block = _block("MIL-STD-882E", y0=20.0, y1=40.0)

    classify_text_block_page_furniture(block, page)

    assert block.is_page_header
    assert block.is_page_furniture
    assert not block.is_page_footer
    assert not block.is_page_number


def test_classify_does_not_mark_real_section_heading() -> None:
    """Real section headings should not be page furniture."""
    page = Page(page_number=1, height=800.0)
    block = _block("1. SCOPE", y0=20.0, y1=40.0)

    classify_text_block_page_furniture(block, page)

    assert not block.is_page_header
    assert not block.is_page_footer
    assert not block.is_page_number
    assert not block.is_page_furniture


def test_classify_does_not_mark_normal_paragraph() -> None:
    """Normal body text should not be page furniture."""
    page = Page(page_number=1, height=800.0)
    block = _block("This is a normal paragraph.")

    classify_text_block_page_furniture(block, page)

    assert not block.is_page_header
    assert not block.is_page_footer
    assert not block.is_page_number
    assert not block.is_page_furniture
