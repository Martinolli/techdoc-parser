"""Serialization and validation for controlled OCR document artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path

from techdoc_parser.ocr.models import (
    OCR_ARTIFACT_SCHEMA_NAME,
    OCR_ARTIFACT_SCHEMA_VERSION,
    SUPPORTED_OCR_ARTIFACT_SCHEMA_VERSIONS,
    ControlledOcrDocumentResult,
    ControlledOcrPageResult,
    OcrArtifactValidationResult,
)


def controlled_ocr_result_to_artifact_dict(
    result: ControlledOcrDocumentResult,
) -> dict[str, object]:
    """Return deterministic JSON-compatible OCR document artifact data."""
    return {
        "schema_name": OCR_ARTIFACT_SCHEMA_NAME,
        "schema_version": OCR_ARTIFACT_SCHEMA_VERSION,
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
        "request": {
            "document_id": result.request.document_id,
            "mode": result.request.mode,
            "languages": list(result.request.languages),
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
            "preserve_rendered_pages": result.request.preserve_rendered_pages,
        },
        "engine": {
            "name": "tesseract",
            "version": result.engine_version,
            "available_languages": list(result.available_languages),
            "requested_languages": list(result.request.languages),
        },
        "outcome": result.outcome,
        "requested_pages": list(result.requested_pages),
        "processed_pages": list(result.processed_pages),
        "skipped_pages": list(result.skipped_pages),
        "failed_pages": list(result.failed_pages),
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
        "pages": [_page_result_to_dict(page) for page in result.page_results],
    }


def controlled_ocr_result_to_json(result: ControlledOcrDocumentResult) -> str:
    """Return deterministic UTF-8 JSON text with a final newline."""
    return (
        json.dumps(
            controlled_ocr_result_to_artifact_dict(result),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def validate_ocr_artifact(data: Mapping[str, object]) -> OcrArtifactValidationResult:
    """Validate the controlled OCR document artifact contract."""
    errors: list[str] = []
    warnings: list[str] = []
    if data.get("schema_name") != OCR_ARTIFACT_SCHEMA_NAME:
        errors.append("OCR_ARTIFACT_SCHEMA_NAME_INVALID")
    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str) or (
        schema_version not in SUPPORTED_OCR_ARTIFACT_SCHEMA_VERSIONS
    ):
        errors.append("OCR_ARTIFACT_SCHEMA_VERSION_UNSUPPORTED")
    pages = data.get("pages")
    if not isinstance(pages, Sequence) or isinstance(pages, str | bytes):
        errors.append("OCR_ARTIFACT_PAGES_MISSING")
    else:
        seen_pages: set[int] = set()
        for page in pages:
            if not isinstance(page, Mapping):
                errors.append("OCR_ARTIFACT_PAGE_INVALID")
                continue
            page_number = page.get("page_number")
            if not isinstance(page_number, int) or page_number < 1:
                errors.append("OCR_ARTIFACT_PAGE_NUMBER_INVALID")
            elif page_number in seen_pages:
                errors.append("OCR_ARTIFACT_PAGE_NUMBER_DUPLICATE")
            else:
                seen_pages.add(page_number)
            if not isinstance(page.get("raw_ocr_text"), str):
                errors.append("OCR_ARTIFACT_RAW_TEXT_MISSING")
            if not isinstance(page.get("normalized_ocr_text"), str):
                errors.append("OCR_ARTIFACT_NORMALIZED_TEXT_MISSING")
            if page.get("raw_ocr_text") == page.get("normalized_ocr_text"):
                warnings.append("OCR_ARTIFACT_RAW_NORMALIZED_TEXT_IDENTICAL")
            if "provenance" not in page:
                errors.append("OCR_ARTIFACT_PAGE_PROVENANCE_MISSING")
    return OcrArtifactValidationResult(
        valid=not errors,
        errors=tuple(sorted(set(errors))),
        warnings=tuple(sorted(set(warnings))),
    )


def load_ocr_document_artifact(path: str | Path) -> Mapping[str, object]:
    """Load and validate an OCR document artifact from disk."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("OCR document artifact JSON must be an object.")
    validation = validate_ocr_artifact(data)
    if not validation.valid:
        raise ValueError(f"Invalid OCR document artifact: {validation.errors}")
    return data


def ocr_artifact_to_page_texts(
    data: Mapping[str, object],
    *,
    text_key: str = "normalized_ocr_text",
) -> dict[int, str]:
    """Extract OCR page text for D.7a's supplied-artifact comparison path."""
    pages = data.get("pages")
    if not isinstance(pages, Sequence) or isinstance(pages, str | bytes):
        raise ValueError("OCR document artifact pages must be a sequence.")
    result: dict[int, str] = {}
    for page in pages:
        if not isinstance(page, Mapping):
            continue
        page_number = page.get("page_number")
        text = page.get(text_key)
        if isinstance(page_number, int) and isinstance(text, str):
            result[page_number] = text
    return result


def _page_result_to_dict(page: ControlledOcrPageResult) -> dict[str, object]:
    data = {
        "page_number": page.page_number,
        "pdf_page_index": page.pdf_page_index,
        "status": page.status,
        "raw_ocr_text": page.raw_ocr_text,
        "normalized_ocr_text": page.normalized_ocr_text,
        "text": page.normalized_ocr_text,
        "ocr_text": page.normalized_ocr_text,
        "warnings": list(page.warnings),
        "errors": list(page.errors),
        "stderr_excerpt": page.stderr_excerpt,
        "exit_code": page.exit_code,
        "provenance": asdict(page.provenance),
    }
    return data


def artifact_bytes_sha256(data: bytes) -> str:
    """Return SHA-256 for already serialized artifact bytes."""
    from hashlib import sha256

    return sha256(data).hexdigest()


__all__ = [
    "artifact_bytes_sha256",
    "controlled_ocr_result_to_artifact_dict",
    "controlled_ocr_result_to_json",
    "load_ocr_document_artifact",
    "ocr_artifact_to_page_texts",
    "validate_ocr_artifact",
]
