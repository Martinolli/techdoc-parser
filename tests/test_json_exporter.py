"""Tests for JSON document export."""

import json
from pathlib import Path

from techdoc_parser.core import Document, DocumentMetadata, Page
from techdoc_parser.exporters import export_document_json


def test_export_document_json_writes_valid_json(tmp_path: Path) -> None:
    """JSON exporter should write a serialized document."""
    document = Document(
        id="doc-1",
        source_path="manual.pdf",
        metadata=DocumentMetadata(title="Manual"),
        pages=[Page(page_number=1, width=200.0, height=100.0)],
    )
    output_path = tmp_path / "nested" / "manual-output"

    export_document_json(document, str(output_path), indent=4)

    assert output_path.parent.is_dir()
    assert output_path.exists()

    content = output_path.read_text(encoding="utf-8")
    data = json.loads(content)

    assert content.startswith('{\n    "id"')
    assert data["id"] == "doc-1"
    assert data["source_path"] == "manual.pdf"
    assert data["metadata"]["title"] == "Manual"
    assert len(data["pages"]) == 1
