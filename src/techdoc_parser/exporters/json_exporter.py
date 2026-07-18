"""JSON export helpers for parsed documents."""

import json
from pathlib import Path

from techdoc_parser.chunking import create_semantic_chunks
from techdoc_parser.core import Chunk, Document
from techdoc_parser.validation import ValidationReport


def export_document_json(
    document: Document,
    output_path: str,
    indent: int = 2,
) -> None:
    """Write a document as JSON to an output path.

    Parent directories are created automatically. The output path is not required
    to use a `.json` extension.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document.to_json(indent=indent), encoding="utf-8")


def chunks_to_json_dict(chunks: list[Chunk]) -> dict[str, object]:
    """Return a JSON-serializable dictionary for chunks."""
    return {
        "chunk_count": len(chunks),
        "chunks": [chunk.to_dict() for chunk in chunks],
    }


def chunks_to_json(chunks: list[Chunk], indent: int = 2) -> str:
    """Return chunks as a JSON string."""
    return json.dumps(chunks_to_json_dict(chunks), indent=indent)


def export_chunks_json(
    chunks: list[Chunk],
    output_path: str | Path,
    indent: int = 2,
) -> None:
    """Write chunks as JSON to an output path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(chunks_to_json(chunks, indent=indent), encoding="utf-8")


def export_document_chunks_json(
    document: Document,
    output_path: str | Path,
    max_chars: int = 1200,
    indent: int = 2,
) -> None:
    """Create semantic chunks for a document and write them as JSON."""
    chunks = create_semantic_chunks(document, max_chars=max_chars)
    export_chunks_json(chunks, output_path, indent=indent)


def validation_report_to_json(
    report: ValidationReport,
    indent: int = 2,
) -> str:
    """Return a validation report as a JSON string."""
    return json.dumps(report.to_dict(), indent=indent)


def export_validation_report_json(
    report: ValidationReport,
    output_path: str | Path,
    indent: int = 2,
) -> None:
    """Write a validation report as JSON to an output path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(validation_report_to_json(report, indent=indent), encoding="utf-8")
