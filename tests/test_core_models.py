"""Tests for core document data models."""

import json

import pytest

from techdoc_parser.core import (
    Block,
    BoundingBox,
    Document,
    DocumentMetadata,
    FigureBlock,
    FormulaBlock,
    HeadingBlock,
    Page,
    SourceLocation,
    TableBlock,
    TextBlock,
)


def test_bounding_box_serialization() -> None:
    """BoundingBox should serialize its coordinates."""
    bbox = BoundingBox(x0=1.0, y0=2.0, x1=3.0, y1=4.0)

    assert bbox.to_dict() == {
        "x0": 1.0,
        "y0": 2.0,
        "x1": 3.0,
        "y1": 4.0,
    }


def test_bounding_box_rejects_invalid_coordinates() -> None:
    """BoundingBox should reject reversed coordinates."""
    with pytest.raises(ValueError, match="x1"):
        BoundingBox(x0=2.0, y0=0.0, x1=1.0, y1=1.0)

    with pytest.raises(ValueError, match="y1"):
        BoundingBox(x0=0.0, y0=2.0, x1=1.0, y1=1.0)


def test_source_location_serialization_without_bbox() -> None:
    """SourceLocation should serialize without optional fields."""
    source = SourceLocation(document_path="sample.pdf")

    assert source.to_dict() == {
        "document_path": "sample.pdf",
        "page_number": None,
        "bbox": None,
        "extraction_method": None,
        "confidence": None,
    }


def test_source_location_serialization_with_bbox() -> None:
    """SourceLocation should serialize nested bounding boxes."""
    bbox = BoundingBox(x0=1.0, y0=2.0, x1=3.0, y1=4.0)
    source = SourceLocation(
        document_path="sample.pdf",
        page_number=1,
        bbox=bbox,
        extraction_method="unit-test",
        confidence=0.95,
    )

    assert source.to_dict() == {
        "document_path": "sample.pdf",
        "page_number": 1,
        "bbox": bbox.to_dict(),
        "extraction_method": "unit-test",
        "confidence": 0.95,
    }


def test_source_location_rejects_invalid_confidence() -> None:
    """SourceLocation should reject confidence values outside 0.0 to 1.0."""
    with pytest.raises(ValueError, match="confidence"):
        SourceLocation(document_path="sample.pdf", confidence=-0.1)

    with pytest.raises(ValueError, match="confidence"):
        SourceLocation(document_path="sample.pdf", confidence=1.1)


def test_block_serialization() -> None:
    """Block should serialize common block fields."""
    source = SourceLocation(document_path="sample.pdf", page_number=1)
    block = Block(
        id="block-1",
        source=source,
        block_type="custom",
        text="Example text",
        normalized_text="Example text",
    )

    assert block.to_dict() == {
        "id": "block-1",
        "source": source.to_dict(),
        "block_type": "custom",
        "text": "Example text",
        "normalized_text": "Example text",
    }


def test_text_block_serialization() -> None:
    """TextBlock should serialize its text and source."""
    source = SourceLocation(document_path="sample.pdf", page_number=1)
    block = TextBlock(
        id="block-1",
        text="Example text",
        source=source,
        normalized_text="Example text",
    )

    assert block.to_dict() == {
        "id": "block-1",
        "text": "Example text",
        "source": source.to_dict(),
        "block_type": "text",
        "normalized_text": "Example text",
    }


def test_heading_block_serialization() -> None:
    """HeadingBlock should serialize heading-specific fields."""
    source = SourceLocation(document_path="sample.pdf", page_number=1)
    block = HeadingBlock(
        id="heading-1",
        source=source,
        text="Introduction",
        normalized_text="Introduction",
        level=2,
    )

    assert block.to_dict() == {
        "id": "heading-1",
        "source": source.to_dict(),
        "block_type": "heading",
        "text": "Introduction",
        "normalized_text": "Introduction",
        "level": 2,
    }


def test_heading_block_rejects_invalid_level() -> None:
    """HeadingBlock should reject levels less than one."""
    source = SourceLocation(document_path="sample.pdf", page_number=1)

    with pytest.raises(ValueError, match="level"):
        HeadingBlock(id="heading-1", source=source, level=0)


def test_table_block_serialization() -> None:
    """TableBlock should serialize table-specific fields."""
    source = SourceLocation(document_path="sample.pdf", page_number=1)
    rows = [["A", "B"], ["1", "2"]]
    block = TableBlock(
        id="table-1",
        source=source,
        text="A B\n1 2",
        caption="Example table",
        rows=rows,
    )

    assert block.to_dict() == {
        "id": "table-1",
        "source": source.to_dict(),
        "block_type": "table",
        "text": "A B\n1 2",
        "normalized_text": None,
        "caption": "Example table",
        "rows": rows,
    }


