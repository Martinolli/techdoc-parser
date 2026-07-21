"""Tests for parser-model to structured-document contract mapping."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techdoc_parser.contracts import (
    STRUCTURED_DOCUMENT_SCHEMA_NAME,
    STRUCTURED_DOCUMENT_SCHEMA_VERSION,
    StructuredDocumentMappingOptions,
    map_block_type_to_content_type,
    map_document_to_structured_document,
    map_document_with_options,
    structured_document_to_dict,
    structured_document_to_json,
)
from techdoc_parser.core import (
    Block,
    BoundingBox,
    Document,
    DocumentMetadata,
    FigureBlock,
    FormulaBlock,
    HeadingBlock,
    Page,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
    TableRegionBlock,
    TextBlock,
)

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "structured_document"
    / "mapped_structured_document.json"
)


def test_parser_document_maps_successfully_to_contract_shape() -> None:
    mapped = map_document_to_structured_document(
        _parser_document(),
        document_id="explicit-doc-id",
        document_title="Synthetic Hydraulic Inspection Guide",
    )
    data = structured_document_to_dict(mapped)

    assert data["schema_name"] == STRUCTURED_DOCUMENT_SCHEMA_NAME
    assert data["schema_version"] == STRUCTURED_DOCUMENT_SCHEMA_VERSION
    assert data["parser_name"] == "techdoc-parser"
    assert data["parser_version"] == "0.1.0"
    assert data["document"] == {
        "document_id": "explicit-doc-id",
        "source_filename": "synthetic-hydraulic-inspection-guide.pdf",
        "document_title": "Synthetic Hydraulic Inspection Guide",
        "canonical_title": "Synthetic Metadata Title",
        "page_count": 2,
    }
    assert data["sections"] == []
    assert data["tables"] == []
    assert data["figures"] == []
    assert data["equations"] == []
    assert data["admonitions"] == []
    assert data["cross_references"] == []


def test_page_mapping_preserves_order_and_known_page_fields_only() -> None:
    data = structured_document_to_dict(
        map_document_to_structured_document(
            _parser_document(),
            document_id="explicit-doc-id",
        )
    )

    assert data["pages"] == [
        {
            "page_id": "page-0001",
            "pdf_page_index": 0,
            "page_number": 1,
            "printed_page_label": None,
        },
        {
            "page_id": "page-0002",
            "pdf_page_index": 1,
            "page_number": 2,
            "printed_page_label": None,
        },
    ]


def test_empty_pages_are_mapped_when_current_model_allows_them() -> None:
    document = Document(
        id="empty-pages",
        source_path="empty-pages.pdf",
        metadata=DocumentMetadata(),
        pages=[Page(page_number=1), Page(page_number=2)],
    )

    data = structured_document_to_dict(
        map_document_to_structured_document(document, document_id="empty-pages")
    )

    assert len(data["pages"]) == 2
    assert data["blocks"] == []


def test_block_mapping_preserves_text_order_indexes_ids_and_normalized_text() -> None:
    data = structured_document_to_dict(
        map_document_to_structured_document(
            _parser_document(),
            document_id="explicit-doc-id",
        )
    )
    blocks = data["blocks"]

    assert [block["block_id"] for block in blocks] == [
        "page-1-text-1",
        "page-1-heading-1",
        "page-1-paragraph-1",
        "page-2-paragraph-1",
        "explicit-doc-id:p1:b1",
    ]
    assert [block["block_type"] for block in blocks] == [
        "paragraph",
        "section_heading",
        "paragraph",
        "paragraph",
        "unknown",
    ]
    assert [block["document_block_index"] for block in blocks] == [0, 1, 2, 3, 4]
    assert [block["page_block_index"] for block in blocks] == [0, 1, 2, 0, 1]
    assert blocks[2]["text"] == "Inspect the synthetic pump housing.\nRecord findings."
    assert (
        blocks[2]["normalized_text"]
        == "Inspect the synthetic pump housing. Record findings."
    )
    assert "section_id" not in blocks[1]


def test_content_type_mapping_is_exhaustive_for_current_known_block_types() -> None:
    source = _source(page_number=1)
    furniture = TextBlock(
        id="footer",
        text="Page 1",
        source=source,
        is_page_footer=True,
        is_page_furniture=True,
    )

    cases = [
        (TextBlock(id="text", text="Text", source=source), "paragraph"),
        (furniture, "metadata"),
        (ParagraphBlock(id="paragraph", text="Paragraph", source=source), "paragraph"),
        (
            HeadingBlock(id="heading", source=source, text="1. Heading", level=1),
            "section_heading",
        ),
        (TableBlock(id="table", source=source, text="A B"), "table"),
        (TableRegionBlock(id="region", source=source, text="A B"), "table"),
        (
            FigureBlock(id="figure", source=source, text="FIGURE 1. Test"),
            "figure_caption",
        ),
        (FormulaBlock(id="formula", source=source, text="a=b"), "equation"),
        (
            Block(id="custom", source=source, block_type="custom", text="Custom"),
            "unknown",
        ),
    ]

    for block, expected in cases:
        assert map_block_type_to_content_type(block) == expected


def test_source_location_and_bounding_box_mapping_are_truthful() -> None:
    data = structured_document_to_dict(
        map_document_to_structured_document(
            _parser_document(),
            document_id="explicit-doc-id",
        )
    )
    first_block = data["blocks"][0]
    source_span = first_block["source_span"]

    assert first_block["bbox"] == {
        "x0": 72.0,
        "y0": 96.0,
        "x1": 420.0,
        "y1": 116.0,
    }
    assert source_span == {
        "page_start": 1,
        "page_end": 1,
        "pdf_page_index_start": 0,
        "pdf_page_index_end": 0,
        "bbox": first_block["bbox"],
        "source_block_ids": ["page-1-text-1"],
        "extraction_method": "pymupdf",
    }
    assert "char_start" not in source_span
    assert "char_end" not in source_span
    assert "confidence" not in source_span
    assert "source_hash" not in source_span


def test_missing_bounding_box_and_zero_coordinates_are_preserved() -> None:
    data = structured_document_to_dict(
        map_document_to_structured_document(
            _parser_document(),
            document_id="explicit-doc-id",
        )
    )
    zero_bbox_block = data["blocks"][3]
    missing_bbox_block = data["blocks"][4]

    assert zero_bbox_block["bbox"] == {
        "x0": 0.0,
        "y0": 0.0,
        "x1": 0.0,
        "y1": 0.0,
    }
    assert zero_bbox_block["source_span"]["bbox"] == zero_bbox_block["bbox"]
    assert "bbox" not in missing_bbox_block
    assert "bbox" not in missing_bbox_block["source_span"]


def test_metadata_is_not_inferred_from_filename_or_timestamps() -> None:
    document = Document(
        id="parser-id",
        source_path="C:\\source\\filename-title.pdf",
        metadata=DocumentMetadata(),
        pages=[Page(page_number=1)],
    )

    data = structured_document_to_dict(
        map_document_to_structured_document(document, document_id="explicit-id")
    )
    metadata = data["document"]

    assert metadata["document_id"] == "explicit-id"
    assert metadata["source_filename"] == "filename-title.pdf"
    assert "document_title" not in metadata
    assert "canonical_title" not in metadata
    assert "revision" not in metadata
    assert "issue" not in metadata
    assert "effective_date" not in metadata
    assert "source_hash" not in metadata


def test_explicit_caller_metadata_is_preserved() -> None:
    data = structured_document_to_dict(
        map_document_to_structured_document(
            _parser_document(),
            document_id="explicit-doc-id",
            document_title="Caller Title",
            revision="Rev A",
            issue="Issue 1",
            effective_date="2026-01-31",
            source_checksum="sha256:caller-supplied",
        )
    )

    assert data["document"]["document_title"] == "Caller Title"
    assert data["document"]["revision"] == "Rev A"
    assert data["document"]["issue"] == "Issue 1"
    assert data["document"]["effective_date"] == "2026-01-31"
    assert data["document"]["source_hash"] == "sha256:caller-supplied"


def test_mapping_options_are_immutable() -> None:
    options = StructuredDocumentMappingOptions(document_id="doc")

    with pytest.raises(Exception, match="cannot assign to field"):
        options.document_id = "changed"  # type: ignore[misc]


def test_normalized_text_can_be_excluded_without_changing_raw_text() -> None:
    data = structured_document_to_dict(
        map_document_to_structured_document(
            _parser_document(),
            document_id="explicit-doc-id",
            include_normalized_text=False,
        )
    )

    assert (
        data["blocks"][2]["text"]
        == "Inspect the synthetic pump housing.\nRecord findings."
    )
    assert "normalized_text" not in data["blocks"][2]


def test_mapping_is_deterministic_and_does_not_mutate_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    document = _parser_document()
    before = document.to_dict()

    first = map_document_to_structured_document(
        document,
        document_id="explicit-doc-id",
    )
    second = map_document_to_structured_document(
        document,
        document_id="explicit-doc-id",
    )

    assert structured_document_to_json(first) == structured_document_to_json(second)
    assert document.to_dict() == before
    assert list(tmp_path.iterdir()) == []


def test_mapper_rejects_blocks_without_raw_text_instead_of_fabricating_text() -> None:
    document = Document(
        id="doc",
        source_path="doc.pdf",
        metadata=DocumentMetadata(),
        pages=[
            Page(
                page_number=1,
                blocks=[Block(id="empty", source=None, block_type="custom")],
            )
        ],
    )

    with pytest.raises(ValueError, match="without non-empty raw text"):
        map_document_to_structured_document(document, document_id="doc")


def test_map_document_with_options_matches_keyword_api() -> None:
    document = _parser_document()
    options = StructuredDocumentMappingOptions(
        document_id="explicit-doc-id",
        document_title="Synthetic Hydraulic Inspection Guide",
    )

    assert structured_document_to_dict(
        map_document_with_options(document, options)
    ) == (
        structured_document_to_dict(
            map_document_to_structured_document(
                document,
                document_id="explicit-doc-id",
                document_title="Synthetic Hydraulic Inspection Guide",
            )
        )
    )


def test_expected_mapped_fixture_matches_output() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    generated = structured_document_to_dict(
        map_document_to_structured_document(
            _parser_document(),
            document_id="explicit-doc-id",
            document_title="Synthetic Hydraulic Inspection Guide",
        )
    )

    assert fixture == generated


def test_expected_mapped_fixture_is_valid_json_object() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert fixture["schema_name"] == "techdoc-structured-document"
    assert fixture["schema_version"] == "0.1.0"
    assert fixture["sections"] == []
    assert fixture["tables"] == []


def _parser_document() -> Document:
    source_path = "C:\\synthetic\\synthetic-hydraulic-inspection-guide.pdf"
    page_1_heading_source = _source(
        document_path=source_path,
        page_number=1,
        bbox=BoundingBox(x0=72.0, y0=96.0, x1=420.0, y1=116.0),
    )
    page_1_paragraph_source = _source(
        document_path=source_path,
        page_number=1,
        bbox=BoundingBox(x0=72.0, y0=144.0, x1=486.5, y1=190.25),
    )
    page_2_zero_bbox_source = _source(
        document_path=source_path,
        page_number=2,
        bbox=BoundingBox(x0=0.0, y0=0.0, x1=0.0, y1=0.0),
    )

    text_block = TextBlock(
        id="page-1-text-1",
        text="1. Synthetic Hydraulic Inspection Guide",
        source=page_1_heading_source,
        normalized_text="1. Synthetic Hydraulic Inspection Guide",
    )
    heading = HeadingBlock(
        id="page-1-heading-1",
        source=page_1_heading_source,
        text="1. Synthetic Hydraulic Inspection Guide",
        normalized_text="1. Synthetic Hydraulic Inspection Guide",
        level=1,
    )
    paragraph = ParagraphBlock(
        id="page-1-paragraph-1",
        text="Inspect the synthetic pump housing.\nRecord findings.",
        normalized_text="Inspect the synthetic pump housing. Record findings.",
        source=page_1_paragraph_source,
        source_text_block_ids=["page-1-text-2"],
    )
    second_page_paragraph = ParagraphBlock(
        id="page-2-paragraph-1",
        text="Zero-origin synthetic measurement block.",
        normalized_text="Zero-origin synthetic measurement block.",
        source=page_2_zero_bbox_source,
        source_text_block_ids=["page-2-text-1"],
    )
    unknown_block = Block(
        id="",
        source=_source(document_path=source_path, page_number=2, bbox=None),
        block_type="custom",
        text="Unclassified synthetic parser block.",
    )

    return Document(
        id="parser-derived-id",
        source_path=source_path,
        metadata=DocumentMetadata(title="Synthetic Metadata Title"),
        pages=[
            Page(
                page_number=1,
                width=612.0,
                height=792.0,
                has_native_text=True,
                blocks=[text_block, heading, paragraph],
                text_blocks=[text_block],
            ),
            Page(
                page_number=2,
                width=612.0,
                height=792.0,
                has_native_text=True,
                blocks=[second_page_paragraph, unknown_block],
            ),
        ],
    )


def _source(
    *,
    page_number: int,
    document_path: str = "synthetic.pdf",
    bbox: BoundingBox | None = None,
) -> SourceLocation:
    return SourceLocation(
        document_path=document_path,
        page_number=page_number,
        bbox=bbox,
        extraction_method="pymupdf",
        confidence=1.0,
    )
