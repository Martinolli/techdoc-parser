"""Tests for the isolated structured-document contract foundation."""

import importlib
import json
from pathlib import Path

import pytest

import techdoc_parser.contracts.structured_document as structured_contract
from techdoc_parser.contracts import (
    STRUCTURED_DOCUMENT_SCHEMA_NAME,
    STRUCTURED_DOCUMENT_SCHEMA_VERSION,
    StructuredBoundingBox,
    StructuredDocumentBlock,
    StructuredDocumentMetadata,
    StructuredDocumentPage,
    StructuredSourceSpan,
    build_structured_document,
    is_supported_structured_document_version,
    require_supported_structured_document_version,
    structured_document_to_dict,
    structured_document_to_json,
)
from techdoc_parser.core import Document, DocumentMetadata, Page
from techdoc_parser.exporters import document_to_json_dict
from techdoc_parser.exporters.manifest import create_output_manifest

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "structured_document"
    / "minimal_structured_document.json"
)


def test_contract_identity_constants_are_target_values() -> None:
    assert STRUCTURED_DOCUMENT_SCHEMA_NAME == "techdoc-structured-document"
    assert STRUCTURED_DOCUMENT_SCHEMA_VERSION == "0.1.0"
    assert is_supported_structured_document_version("0.1.0")


def test_unsupported_schema_version_is_rejected() -> None:
    assert not is_supported_structured_document_version("9.9.9")
    with pytest.raises(ValueError, match="Unsupported"):
        require_supported_structured_document_version("9.9.9")
    with pytest.raises(ValueError, match="Unsupported"):
        build_structured_document(
            document=_metadata(),
            pages=_pages(),
            schema_version="9.9.9",
        )


def test_minimum_structured_document_serializes_to_target_shape() -> None:
    data = structured_document_to_dict(_minimum_document())

    assert list(data) == [
        "schema_name",
        "schema_version",
        "parser_name",
        "parser_version",
        "document",
        "pages",
        "sections",
        "blocks",
        "tables",
        "figures",
        "equations",
        "admonitions",
        "cross_references",
    ]
    assert data["schema_name"] == "techdoc-structured-document"
    assert data["schema_version"] == "0.1.0"
    assert data["parser_name"] == "techdoc-parser"
    assert data["parser_version"] == "0.1.0"


def test_document_metadata_does_not_fabricate_unknown_values() -> None:
    metadata = structured_document_to_dict(_minimum_document())["document"]

    assert isinstance(metadata, dict)
    assert metadata["document_id"] == "synthetic-hydraulic-guide"
    assert metadata["source_filename"] == "synthetic-hydraulic-inspection-guide.pdf"
    assert "source_hash" not in metadata
    assert "revision" not in metadata
    assert "issue" not in metadata
    assert "effective_date" not in metadata


def test_source_filename_is_not_used_as_title() -> None:
    document = build_structured_document(
        document=StructuredDocumentMetadata(
            document_id="synthetic-no-title",
            source_filename="synthetic-no-title.pdf",
            page_count=1,
        ),
        pages=[
            StructuredDocumentPage(
                page_id="page-0001",
                pdf_page_index=0,
                page_number=1,
            )
        ],
    )

    metadata = structured_document_to_dict(document)["document"]

    assert isinstance(metadata, dict)
    assert metadata["source_filename"] == "synthetic-no-title.pdf"
    assert "document_title" not in metadata
    assert "canonical_title" not in metadata


def test_page_indices_and_printed_labels_preserve_known_values_only() -> None:
    pages = structured_document_to_dict(_minimum_document())["pages"]

    assert isinstance(pages, list)
    assert pages[0] == {
        "page_id": "page-0001",
        "pdf_page_index": 0,
        "page_number": 1,
        "printed_page_label": None,
    }
    assert pages[1]["pdf_page_index"] == 1
    assert pages[1]["page_number"] == 2
    assert pages[1]["printed_page_label"] is None


