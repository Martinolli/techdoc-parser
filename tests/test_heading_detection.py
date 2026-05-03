"""Tests for conservative heading detection."""

from techdoc_parser.core import HeadingBlock, SourceLocation, TextBlock
from techdoc_parser.structure import (
    create_heading_block_from_text_block,
    detect_heading_level,
    extract_heading_blocks_from_text_block,
    is_heading_text,
)
from techdoc_parser.structure.headings import is_table_of_contents_text


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
        "101.2.7 Some heading text",
        "101.2.8 As a minimum, report the following:",
        "101.2.9 Some heading text",
        "101.3 Some heading text",
        "TASK 101",
        (
            "TASK 101 HAZARD IDENTIFICATION AND MITIGATION EFFORT USING THE "
            "SYSTEM SAFETY METHODOLOGY"
        ),
        "TASK SECTION 100 - MANAGEMENT",
        "APPENDIX A GUIDANCE FOR THE SYSTEM SAFETY EFFORT",
        "APPENDIX B SOFTWARE SYSTEM SAFETY ENGINEERING AND ANALYSIS",
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
        "MIL-STD-882E",
        "Source: https://assist.dla.mil -- Downloaded by test@example.com",
        "EOD",
        "ESOH",
        "FHA",
        "MIL-STD",
        "1",
        "104",
        "IV",
        (
            "3.2.1 Acceptable Risk. Risk that the appropriate acceptance "
            "authority has accepted."
        ),
        (
            "1. This Standard is approved for use by all Military Departments "
            "and Defense Agencies"
        ),
        (
            "2. This system safety standard practice is a key element of Systems "
            "Engineering (SE) that"
        ),
        (
            "3. DoD is committed to protecting personnel from accidental death, "
            "injury, or occupational"
        ),
        (
            "6. Comments, suggestions, or questions on this document should be "
            "addressed to"
        ),
        "Appendix A for an example of quantitative probability levels",
        "See Appendix B for software safety analysis guidance",
        "Refer to Appendix A for additional information",
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
    assert detect_heading_level("TASK SECTION 100 - MANAGEMENT") == 1
    assert detect_heading_level("TASK 101") == 1
    assert detect_heading_level("APPENDIX A GUIDANCE FOR THE SYSTEM SAFETY EFFORT") == 1
    assert detect_heading_level("101.3 Details to be specified.") == 2
    assert detect_heading_level("101.2.8 As a minimum, report the following:") == 3
    assert detect_heading_level("2.2 Government documents") == 2
    assert detect_heading_level("2.2.1 Specifications, standards, and handbooks") == 3


def test_true_standard_headings_are_preserved() -> None:
    """Context-aware filtering should preserve known true technical headings."""
    headings = {
        "1. SCOPE": 1,
        "2. APPLICABLE DOCUMENTS": 1,
        "3. DEFINITIONS": 1,
        "4. GENERAL REQUIREMENTS": 1,
        "5. DETAILED REQUIREMENTS": 1,
        "6. NOTES": 1,
        "2.2 Government documents": 2,
        "2.2.1 Specifications, standards, and handbooks": 3,
        "4.3 System safety process": 2,
        "TASK SECTION 100 - MANAGEMENT": 1,
        "TASK 101": 1,
        "APPENDIX A GUIDANCE FOR THE SYSTEM SAFETY EFFORT": 1,
    }

    for heading, level in headings.items():
        assert is_heading_text(heading)
        assert detect_heading_level(heading) == level


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


def test_extract_heading_blocks_from_text_block_returns_isolated_heading() -> None:
    """Isolated heading blocks should still produce one HeadingBlock."""
    source = SourceLocation(document_path="manual.pdf", page_number=1)
    text_block = TextBlock(
        id="page-1-text-1",
        text="1. SCOPE",
        source=source,
        normalized_text="1. SCOPE",
    )

    headings = extract_heading_blocks_from_text_block(text_block)

    assert len(headings) == 1
    assert headings[0].id == "page-1-heading-1"
    assert headings[0].text == "1. SCOPE"
    assert headings[0].normalized_text == "1. SCOPE"
    assert headings[0].source is source
    assert headings[0].level == 1


