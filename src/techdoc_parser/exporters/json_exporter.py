"""JSON export helpers for parsed documents."""

from pathlib import Path

from techdoc_parser.core import Document


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
