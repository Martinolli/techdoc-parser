"""Structured-document artifact export helpers."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from techdoc_parser.contracts import (
    STRUCTURED_DOCUMENT_SCHEMA_NAME,
    STRUCTURED_DOCUMENT_SCHEMA_VERSION,
    StructuredDocument,
    build_structured_document_artifact,
)
from techdoc_parser.core import Document


@dataclass(frozen=True)
class StructuredDocumentArtifact:
    """Metadata returned after writing one structured-document artifact."""

    output_path: Path
    schema_name: str
    schema_version: str
    source_sha256: str
    artifact_sha256: str
    document_id: str

    def to_manifest_entry(self) -> dict[str, object]:
        """Return the additive manifest record for this artifact."""
        return {
            "artifact_type": "structured_document",
            "path": str(self.output_path),
            "media_type": "application/json",
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "source_sha256": self.source_sha256,
            "artifact_sha256": self.artifact_sha256,
            "document_id": self.document_id,
        }


def compute_source_sha256(path: str | Path) -> str:
    """Return the lowercase SHA-256 digest of the exact source file bytes."""
    return _compute_file_sha256(Path(path))


def write_structured_document(
    document: StructuredDocument,
    output_path: str | Path,
    *,
    overwrite: bool = False,
    indent: int | None = 2,
) -> Path:
    """Write a structured-document JSON artifact atomically.

    The writer serializes the complete JSON payload before touching the
    destination, writes UTF-8 JSON with a final newline to a sibling temporary
    file, then atomically replaces the destination. Existing destinations are
    rejected unless ``overwrite`` is explicit.
    """
    path = Path(output_path)
    _validate_output_path(path, overwrite=overwrite)

    payload = document.to_json(indent=indent) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _temporary_sibling_path(path)

    try:
        if temp_path.exists():
            temp_path.unlink()
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and not overwrite:
            raise FileExistsError(f"Structured-document output already exists: {path}")
        os.replace(temp_path, path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    return path


def export_structured_document(
    parsed_document: Document,
    *,
    source_path: str | Path,
    output_path: str | Path,
    document_id: str,
    document_title: str | None = None,
    document_number: str | None = None,
    revision: str | None = None,
    issue: str | None = None,
    effective_date: str | None = None,
    overwrite: bool = False,
    indent: int | None = 2,
) -> StructuredDocumentArtifact:
    """Build, write, and describe one structured-document artifact."""
    source = Path(source_path)
    output = Path(output_path)
    _validate_distinct_paths(source, output)
    source_sha256 = compute_source_sha256(source)
    structured_document = build_structured_document_artifact(
        parsed_document,
        document_id=document_id,
        document_title=document_title,
        document_number=document_number,
        revision=revision,
        issue=issue,
        effective_date=effective_date,
        source_checksum=source_sha256,
    )
    written_path = write_structured_document(
        structured_document,
        output,
        overwrite=overwrite,
        indent=indent,
    )
    return StructuredDocumentArtifact(
        output_path=written_path,
        schema_name=STRUCTURED_DOCUMENT_SCHEMA_NAME,
        schema_version=STRUCTURED_DOCUMENT_SCHEMA_VERSION,
        source_sha256=source_sha256,
        artifact_sha256=_compute_file_sha256(written_path),
        document_id=document_id,
    )


def _compute_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_output_path(path: Path, *, overwrite: bool) -> None:
    if path.exists() and path.is_dir():
        raise IsADirectoryError(f"Structured-document output is a directory: {path}")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Structured-document output already exists: {path}")


def _validate_distinct_paths(source_path: Path, output_path: Path) -> None:
    try:
        source_resolved = source_path.resolve(strict=False)
        output_resolved = output_path.resolve(strict=False)
    except OSError as exc:
        raise ValueError("Could not resolve structured-document paths.") from exc
    if source_resolved == output_resolved:
        raise ValueError(
            "Structured-document output path must not be the input source path."
        )


def _temporary_sibling_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.tmp")


__all__ = [
    "StructuredDocumentArtifact",
    "compute_source_sha256",
    "export_structured_document",
    "write_structured_document",
]