def test_extract_heading_blocks_returns_multiple_line_headings() -> None:
    """Multiline text blocks can contain multiple embedded headings."""
    source = SourceLocation(document_path="manual.pdf", page_number=7)
    text_block = TextBlock(
        id="page-7-text-4",
        text=(
            "This paragraph introduces the page.\n\n"
            "2. APPLICABLE DOCUMENTS\n"
            "Body text follows.\n"
            "2.2 Government documents\n"
            "2.2.1 Specifications, standards, and handbooks"
        ),
        source=source,
        normalized_text=(
            "This paragraph introduces the page.\n\n"
            "2. APPLICABLE DOCUMENTS\n"
            "Body text follows.\n"
            "2.2 Government documents\n"
            "2.2.1 Specifications, standards, and handbooks"
        ),
    )

    headings = extract_heading_blocks_from_text_block(text_block)

    assert [heading.normalized_text for heading in headings] == [
        "2. APPLICABLE DOCUMENTS",
        "2.2 Government documents",
        "2.2.1 Specifications, standards, and handbooks",
    ]
    assert [heading.id for heading in headings] == [
        "page-7-text-4-line-heading-1",
        "page-7-text-4-line-heading-2",
        "page-7-text-4-line-heading-3",
    ]
    assert [heading.level for heading in headings] == [1, 2, 3]
    assert all(heading.source is source for heading in headings)


def test_extract_heading_blocks_from_text_block_detects_mil_std_headings() -> None:
    """MIL-STD task and appendix headings should be extracted line by line."""
    source = SourceLocation(document_path="mil_std_882e.pdf", page_number=20)
    text_block = TextBlock(
        id="page-20-text-3",
        text=(
            "101.2.8 As a minimum, report the following:\n"
            "101.3 Details to be specified.\n"
            "TASK 101\n"
            "TASK SECTION 100 - MANAGEMENT\n"
            "APPENDIX A GUIDANCE FOR THE SYSTEM SAFETY EFFORT"
        ),
        source=source,
        normalized_text=(
            "101.2.8 As a minimum, report the following:\n"
            "101.3 Details to be specified.\n"
            "TASK 101\n"
            "TASK SECTION 100 - MANAGEMENT\n"
            "APPENDIX A GUIDANCE FOR THE SYSTEM SAFETY EFFORT"
        ),
    )

    headings = extract_heading_blocks_from_text_block(text_block)

    assert [heading.normalized_text for heading in headings] == [
        "101.2.8 As a minimum, report the following:",
        "101.3 Details to be specified.",
        "TASK 101",
        "TASK SECTION 100 - MANAGEMENT",
        "APPENDIX A GUIDANCE FOR THE SYSTEM SAFETY EFFORT",
    ]
    assert [heading.level for heading in headings] == [3, 2, 1, 1, 1]


def test_extract_heading_blocks_from_text_block_avoids_duplicates() -> None:
    """Duplicate heading lines from one text block should produce one heading."""
    source = SourceLocation(document_path="manual.pdf", page_number=1)
    text_block = TextBlock(
        id="page-1-text-2",
        text="Overview\nOverview",
        source=source,
        normalized_text="Overview\nOverview",
    )

    headings = extract_heading_blocks_from_text_block(text_block)

    assert len(headings) == 1
    assert headings[0].normalized_text == "Overview"

    unnormalized_text_block = TextBlock(
        id="page-1-text-3",
        text="Overview",
        source=source,
    )

    assert len(extract_heading_blocks_from_text_block(unnormalized_text_block)) == 1