def test_empty_sections_are_accepted() -> None:
    data = structured_document_to_dict(_minimum_document())

    assert data["sections"] == []


def test_unsupported_entity_collections_are_initialized_as_empty_lists() -> None:
    data = structured_document_to_dict(_minimum_document())

    assert data["tables"] == []
    assert data["figures"] == []
    assert data["equations"] == []
    assert data["admonitions"] == []
    assert data["cross_references"] == []


def test_block_order_and_indexes_are_caller_controlled_and_deterministic() -> None:
    document = _minimum_document()
    data = structured_document_to_dict(document)
    first_json = structured_document_to_json(document)
    second_json = structured_document_to_json(document)

    assert first_json == second_json
    assert [block["block_id"] for block in data["blocks"]] == [
        "blk-0001",
        "blk-0002",
    ]
    assert [block["document_block_index"] for block in data["blocks"]] == [0, 1]


def test_source_spans_preserve_page_ranges_and_bbox_without_confidence() -> None:
    blocks = structured_document_to_dict(_minimum_document())["blocks"]

    assert isinstance(blocks, list)
    assert blocks[0]["source_span"] == {
        "page_start": 1,
        "page_end": 1,
        "pdf_page_index_start": 0,
        "pdf_page_index_end": 0,
    }
    assert blocks[1]["source_span"] == {
        "page_start": 2,
        "page_end": 2,
        "pdf_page_index_start": 1,
        "pdf_page_index_end": 1,
        "bbox": {
            "x0": 72.0,
            "y0": 144.0,
            "x1": 420.0,
            "y1": 166.0,
        },
    }
    assert "confidence" not in blocks[0]
    assert "confidence" not in blocks[0]["source_span"]
    assert "extraction_confidence" not in blocks[0]


def test_unicode_text_is_preserved_in_json() -> None:
    document = build_structured_document(
        document=_metadata(),
        pages=_pages(),
        blocks=[
            StructuredDocumentBlock(
                block_id="blk-unicode",
                block_type="paragraph",
                text="Cafe hydraulic Δ check",
                source_span=StructuredSourceSpan(
                    page_start=1,
                    page_end=1,
                    pdf_page_index_start=0,
                    pdf_page_index_end=0,
                ),
            )
        ],
    )

    output = structured_document_to_json(document)

    assert "Cafe hydraulic Δ check" in output
    assert "\\u0394" not in output


def test_serialization_does_not_include_absolute_paths_or_timestamps() -> None:
    output = structured_document_to_json(_minimum_document())
    data = json.loads(output)

    assert "C:\\" not in output
    assert "/Users/" not in output
    assert "created_at" not in output
    assert "updated_at" not in output
    assert "export_timestamp" not in output
    assert "timestamp" not in output
    assert "effective_date" not in data["document"]


def test_builder_copies_input_collections_without_mutating_them() -> None:
    pages = list(_pages())
    blocks = list(_blocks())
    tables = [{"table_id": "tbl-1", "page_start": 1}]
    document = build_structured_document(
        document=_metadata(),
        pages=pages,
        blocks=blocks,
        tables=tables,
    )

    pages.append(
        StructuredDocumentPage(
            page_id="page-9999",
            pdf_page_index=9998,
            page_number=9999,
        )
    )
    blocks.clear()
    tables[0]["table_id"] = "changed"
    data = structured_document_to_dict(document)

    assert len(data["pages"]) == 2
    assert len(data["blocks"]) == 2
    assert data["tables"] == [{"table_id": "tbl-1", "page_start": 1}]


def test_contract_import_and_serialization_do_not_write_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())

    importlib.reload(structured_contract)
    structured_contract.structured_document_to_json(_minimum_document())

    assert set(tmp_path.iterdir()) == before


def test_minimal_fixture_matches_contract_output() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    generated = structured_document_to_dict(_minimum_document())

    assert fixture == generated


def test_minimal_fixture_is_valid_json_object() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert isinstance(fixture, dict)
    assert fixture["schema_name"] == "techdoc-structured-document"
    assert fixture["schema_version"] == "0.1.0"


