"""Tests for conservative heading detection."""

from techdoc_parser.core import HeadingBlock, SourceLocation, TextBlock
from techdoc_parser.structure import (
    create_heading_block_from_text_block,
    detect_heading_level,
    is_heading_text,
)


def test_is_heading_text_detects_known_heading_patterns() -> None:
    """Common technical-document heading patterns should be detected."""
    headings = [
        "ABSTRACT",
        "EXECUTIVE SUMMARY",
        "Contents",
        "CHAPTER 1 - Introduction",
        "CHAPTER 10 - AI Analysis Workflow",
        "ANNEX A - Operational Checklists",
        "1. Introduction",
        "1.1 Scope",
        "2.3.4 Test Conditions",
        "A.1 Data Upload Checklist",
        "Overview",
        "Backend",
        "Docker",
    ]

    for heading in headings:
        assert is_heading_text(heading)


def test_is_heading_text_rejects_false_positives() -> None:
    """Paragraphs, bullets, footers, and TOC entries should not be headings."""
    false_positives = [
        (
            "This is a normal paragraph with enough words to represent body text "
            "rather than a structural heading in a technical manual."
        ),
        "- Overview",
        "FTIAS Manual | V-00 | Page 16 Friday, April 24, 2026",
        "Overview ................................................................ 16",
        "CHAPTER 1 - Introduction ...................................... 15",
        "This is a normal sentence ending with punctuation.",
    ]

    for text in false_positives:
        assert not is_heading_text(text)


def test_detect_heading_level() -> None:
    """Heading levels should follow the initial heuristic mapping."""
    assert detect_heading_level("CHAPTER 1 - Introduction") == 1
    assert detect_heading_level("ANNEX A - Operational Checklists") == 1
    assert detect_heading_level("1. Introduction") == 1
    assert detect_heading_level("1.1 Scope") == 2
    assert detect_heading_level("2.3.4 Test Conditions") == 3
    assert detect_heading_level("B.3 Risk Categories") == 2
    assert detect_heading_level("Overview") == 2


def test_create_heading_block_from_text_block_returns_heading() -> None:
    """Heading text blocks should produce HeadingBlock objects."""
    source = SourceLocation(document_path="manual.pdf", page_number=1)
    text_block = TextBlock(
        id="page-1-text-1",
        text="CHAPTER 1 - Introduction",
        source=source,
        normalized_text="CHAPTER 1 - Introduction",
    )

    heading = create_heading_block_from_text_block(text_block)

    assert isinstance(heading, HeadingBlock)
    assert heading.id == "page-1-heading-1"
    assert heading.text == "CHAPTER 1 - Introduction"
    assert heading.normalized_text == "CHAPTER 1 - Introduction"
    assert heading.source is source
    assert heading.block_type == "heading"
    assert heading.level == 1


def test_create_heading_block_from_text_block_returns_none_for_paragraph() -> None:
    """Normal paragraph text blocks should not produce HeadingBlock objects."""
    source = SourceLocation(document_path="manual.pdf", page_number=1)
    text_block = TextBlock(
        id="page-1-text-1",
        text="This is a normal sentence ending with punctuation.",
        source=source,
        normalized_text="This is a normal sentence ending with punctuation.",
    )

    assert create_heading_block_from_text_block(text_block) is None


def test_create_heading_block_from_text_block_uses_normalized_text() -> None:
    """Normalized text should drive detection when present."""
    source = SourceLocation(document_path="manual.pdf", page_number=1)
    text_block = TextBlock(
        id="custom-id",
        text="  Overview  ",
        source=source,
        normalized_text="Overview",
    )

    heading = create_heading_block_from_text_block(text_block)

    assert isinstance(heading, HeadingBlock)
    assert heading.id == "custom-id-heading"
    assert heading.text == "  Overview  "
    assert heading.normalized_text == "Overview"
    assert heading.source is source
    assert heading.block_type == "heading"
    assert heading.level == 2