def test_extract_heading_blocks_from_text_block_rejects_line_false_positives() -> None:
    """Line-level extraction should keep conservative false-positive filtering."""
    source = SourceLocation(document_path="mil_std_882e.pdf", page_number=4)
    text_block = TextBlock(
        id="page-4-text-2",
        text=(
            "MIL-STD-882E\n"
            "Source: https://assist.dla.mil -- Downloaded by test@example.com\n"
            "EOD\n"
            "ESOH\n"
            "Overview ........................................................ 16\n"
            "This is an ordinary sentence paragraph.\n"
            "3.2.1 Acceptable Risk. Risk that the appropriate acceptance "
            "authority has accepted."
        ),
        source=source,
        normalized_text=(
            "MIL-STD-882E\n"
            "Source: https://assist.dla.mil -- Downloaded by test@example.com\n"
            "EOD\n"
            "ESOH\n"
            "Overview ........................................................ 16\n"
            "This is an ordinary sentence paragraph.\n"
            "3.2.1 Acceptable Risk. Risk that the appropriate acceptance "
            "authority has accepted."
        ),
    )

    assert extract_heading_blocks_from_text_block(text_block) == []


def test_is_table_of_contents_text_detects_toc_like_block() -> None:
    """TOC-like blocks should be identified from headings, columns, and dot leaders."""
    text = (
        "CONTENTS\n"
        "PARAGRAPH PAGE\n"
        "FOREWORD ................................................................ ii\n"
        "1. SCOPE ................................................................ 1\n"
        "TASK 102 SYSTEM SAFETY PROGRAM PLAN .............................. 24\n"
        "TASK 201 PRELIMINARY HAZARD LIST ................................. 44\n"
    )

    assert is_table_of_contents_text(text)


def test_extract_heading_blocks_from_toc_like_block_returns_only_contents() -> None:
    """Only the Contents heading should survive within TOC-like blocks."""
    source = SourceLocation(document_path="mil_std_882e.pdf", page_number=3)
    text_block = TextBlock(
        id="page-3-text-1",
        text=(
            "CONTENTS\n"
            "PARAGRAPH PAGE\n"
            "FOREWORD .......................................................... ii\n"
            "1. SCOPE .......................................................... 1\n"
            "TASK 102 SYSTEM SAFETY PROGRAM PLAN .............................. 24\n"
            "APPENDIX A GUIDANCE FOR THE SYSTEM SAFETY EFFORT ................. 90"
        ),
        source=source,
        normalized_text=(
            "CONTENTS\n"
            "PARAGRAPH PAGE\n"
            "FOREWORD .......................................................... ii\n"
            "1. SCOPE .......................................................... 1\n"
            "TASK 102 SYSTEM SAFETY PROGRAM PLAN .............................. 24\n"
            "APPENDIX A GUIDANCE FOR THE SYSTEM SAFETY EFFORT ................. 90"
        ),
    )

    headings = extract_heading_blocks_from_text_block(text_block)

    assert [heading.normalized_text for heading in headings] == ["CONTENTS"]


def test_toc_task_and_appendix_entries_are_not_headings() -> None:
    """TOC task and appendix entries with dot leaders should be rejected."""
    false_positives = [
        (
            "TASK 102 SYSTEM SAFETY PROGRAM PLAN "
            "........................................................ 24"
        ),
        (
            "TASK 201 PRELIMINARY HAZARD LIST "
            "........................................................ 44"
        ),
        (
            "APPENDIX A GUIDANCE FOR THE SYSTEM SAFETY EFFORT "
            "....................................90"
        ),
    ]

    for text in false_positives:
        assert not is_heading_text(text)


def test_numbered_body_paragraphs_are_not_headings() -> None:
    """Foreword/body numbered paragraphs should not become headings."""
    false_positives = [
        (
            "1. This Standard is approved for use by all Military Departments "
            "and Defense Agencies"
        ),
        (
            "2. This system safety standard practice is a key element of Systems "
            "Engineering (SE) that"
        ),
        (
            "3. DoD is committed to protecting personnel from accidental death, "
            "injury, or occupational"
        ),
        (
            "6. Comments, suggestions, or questions on this document should be "
            "addressed to"
        ),
    ]

    for text in false_positives:
        assert not is_heading_text(text)


def test_sentence_like_appendix_references_are_not_headings() -> None:
    """Appendix references inside prose should not become headings."""
    false_positives = [
        "Appendix A for an example of quantitative probability levels",
        "See Appendix B for software safety analysis guidance",
        "Refer to Appendix A for additional information",
    ]

    for text in false_positives:
        assert not is_heading_text(text)
