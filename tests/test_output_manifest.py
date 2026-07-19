"""Tests for output manifest export."""

import json
from pathlib import Path

from techdoc_parser.core import Chunk, Document, DocumentMetadata, Page
from techdoc_parser.exporters import (
    create_output_manifest,
    export_output_manifest_json,
    output_manifest_to_json,
)
from techdoc_parser.validation import (
    ValidationDecision,
    ValidationIssue,
    ValidationReport,
)


def _document() -> Document:
    return Document(
        id="manual",
        source_path="input/manual.pdf",
        metadata=DocumentMetadata(title="Manual"),
        pages=[Page(page_number=1), Page(page_number=2)],
    )


def _chunk(id: str) -> Chunk:
    return Chunk(
        id=id,
        document_id="manual",
        text="Chunk text.",
        source_page_numbers=[1],
        source_block_ids=[f"{id}-block"],
        source_text_block_ids=[f"{id}-text"],
    )


def _report() -> ValidationReport:
    return ValidationReport(
        document_id="manual",
        source_path="input/manual.pdf",
        issues=[
            ValidationIssue("document.empty", "error", "Document is empty."),
            ValidationIssue("page.requires_ocr", "warning", "Page requires OCR."),
            ValidationIssue("page.furniture_only", "info", "Furniture-only page."),
        ],
        summary={
            "page_count": 2,
            "chunk_count": 3,
            "pages_requiring_ocr": 1,
            "pages_furniture_only": 1,
        },
    )


def _decision() -> ValidationDecision:
    return ValidationDecision(
        status="review",
        can_ingest=False,
        reason="Validation warnings require review before automated ingestion.",
        issue_count=1,
        error_count=0,
        warning_count=1,
        info_count=0,
    )


def test_create_output_manifest_includes_metadata_source_and_page_count() -> None:
    """Basic manifest should include export metadata, source, and page metrics."""
    manifest = create_output_manifest(document=_document())

    source = manifest["source"]
    metrics = manifest["metrics"]

    assert manifest["schema_version"] == "0.1.0"
    assert manifest["parser"] == {"name": "techdoc-parser", "version": "0.1.0"}
    assert isinstance(source, dict)
    assert source["path"] == "input/manual.pdf"
    assert source["document_id"] == "manual"
    assert isinstance(metrics, dict)
    assert metrics["page_count"] == 2


def test_create_output_manifest_includes_only_provided_output_paths() -> None:
    """Manifest outputs should include stable keys only for provided paths."""
    manifest = create_output_manifest(
        document=_document(),
        document_json_path=Path("output/document.json"),
        chunks_json_path="output/chunks.json",
        validation_json_path=Path("output/validation.json"),
        gate_json_path="output/gate.json",
        validation_summary_markdown_path=Path("output/validation_summary.md"),
    )

    outputs = manifest["outputs"]

    assert outputs == {
        "document_json": str(Path("output/document.json")),
        "chunks_json": "output/chunks.json",
        "validation_json": str(Path("output/validation.json")),
        "gate_json": "output/gate.json",
        "validation_summary_markdown": str(Path("output/validation_summary.md")),
    }


def test_create_output_manifest_omits_missing_output_paths() -> None:
    """Manifest outputs should not include keys for paths that were not provided."""
    manifest = create_output_manifest(
        document=_document(),
        document_json_path="output/document.json",
    )

    assert manifest["outputs"] == {"document_json": "output/document.json"}


def test_create_output_manifest_includes_chunk_metrics() -> None:
    """Manifest metrics should include chunk count when chunks are provided."""
    manifest = create_output_manifest(
        document=_document(),
        chunks=[_chunk("chunk-1"), _chunk("chunk-2")],
    )

    metrics = manifest["metrics"]

    assert isinstance(metrics, dict)
    assert metrics["chunk_count"] == 2


def test_create_output_manifest_includes_validation_report_metrics() -> None:
    """Manifest metrics should include validation counts and selected summary data."""
    manifest = create_output_manifest(
        document=_document(),
        validation_report=_report(),
    )

    metrics = manifest["metrics"]

    assert isinstance(metrics, dict)
    assert metrics["chunk_count"] == 3
    assert metrics["issue_count"] == 3
    assert metrics["error_count"] == 1
    assert metrics["warning_count"] == 1
    assert metrics["info_count"] == 1
    assert metrics["pages_requiring_ocr"] == 1
    assert metrics["pages_furniture_only"] == 1
    assert metrics["has_errors"] is True
    assert metrics["has_warnings"] is True


def test_create_output_manifest_includes_decision() -> None:
    """Manifest should include compact validation decision data when provided."""
    manifest = create_output_manifest(
        document=_document(),
        validation_decision=_decision(),
    )

    assert manifest["decision"] == {
        "status": "review",
        "can_ingest": False,
        "reason": "Validation warnings require review before automated ingestion.",
    }


def test_output_manifest_to_json_returns_valid_json() -> None:
    """Manifest JSON helper should serialize manifest data."""
    manifest = create_output_manifest(
        document=_document(),
        document_json_path="output/document.json",
    )

    data = json.loads(output_manifest_to_json(manifest))

    assert data["schema_version"] == "0.1.0"
    assert data["outputs"] == {"document_json": "output/document.json"}


def test_export_output_manifest_json_writes_file(tmp_path: Path) -> None:
    """Manifest exporter should write JSON to disk."""
    output_path = tmp_path / "nested" / "manifest.json"
    manifest = create_output_manifest(
        document=_document(),
        validation_report=_report(),
        validation_decision=_decision(),
    )

    export_output_manifest_json(manifest, output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["source"]["document_id"] == "manual"
    assert data["decision"]["status"] == "review"
    assert data["metrics"]["issue_count"] == 3
