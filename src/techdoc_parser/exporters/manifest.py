"""Output manifest export helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from techdoc_parser.core import Chunk, Document
from techdoc_parser.validation import ValidationDecision, ValidationReport
from techdoc_parser.version import get_export_metadata


def create_output_manifest(
    *,
    document: Document,
    chunks: list[Chunk] | None = None,
    validation_report: ValidationReport | None = None,
    validation_decision: ValidationDecision | None = None,
    document_json_path: str | Path | None = None,
    chunks_json_path: str | Path | None = None,
    validation_json_path: str | Path | None = None,
    gate_json_path: str | Path | None = None,
    validation_summary_markdown_path: str | Path | None = None,
    structured_document_artifact: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Create a JSON-serializable manifest for an exported output package."""
    manifest: dict[str, object] = {
        **get_export_metadata(),
        "source": {
            "path": document.source_path,
            "document_id": document.id,
        },
        "metrics": _metrics(document, chunks, validation_report),
    }

    outputs = _outputs(
        document_json_path=document_json_path,
        chunks_json_path=chunks_json_path,
        validation_json_path=validation_json_path,
        gate_json_path=gate_json_path,
        validation_summary_markdown_path=validation_summary_markdown_path,
        structured_document_artifact=structured_document_artifact,
    )
    if outputs:
        manifest["outputs"] = outputs
    if structured_document_artifact is not None:
        manifest["artifacts"] = [dict(structured_document_artifact)]

    if validation_decision is not None:
        manifest["decision"] = {
            "status": validation_decision.status,
            "can_ingest": validation_decision.can_ingest,
            "reason": validation_decision.reason,
        }

    return manifest


def output_manifest_to_json(manifest: dict[str, object], indent: int = 2) -> str:
    """Return an output manifest as a JSON string."""
    return json.dumps(manifest, indent=indent)


def export_output_manifest_json(
    manifest: dict[str, object],
    output_path: str | Path,
    indent: int = 2,
) -> None:
    """Write an output manifest JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(output_manifest_to_json(manifest, indent=indent), encoding="utf-8")


def _outputs(
    *,
    document_json_path: str | Path | None,
    chunks_json_path: str | Path | None,
    validation_json_path: str | Path | None,
    gate_json_path: str | Path | None,
    validation_summary_markdown_path: str | Path | None,
    structured_document_artifact: Mapping[str, object] | None,
) -> dict[str, str]:
    outputs: dict[str, str] = {}
    _add_output(outputs, "document_json", document_json_path)
    _add_output(outputs, "chunks_json", chunks_json_path)
    _add_output(outputs, "validation_json", validation_json_path)
    _add_output(outputs, "gate_json", gate_json_path)
    _add_output(
        outputs,
        "validation_summary_markdown",
        validation_summary_markdown_path,
    )
    if structured_document_artifact is not None:
        path = structured_document_artifact.get("path")
        if path is not None:
            outputs["structured_document"] = str(path)
    return outputs


def _add_output(
    outputs: dict[str, str],
    key: str,
    path: str | Path | None,
) -> None:
    if path is not None:
        outputs[key] = str(path)


def _metrics(
    document: Document,
    chunks: list[Chunk] | None,
    validation_report: ValidationReport | None,
) -> dict[str, object]:
    metrics: dict[str, object] = {
        "page_count": len(document.pages),
    }

    if chunks is not None:
        metrics["chunk_count"] = len(chunks)
    elif validation_report is not None and "chunk_count" in validation_report.summary:
        metrics["chunk_count"] = validation_report.summary["chunk_count"]

    if validation_report is not None:
        metrics["issue_count"] = validation_report.issue_count
        metrics["error_count"] = validation_report.error_count
        metrics["warning_count"] = validation_report.warning_count
        metrics["info_count"] = validation_report.info_count
        for key in (
            "pages_requiring_ocr",
            "pages_furniture_only",
            "has_errors",
            "has_warnings",
        ):
            if key in validation_report.summary:
                metrics[key] = validation_report.summary[key]

    return metrics


__all__ = [
    "create_output_manifest",
    "export_output_manifest_json",
    "output_manifest_to_json",
]
