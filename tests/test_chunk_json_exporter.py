"""Tests for semantic chunk JSON export."""

import json
from pathlib import Path

from techdoc_parser.core import (
    BoundingBox,
    Chunk,
    Document,
    DocumentMetadata,
    Page,
    ParagraphBlock,
    SourceLocation,
)
from techdoc_parser.exporters import (
    chunks_to_json,
    chunks_to_json_dict,
    export_chunks_json,
    export_document_chunks_json,
)


def _chunk(id: str, text: str) -> Chunk:
    return Chunk(
        id=id,
        document_id="manual",
        text=text,
        source_page_numbers=[1],
        source_block_ids=[f"{id}-block"],
        source_text_block_ids=[f"{id}-text"],
        chunk_type="semantic",
        metadata={"chunk_index": id.rsplit("-", maxsplit=1)[-1]},
    )


def _document() -> Document:
    source = SourceLocation(
        document_path="manual.pdf",
        page_number=1,
        bbox=BoundingBox(x0=1.0, y0=2.0, x1=3.0, y1=4.0),
    )
    paragraph = ParagraphBlock(
        id="paragraph-1",
        source=source,
        text="Body paragraph.",
        normalized_text="Body paragraph.",
        source_text_block_ids=["text-1"],
    )
    return Document(
        id="manual",
        source_path="manual.pdf",
        metadata=DocumentMetadata(title="Manual"),
        pages=[Page(page_number=1, blocks=[paragraph])],
    )


def test_chunks_to_json_dict_serializes_chunks() -> None:
    """Chunk JSON dict should include count and serialized chunk values."""
    chunks = [_chunk("chunk-1", "First"), _chunk("chunk-2", "Second")]

    data = chunks_to_json_dict(chunks)

    assert data["schema_version"] == "0.1.0"
    assert data["parser"] == {"name": "techdoc-parser", "version": "0.1.0"}
    assert data["chunk_count"] == 2
    assert data["chunks"] == [chunk.to_dict() for chunk in chunks]
    first_chunk = data["chunks"][0]
    assert isinstance(first_chunk, dict)
    assert first_chunk["source_page_numbers"] == [1]
    assert first_chunk["source_block_ids"] == ["chunk-1-block"]
    assert first_chunk["source_text_block_ids"] == ["chunk-1-text"]
    assert first_chunk["metadata"] == {"chunk_index": "1"}


def test_chunks_to_json_returns_valid_indented_json() -> None:
    """Chunk JSON string should be parseable and indented."""
    json_text = chunks_to_json([_chunk("chunk-1", "First")], indent=2)

    data = json.loads(json_text)

    assert data["schema_version"] == "0.1.0"
    assert data["parser"]["name"] == "techdoc-parser"
    assert data["chunk_count"] == 1
    assert '\n  "chunk_count"' in json_text


def test_export_chunks_json_writes_file(tmp_path: Path) -> None:
    """Chunk JSON exporter should write chunk data to disk."""
    output_path = tmp_path / "nested" / "chunks.json"

    export_chunks_json([_chunk("chunk-1", "First")], output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "0.1.0"
    assert data["parser"]["version"]
    assert data["chunk_count"] == 1
    assert data["chunks"][0]["id"] == "chunk-1"


def test_export_document_chunks_json_creates_and_writes_chunks(tmp_path: Path) -> None:
    """Document chunk export should create semantic chunks before writing."""
    output_path = tmp_path / "chunks.json"

    export_document_chunks_json(_document(), output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "0.1.0"
    assert data["parser"]["name"] == "techdoc-parser"
    assert data["chunk_count"] == 1
    assert data["chunks"][0]["text"] == "Body paragraph."
    assert data["chunks"][0]["source_block_ids"] == ["paragraph-1"]
