"""Tests for core document data models."""

import json

import pytest

from techdoc_parser.core import (
    BoundingBox,
    Document,
    DocumentMetadata,
    Page,
    SourceLocation,
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


def test_page_serialization() -> None:
    """Page should serialize its dimensions and text blocks."""
    source = SourceLocation(document_path="sample.pdf", page_number=1)
    block = TextBlock(id="block-1", text="Example text", source=source)
    page = Page(page_number=1, width=612.0, height=792.0, text_blocks=[block])

    assert page.to_dict() == {
        "page_number": 1,
        "width": 612.0,
        "height": 792.0,
        "text_blocks": [block.to_dict()],
    }


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
