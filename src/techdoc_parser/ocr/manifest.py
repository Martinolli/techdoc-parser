"""Manifest support for controlled OCR artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping

from techdoc_parser.ocr.artifact import artifact_bytes_sha256
from techdoc_parser.ocr.models import (
    OCR_ARTIFACT_SCHEMA_NAME,
    OCR_ARTIFACT_SCHEMA_VERSION,
    OCR_MANIFEST_SCHEMA_NAME,
    OCR_MANIFEST_SCHEMA_VERSION,
    SUPPORTED_OCR_MANIFEST_SCHEMA_VERSIONS,
    ControlledOcrDocumentResult,
    OcrManifestValidationResult,
)


def create_controlled_ocr_manifest(
    result: ControlledOcrDocumentResult,
    *,
    artifact_path: str = "ocr_document.json",
    artifact_bytes: bytes,
) -> dict[str, object]:
    """Create deterministic OCR manifest data for a written document artifact."""
    return {
        "schema_name": OCR_MANIFEST_SCHEMA_NAME,
        "schema_version": OCR_MANIFEST_SCHEMA_VERSION,
        "adapter": {
            "name": result.adapter_name,
            "version": result.adapter_version,
        },
        "source": {
            "filename": result.source_filename,
            "sha256": result.source_sha256,
            "size_bytes": result.source_size_bytes,
            "observed_page_count": result.observed_page_count,
        },
        "engine": {
            "name": "tesseract",
            "version": result.engine_version,
            "requested_languages": list(result.request.languages),
            "available_languages": list(result.available_languages),
        },
        "configuration": {
            "document_id": result.request.document_id,
            "mode": result.request.mode,
            "selected_pages": (
                list(result.request.selected_pages)
                if result.request.selected_pages is not None
                else None
            ),
            "dpi": result.request.dpi,
            "psm": result.request.psm,
            "oem": result.request.oem,
            "timeout_seconds": result.request.timeout_seconds,
            "strict": result.request.strict,
        },
        "artifact": {
            "schema_name": OCR_ARTIFACT_SCHEMA_NAME,
            "schema_version": OCR_ARTIFACT_SCHEMA_VERSION,
            "path": artifact_path,
            "sha256": artifact_bytes_sha256(artifact_bytes),
            "content_type": "application/json",
        },
        "pages": {
            "requested": list(result.requested_pages),
            "processed": list(result.processed_pages),
            "skipped": list(result.skipped_pages),
            "failed": list(result.failed_pages),
        },
        "outcome": result.outcome,
        "warnings": list(result.warnings),
        "errors": list(result.errors),
        "limitations": list(result.limitations),
        "safety": {
            "default_parser_behavior_changed": result.default_parser_behavior_changed,
            "structured_document_schema_changed": (
                result.structured_document_schema_changed
            ),
            "aviationrag_activity": result.aviationrag_activity,
            "embeddings_or_vector_store_activity": (
                result.embeddings_or_vector_store_activity
            ),
        },
    }


def controlled_ocr_manifest_to_json(manifest: Mapping[str, object]) -> str:
    """Return deterministic manifest JSON text with a final newline."""
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def validate_ocr_manifest(data: Mapping[str, object]) -> OcrManifestValidationResult:
    """Validate the controlled OCR manifest contract."""
    errors: list[str] = []
    if data.get("schema_name") != OCR_MANIFEST_SCHEMA_NAME:
        errors.append("OCR_MANIFEST_SCHEMA_NAME_INVALID")
    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str) or (
        schema_version not in SUPPORTED_OCR_MANIFEST_SCHEMA_VERSIONS
    ):
        errors.append("OCR_MANIFEST_SCHEMA_VERSION_UNSUPPORTED")
    artifact = data.get("artifact")
    if not isinstance(artifact, Mapping):
        errors.append("OCR_MANIFEST_ARTIFACT_MISSING")
    else:
        if artifact.get("schema_name") != OCR_ARTIFACT_SCHEMA_NAME:
            errors.append("OCR_MANIFEST_ARTIFACT_SCHEMA_NAME_INVALID")
        if not isinstance(artifact.get("sha256"), str):
            errors.append("OCR_MANIFEST_ARTIFACT_SHA256_MISSING")
    if "engine" not in data:
        errors.append("OCR_MANIFEST_ENGINE_MISSING")
    if "pages" not in data:
        errors.append("OCR_MANIFEST_PAGES_MISSING")
    return OcrManifestValidationResult(valid=not errors, errors=tuple(sorted(errors)))


__all__ = [
    "controlled_ocr_manifest_to_json",
    "create_controlled_ocr_manifest",
    "validate_ocr_manifest",
]