def test_existing_document_json_shape_remains_unchanged() -> None:
    document = Document(
        id="doc-1",
        source_path="manual.pdf",
        metadata=DocumentMetadata(title="Manual"),
        pages=[Page(page_number=1)],
    )

    data = document_to_json_dict(document)

    assert data["schema_version"] == "0.1.0"
    assert data["parser"] == {"name": "techdoc-parser", "version": "0.1.0"}
    assert data["id"] == "doc-1"
    assert data["source_path"] == "manual.pdf"
    assert "schema_name" not in data
    assert "document" not in data
    assert "blocks" not in data


def test_existing_manifest_shape_remains_unchanged() -> None:
    document = Document(
        id="manual",
        source_path="input/manual.pdf",
        metadata=DocumentMetadata(title="Manual"),
        pages=[Page(page_number=1)],
    )

    manifest = create_output_manifest(document=document)

    assert manifest["schema_version"] == "0.1.0"
    assert manifest["parser"] == {"name": "techdoc-parser", "version": "0.1.0"}
    assert manifest["source"] == {
        "path": "input/manual.pdf",
        "document_id": "manual",
    }
    assert "schema_name" not in manifest
    assert "structured_document" not in manifest


def test_invalid_values_are_rejected_without_repair() -> None:
    with pytest.raises(ValueError, match="source_hash"):
        StructuredDocumentMetadata(
            document_id="doc",
            source_filename="doc.pdf",
            source_hash="",
        )
    with pytest.raises(ValueError, match="page_start"):
        StructuredSourceSpan(page_start=2, page_end=1)
    with pytest.raises(ValueError, match="pdf_page_index"):
        StructuredDocumentPage(
            page_id="page",
            pdf_page_index=-1,
            page_number=1,
        )
    with pytest.raises(ValueError, match="text"):
        StructuredDocumentBlock(
            block_id="blk",
            block_type="paragraph",
            text="",
            source_span=StructuredSourceSpan(page_start=1),
        )


def _minimum_document() -> structured_contract.StructuredDocument:
    return build_structured_document(
        document=_metadata(),
        pages=_pages(),
        sections=[],
        blocks=_blocks(),
    )


def _metadata() -> StructuredDocumentMetadata:
    return StructuredDocumentMetadata(
        document_id="synthetic-hydraulic-guide",
        source_filename="synthetic-hydraulic-inspection-guide.pdf",
        document_title="Synthetic Hydraulic Inspection Guide",
        page_count=2,
    )


def _pages() -> list[StructuredDocumentPage]:
    return [
        StructuredDocumentPage(
            page_id="page-0001",
            pdf_page_index=0,
            page_number=1,
        ),
        StructuredDocumentPage(
            page_id="page-0002",
            pdf_page_index=1,
            page_number=2,
        ),
    ]


def _blocks() -> list[StructuredDocumentBlock]:
    return [
        StructuredDocumentBlock(
            block_id="blk-0001",
            block_type="paragraph",
            text="Synthetic hydraulic inspection overview.\n"
            "Keep pump access panels clean.",
            document_block_index=0,
            page_block_index=0,
            page_id="page-0001",
            page_number=1,
            pdf_page_index=0,
            source_span=StructuredSourceSpan(
                page_start=1,
                page_end=1,
                pdf_page_index_start=0,
                pdf_page_index_end=0,
            ),
        ),
        StructuredDocumentBlock(
            block_id="blk-0002",
            block_type="paragraph",
            text="Synthetic pressure check instructions only.",
            document_block_index=1,
            page_block_index=0,
            page_id="page-0002",
            page_number=2,
            pdf_page_index=1,
            source_span=StructuredSourceSpan(
                page_start=2,
                page_end=2,
                pdf_page_index_start=1,
                pdf_page_index_end=1,
                bbox=StructuredBoundingBox(
                    x0=72.0,
                    y0=144.0,
                    x1=420.0,
                    y1=166.0,
                ),
            ),
        ),
    ]
