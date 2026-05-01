"""Public parsing entry points."""

from pathlib import Path

from techdoc_parser.core import Document
from techdoc_parser.ingestion import PDFLoader


def parse_document(path: str) -> Document:
    """Parse a technical document.

    Args:
        path: Path to the document to parse.

    Raises:
        ValueError: The document file type is not supported.
    """
    document_path = Path(path)
    if document_path.suffix.lower() == ".pdf":
        return PDFLoader(path).load()

    raise ValueError(f"Unsupported file type: {document_path.suffix or '<none>'}")