def test_formula_block_serialization() -> None:
    """FormulaBlock should serialize formula-specific fields."""
    source = SourceLocation(document_path="sample.pdf", page_number=1)
    block = FormulaBlock(
        id="formula-1",
        source=source,
        text="E = mc^2",
        latex="E = mc^2",
        variables=["E", "m", "c"],
    )

    assert block.to_dict() == {
        "id": "formula-1",
        "source": source.to_dict(),
        "block_type": "formula",
        "text": "E = mc^2",
        "normalized_text": None,
        "latex": "E = mc^2",
        "variables": ["E", "m", "c"],
    }


def test_figure_block_serialization() -> None:
    """FigureBlock should serialize figure-specific fields."""
    source = SourceLocation(document_path="sample.pdf", page_number=1)
    block = FigureBlock(
        id="figure-1",
        source=source,
        caption="Example figure",
        image_path="images/figure-1.png",
    )

    assert block.to_dict() == {
        "id": "figure-1",
        "source": source.to_dict(),
        "block_type": "figure",
        "text": None,
        "normalized_text": None,
        "caption": "Example figure",
        "image_path": "images/figure-1.png",
    }


def test_page_serialization_with_text_blocks() -> None:
    """Page should serialize its dimensions and text blocks."""
    source = SourceLocation(document_path="sample.pdf", page_number=1)
    block = TextBlock(id="block-1", text="Example text", source=source)
    page = Page(page_number=1, width=612.0, height=792.0, text_blocks=[block])

    assert page.to_dict() == {
        "page_number": 1,
        "width": 612.0,
        "height": 792.0,
        "has_native_text": False,
        "requires_ocr": False,
        "blocks": [],
        "text_blocks": [block.to_dict()],
    }


def test_page_serialization_with_generic_blocks() -> None:
    """Page should serialize generic document blocks."""
    source = SourceLocation(document_path="sample.pdf", page_number=1)
    block = Block(id="block-1", source=source, block_type="custom")
    page = Page(page_number=1, width=612.0, height=792.0, blocks=[block])

    assert page.to_dict() == {
        "page_number": 1,
        "width": 612.0,
        "height": 792.0,
        "has_native_text": False,
        "requires_ocr": False,
        "blocks": [block.to_dict()],
        "text_blocks": [],
    }


def test_page_blocks_can_contain_heading_block() -> None:
    """Page blocks should support heading blocks."""
    source = SourceLocation(document_path="sample.pdf", page_number=1)
    block = HeadingBlock(id="heading-1", source=source, text="Overview", level=1)
    page = Page(page_number=1, blocks=[block])

    assert page.to_dict()["blocks"] == [block.to_dict()]


def test_page_blocks_can_contain_table_block() -> None:
    """Page blocks should support table blocks."""
    source = SourceLocation(document_path="sample.pdf", page_number=1)
    block = TableBlock(id="table-1", source=source, rows=[["A", "B"]])
    page = Page(page_number=1, blocks=[block])

    assert page.to_dict()["blocks"] == [block.to_dict()]


def test_page_rejects_invalid_page_number() -> None:
    """Page should reject page numbers less than one."""
    with pytest.raises(ValueError, match="page_number"):
        Page(page_number=0)


def test_document_serialization() -> None:
    """Document should serialize metadata and pages."""
    metadata = DocumentMetadata(title="Sample", keywords=["tech", "doc"])
    page = Page(page_number=1)
    document = Document(
        id="doc-1",
        source_path="sample.pdf",
        metadata=metadata,
        pages=[page],
    )

    assert document.to_dict() == {
        "id": "doc-1",
        "source_path": "sample.pdf",
        "metadata": metadata.to_dict(),
        "pages": [page.to_dict()],
    }


def test_document_to_json_returns_valid_json() -> None:
    """Document.to_json should return parseable JSON."""
    document = Document(
        id="doc-1",
        source_path="sample.pdf",
        metadata=DocumentMetadata(title="Sample"),
        pages=[Page(page_number=1)],
    )

    data = json.loads(document.to_json())

    assert data["id"] == "doc-1"
    assert data["source_path"] == "sample.pdf"
    assert data["metadata"]["title"] == "Sample"
    assert data["pages"][0]["page_number"] == 1
