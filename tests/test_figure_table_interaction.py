"""Tests for figure-context table candidate suppression."""

from techdoc_parser.core import FigureBlock, Page, SourceLocation, TableBlock, TextBlock
from techdoc_parser.structure import create_table_blocks_for_page


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


def _figure_block() -> FigureBlock:
    return FigureBlock(
        id="figure-1",
        source=_source(),
        text="FIGURE B-1. Assessing software's contribution to risk",
        normalized_text="FIGURE B-1. Assessing software's contribution to risk",
        caption="FIGURE B-1. Assessing software's contribution to risk",
        source_text_block_ids=["caption-1"],
        is_candidate=True,
    )


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
