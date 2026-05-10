"""Tests for conservative figure candidate detection."""

from techdoc_parser.core import FigureBlock, Page, SourceLocation, TextBlock
from techdoc_parser.structure import (
    create_figure_blocks_for_page,
    is_figure_caption_text,
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


def test_is_figure_caption_text_detects_obvious_captions() -> None:
    """Obvious figure captions should be detected."""
    assert is_figure_caption_text(
        "FIGURE B-1. Assessing software\u2019s contribution to risk"
    )
    assert is_figure_caption_text(
        "Figure B-1. Assessing software\u2019s contribution to risk"
    )
    assert is_figure_caption_text("FIGURE 1. System overview")
    assert is_figure_caption_text("Figure 1. System overview")
    assert is_figure_caption_text("Figure 2. Detailed architecture")
    assert is_figure_caption_text("Figure A-1. Example workflow")
    assert is_figure_caption_text("FIGURE A-2. Example diagram")


def test_is_figure_caption_text_rejects_false_positives() -> None:
    """Figure references and non-caption structural text should not be detected."""
    assert not is_figure_caption_text("See Figure 1 for details.")
    assert not is_figure_caption_text("The process is shown in Figure 2.")
    assert not is_figure_caption_text("TABLE I. Severity categories")
    assert not is_figure_caption_text("1. SCOPE")
    assert not is_figure_caption_text("MIL-STD-882E")
    assert not is_figure_caption_text(
        "Source: https://assist.dla.mil -- Downloaded: 2026-05-09T06:31Z"
    )
    assert not is_figure_caption_text(
        "Element 4:\nIdentify and Document\nRisk Mitigation Measures"
    )
    assert not is_figure_caption_text(
        "Hazard Tracking Log\nHazard Title\nHazard Description\nHazard Causes"
    )


def test_create_figure_blocks_for_page_creates_candidate() -> None:
    """Figure caption text should create a FigureBlock candidate."""
    text = "FIGURE 1. System overview"
    text_block = _text_block(text, normalized_text=text)
    page = Page(page_number=1, text_blocks=[text_block], blocks=[text_block])

    figures = create_figure_blocks_for_page(page)

    assert len(figures) == 1
    assert isinstance(figures[0], FigureBlock)
    assert figures[0].block_type == "figure"
    assert figures[0].source is text_block.source
    assert figures[0].text == text
    assert figures[0].normalized_text == text
    assert figures[0].caption == text
    assert figures[0].source_text_block_ids == ["text-1"]
    assert figures[0].is_candidate is True


def test_create_figure_blocks_for_page_skips_reference_paragraph() -> None:
    """Normal figure reference paragraphs should not create FigureBlock objects."""
    text = "See Figure 1 for details."
    text_block = _text_block(text, normalized_text=text)
    page = Page(page_number=1, text_blocks=[text_block], blocks=[text_block])

    assert create_figure_blocks_for_page(page) == []


def test_create_figure_blocks_for_page_skips_page_furniture() -> None:
    """Page furniture should not create FigureBlock objects."""
    text = "FIGURE 1. System overview"
    text_block = _text_block(text, normalized_text=text)
    text_block.is_page_furniture = True
    page = Page(page_number=1, text_blocks=[text_block], blocks=[text_block])

    assert create_figure_blocks_for_page(page) == []
