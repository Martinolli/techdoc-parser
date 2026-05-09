"""Tests for JSON document export."""

import json
from pathlib import Path

from techdoc_parser.core import (
    Document,
    DocumentMetadata,
    Page,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
    TextBlock,
)
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


def test_export_document_json_includes_paragraph_blocks_only_in_blocks(
    tmp_path: Path,
) -> None:
    """ParagraphBlock objects should serialize under page.blocks only."""
    source = SourceLocation(document_path="manual.pdf", page_number=1)
    text_block = TextBlock(id="text-1", text="Example text.", source=source)
    paragraph = ParagraphBlock(
        id="paragraph-1",
        text="Example text.",
        source=source,
        source_text_block_ids=["text-1"],
    )
    document = Document(
        id="doc-1",
        source_path="manual.pdf",
        metadata=DocumentMetadata(title="Manual"),
        pages=[
            Page(
                page_number=1,
                blocks=[text_block, paragraph],
                text_blocks=[text_block],
            )
        ],
    )
    output_path = tmp_path / "manual.json"

    export_document_json(document, str(output_path))

    data = json.loads(output_path.read_text(encoding="utf-8"))
    page = data["pages"][0]

    assert any(block["block_type"] == "paragraph" for block in page["blocks"])
    assert all(block["block_type"] == "text" for block in page["text_blocks"])


def test_export_document_json_includes_table_candidate_metadata(
    tmp_path: Path,
) -> None:
    """TableBlock JSON should include candidate metadata."""
    source = SourceLocation(document_path="manual.pdf", page_number=1)
    table = TableBlock(
        id="table-1",
        source=source,
        text="Category    Description\nHigh        Severe impact",
        normalized_text="Category Description\nHigh Severe impact",
        rows=[["Category Description"], ["High Severe impact"]],
        source_text_block_ids=["text-1"],
        is_candidate=True,
    )
    document = Document(
        id="doc-1",
        source_path="manual.pdf",
        metadata=DocumentMetadata(title="Manual"),
        pages=[Page(page_number=1, blocks=[table])],
    )
    output_path = tmp_path / "manual.json"

    export_document_json(document, str(output_path))

    data = json.loads(output_path.read_text(encoding="utf-8"))
    table_data = data["pages"][0]["blocks"][0]

    assert table_data["block_type"] == "table"
    assert table_data["is_candidate"] is True
    assert table_data["source_text_block_ids"] == ["text-1"]
