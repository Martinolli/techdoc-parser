"""Tests for conservative table candidate detection."""

from techdoc_parser.core import (
    HeadingBlock,
    Page,
    SourceLocation,
    TableBlock,
    TextBlock,
)
from techdoc_parser.structure import (
    create_table_blocks_for_page,
    is_table_candidate_text,
)


def _source() -> SourceLocation:
    return SourceLocation(document_path="manual.pdf", page_number=1)


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


def test_is_table_candidate_text_detects_table_patterns() -> None:
    """Known table-like text patterns should be detected."""
    assert is_table_candidate_text("TABLE I. Severity categories")
    assert is_table_candidate_text("TABLE II. Probability levels")
    assert is_table_candidate_text("TABLE III. Risk assessment matrix")
    assert is_table_candidate_text("Table 1. Example table")
    assert is_table_candidate_text("A-I. Task application matrix")
    assert is_table_candidate_text(
        "B-I. Software hazard causal factor risk assessment criteria"
    )
    assert is_table_candidate_text("III. Risk assessment matrix")
    assert is_table_candidate_text(
        "Description\nSeverity\nCategory\nMishap Result Criteria"
    )
    assert is_table_candidate_text(
        "Category    Description\nHigh        Severe impact\nLow         Minor impact"
    )
    assert is_table_candidate_text("Entity\nPurpose\nKey links\nWhy it matters")
    assert is_table_candidate_text(
        "Catastrophic\n1\nCould result in one or more of the following..."
    )
    assert is_table_candidate_text("Critical\n2")


def test_is_table_candidate_text_rejects_false_positives() -> None:
    """Normal prose and non-table structural text should not be detected."""
    assert not is_table_candidate_text("This is a normal paragraph.")
    assert not is_table_candidate_text("1. SCOPE")
    assert not is_table_candidate_text("Source: https://assist.dla.mil")
    assert not is_table_candidate_text("TASK 102 ................................. 24")
    assert not is_table_candidate_text("Figure 1. System overview")


def test_is_table_candidate_text_rejects_numbered_prose() -> None:
    """MIL-STD foreword/body prose should not become table candidates."""
    assert not is_table_candidate_text(
        "5. This revision incorporates changes to meet Government and industry "
        "requests to reinstate task descriptions and improve the standard."
    )
    assert not is_table_candidate_text(
        "3. DoD is committed to protecting personnel from accidental death, "
        "injury, or occupational illness."
    )
    assert not is_table_candidate_text(
        "4. This system safety standard practice identifies the DoD approach "
        "for identifying hazards and managing associated risks."
    )
    assert not is_table_candidate_text(
        "This generated paragraph wraps across several lines of text and "
        "contains ordinary sentence structure, lowercase words, and punctuation "
        "without any compact table headers or row-like structure."
    )


def test_create_table_blocks_for_page_creates_candidate() -> None:
    """Table candidate text should create a TableBlock."""
    text = (
        "Category    Description\nHigh        Severe impact\nLow         Minor impact"
    )
    text_block = _text_block(text, normalized_text=text)
    page = Page(page_number=1, text_blocks=[text_block], blocks=[text_block])

    tables = create_table_blocks_for_page(page)

    assert len(tables) == 1
    assert isinstance(tables[0], TableBlock)
    assert tables[0].block_type == "table"
    assert tables[0].text == text
    assert tables[0].normalized_text == text
    assert tables[0].source is text_block.source
    assert tables[0].source_text_block_ids == ["text-1"]
    assert tables[0].is_candidate is True
    assert tables[0].rows


def test_create_table_blocks_for_page_skips_long_prose_false_positive() -> None:
    """Long numbered prose should not create table candidates."""
    text = (
        "5. This revision incorporates changes to meet Government and industry "
        "requests to reinstate task descriptions and improve the standard."
    )
    text_block = _text_block(text, normalized_text=text)
    page = Page(page_number=1, text_blocks=[text_block], blocks=[text_block])

    assert create_table_blocks_for_page(page) == []


def test_create_table_blocks_for_page_preserves_table_candidate_fields() -> None:
    """Real table candidates should preserve source references."""
    text = "TABLE II. Probability levels"
    text_block = _text_block(text, normalized_text=text)
    page = Page(page_number=1, text_blocks=[text_block], blocks=[text_block])

    tables = create_table_blocks_for_page(page)

    assert len(tables) == 1
    assert tables[0].text == text
    assert tables[0].source is text_block.source
    assert tables[0].source_text_block_ids == ["text-1"]
    assert tables[0].is_candidate is True


def test_create_table_blocks_for_page_skips_page_furniture() -> None:
    """Page furniture should not create table candidates."""
    text_block = _text_block("Entity\nPurpose\nKey links\nWhy it matters")
    text_block.is_page_furniture = True
    page = Page(page_number=1, text_blocks=[text_block], blocks=[text_block])

    assert create_table_blocks_for_page(page) == []


def test_create_table_blocks_for_page_skips_heading_text() -> None:
    """Text matching an existing heading should not become a table candidate."""
    text_block = _text_block("III. Risk assessment matrix", normalized_text="1. SCOPE")
    heading = HeadingBlock(
        id="heading-1",
        source=text_block.source,
        text="1. SCOPE",
        normalized_text="1. SCOPE",
        level=1,
    )
    page = Page(page_number=1, text_blocks=[text_block], blocks=[text_block, heading])

    assert create_table_blocks_for_page(page) == []
