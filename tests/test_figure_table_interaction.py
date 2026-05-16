"""Tests for figure-context table candidate suppression."""

import pytest

from techdoc_parser.core import (
    BoundingBox,
    FigureBlock,
    Page,
    SourceLocation,
    TableBlock,
    TextBlock,
)
from techdoc_parser.structure import create_table_blocks_for_page


def _source(bbox: BoundingBox | None = None) -> SourceLocation:
    return SourceLocation(document_path="manual.pdf", page_number=1, bbox=bbox)


def _text_block(
    text: str,
    *,
    id: str = "text-1",
    normalized_text: str | None = None,
    bbox: BoundingBox | None = None,
) -> TextBlock:
    return TextBlock(
        id=id,
        text=text,
        source=_source(bbox),
        normalized_text=normalized_text,
    )


def _figure_block(bbox: BoundingBox | None = None) -> FigureBlock:
    return FigureBlock(
        id="figure-1",
        source=_source(bbox),
        text="FIGURE B-1. Assessing software's contribution to risk",
        normalized_text="FIGURE B-1. Assessing software's contribution to risk",
        caption="FIGURE B-1. Assessing software's contribution to risk",
        source_text_block_ids=["caption-1"],
        is_candidate=True,
    )


@pytest.mark.parametrize(
    "text",
    [
        "Hazard Tracking Log\nHazard Title\nHazard Description\nHazard Causes",
        "System Risk\n(Accepted in accordance\nwith applicable DoDI\n5000 Series)",
        (
            "Safety-significant Software\nFunctions\n"
            "\u2022 Causes, controls\n\u2022 Verification\u2014SwCI, LOR"
        ),
        (
            "System and Software System\nSafety Programs, Software\n"
            "Development Process,\nSafety-Significant Software,\n"
            "SSCM, SwCI\nSwSS design reqts., LOR"
        ),
        (
            "CM/Drawing Control\nEngineering Design Process\n"
            "Process/Part Selection and\nControl, Verification, MIL-STDs"
        ),
        "Operator Training, Demos,\nTests, Warnings/Cautions,\nTMs, HFE/HMI, MIL-STDs",
    ],
)
def test_figure_context_suppresses_mil_std_figure_internal_labels(
    text: str,
) -> None:
    """MIL-STD FIGURE B-1 internal labels should not create table candidates."""
    text_block = _text_block(text, normalized_text=text)
    figure = _figure_block()
    page = Page(
        page_number=1,
        text_blocks=[text_block],
        blocks=[text_block, figure],
    )

    assert create_table_blocks_for_page(page) == []


def test_figure_context_suppresses_form_template_label_table_candidate() -> None:
    """Figure-internal form/template labels should not create TableBlock objects."""
    text = "Hazard Tracking Log\nHazard Title\nHazard Description\nHazard Causes"
    text_block = _text_block(text, normalized_text=text)
    figure = _figure_block()
    page = Page(
        page_number=1,
        text_blocks=[text_block],
        blocks=[text_block, figure],
    )

    assert create_table_blocks_for_page(page) == []


def test_figure_context_suppresses_process_element_table_candidate() -> None:
    """Figure-internal process element labels should not create TableBlock objects."""
    text = "Element 4:\nIdentify and Document\nRisk Mitigation Measures"
    text_block = _text_block(text, normalized_text=text)
    figure = _figure_block()
    page = Page(
        page_number=1,
        text_blocks=[text_block],
        blocks=[text_block, figure],
    )

    assert create_table_blocks_for_page(page) == []


def test_figure_context_suppresses_input_process_output_label() -> None:
    """Compact diagram labels should be suppressed when figure context exists."""
    text = "Input\nProcess\nOutput"
    text_block = _text_block(text, normalized_text=text)
    figure = _figure_block()
    page = Page(
        page_number=1,
        text_blocks=[text_block],
        blocks=[text_block, figure],
    )

    assert create_table_blocks_for_page(page) == []


def test_bottom_figure_caption_suppresses_nearby_label_above_caption() -> None:
    """Labels above a bottom figure caption should be suppressed conservatively."""
    text = "System Risk\n(Accepted in accordance\nwith applicable DoDI\n5000 Series)"
    text_block = _text_block(
        text,
        normalized_text=text,
        bbox=BoundingBox(x0=100.0, y0=430.0, x1=300.0, y1=500.0),
    )
    figure = _figure_block(bbox=BoundingBox(x0=80.0, y0=620.0, x1=520.0, y1=650.0))
    page = Page(
        page_number=1,
        width=600.0,
        height=800.0,
        text_blocks=[text_block],
        blocks=[text_block, figure],
    )

    assert create_table_blocks_for_page(page) == []


def test_figure_context_preserves_table_caption_candidate() -> None:
    """Figure context must not suppress real table captions."""
    text = "TABLE I. Severity categories"
    text_block = _text_block(text, normalized_text=text)
    figure = _figure_block()
    page = Page(
        page_number=1,
        text_blocks=[text_block],
        blocks=[text_block, figure],
    )

    tables = create_table_blocks_for_page(page)

    assert len(tables) == 1
    assert isinstance(tables[0], TableBlock)
    assert tables[0].text == text
    assert tables[0].source_text_block_ids == ["text-1"]
    assert tables[0].is_candidate is True


def test_figure_context_preserves_table_header_candidate() -> None:
    """Figure context must not suppress real table header blocks."""
    text = "Description\nSeverity\nCategory\nMishap Result Criteria"
    text_block = _text_block(text, normalized_text=text)
    figure = _figure_block()
    page = Page(
        page_number=1,
        text_blocks=[text_block],
        blocks=[text_block, figure],
    )

    tables = create_table_blocks_for_page(page)

    assert len(tables) == 1
    assert tables[0].text == text
    assert tables[0].is_candidate is True


def test_table_caption_candidate_still_created_without_figure_context() -> None:
    """Normal table candidate behavior should continue without figure context."""
    text = "TABLE II. Probability levels"
    text_block = _text_block(text, normalized_text=text)
    page = Page(page_number=1, text_blocks=[text_block], blocks=[text_block])

    tables = create_table_blocks_for_page(page)

    assert len(tables) == 1
    assert tables[0].text == text


def test_table_header_candidate_still_created_without_figure_context() -> None:
    """Table header candidate behavior should continue without figure context."""
    text = "Description\nSeverity\nCategory\nMishap Result Criteria"
    text_block = _text_block(text, normalized_text=text)
    page = Page(page_number=1, text_blocks=[text_block], blocks=[text_block])

    tables = create_table_blocks_for_page(page)

    assert len(tables) == 1
    assert tables[0].text == text


@pytest.mark.parametrize(
    "text",
    [
        (
            "(1) Figure B-1 illustrates the relationship between the software "
            "system safety activities and risk. Table B-I provides example "
            "criteria."
        ),
        (
            "d. Software system safety risk assessment. After completion of all "
            "specified software system safety engineering analysis..."
        ),
    ],
)
def test_figure_context_does_not_create_tables_for_normal_body_paragraphs(
    text: str,
) -> None:
    """Normal body paragraphs on figure pages should not create table candidates."""
    text_block = _text_block(text, normalized_text=text)
    figure = _figure_block()
    page = Page(
        page_number=1,
        text_blocks=[text_block],
        blocks=[text_block, figure],
    )

    assert create_table_blocks_for_page(page) == []
