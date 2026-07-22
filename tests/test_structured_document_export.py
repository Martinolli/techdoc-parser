"""Tests for optional structured-document artifact export."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import fitz
import pytest

from techdoc_parser.cli import main
from techdoc_parser.contracts import build_structured_document_artifact
from techdoc_parser.core import (
    BoundingBox,
    Document,
    DocumentMetadata,
    HeadingBlock,
    Page,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
    TextBlock,
)
from techdoc_parser.exporters import (
    compute_source_sha256,
    create_output_manifest,
    export_structured_document,
    write_structured_document,
)


def test_public_construction_api_reuses_mapper_and_preserves_metadata(
    tmp_path: Path,
) -> None:
    """Pure API should build a StructuredDocument without filesystem writes."""
    document = _parser_document()
    before = copy.deepcopy(document.to_dict())

    structured = build_structured_document_artifact(
        document,
        document_id="DOC-13G",
        document_title="Synthetic Export Guide",
        document_number="SYN-001",
        revision="A",
        issue="1",
        effective_date="2026-07-22",
        source_checksum="abc123",
    )

    data = structured.to_dict()
    assert data["document"]["document_id"] == "DOC-13G"
    assert data["document"]["document_title"] == "Synthetic Export Guide"
    assert data["document"]["document_number"] == "SYN-001"
    assert data["document"]["revision"] == "A"
    assert data["document"]["issue"] == "1"
    assert data["document"]["effective_date"] == "2026-07-22"
    assert data["document"]["source_hash"] == "abc123"
    assert data["tables"]
    assert document.to_dict() == before
    assert list(tmp_path.iterdir()) == []


def test_public_construction_api_leaves_missing_optional_metadata_absent() -> None:
    data = build_structured_document_artifact(
        _parser_document(),
        document_id="DOC-13G",
    ).to_dict()

    metadata = data["document"]
    assert "document_title" not in metadata
    assert "document_number" not in metadata
    assert "revision" not in metadata
    assert "issue" not in metadata
    assert "effective_date" not in metadata
    assert "source_hash" not in metadata


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        (b"abc", hashlib.sha256(b"abc").hexdigest()),
        ("Snowman: \u2603\nBinary:\x00\xff".encode(), None),
    ],
)
def test_compute_source_sha256_hashes_exact_file_bytes(
    tmp_path: Path,
    payload: bytes,
    expected: str | None,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(payload)

    digest = compute_source_sha256(source)

    assert digest == (expected or hashlib.sha256(payload).hexdigest())
    assert digest == digest.lower()
    assert len(digest) == 64
    assert compute_source_sha256(source) == digest


def test_compute_source_sha256_missing_file_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        compute_source_sha256(tmp_path / "missing.pdf")


def test_extracted_text_changes_do_not_change_source_hash(tmp_path: Path) -> None:
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"source bytes")
    first = compute_source_sha256(source)

    document = _parser_document()
    document.pages[0].blocks[0].text = "Changed extracted text only"

    assert compute_source_sha256(source) == first


def test_write_structured_document_writes_valid_deterministic_json(
    tmp_path: Path,
) -> None:
    structured = build_structured_document_artifact(
        _parser_document(),
        document_id="DOC-13G",
        document_title="Synthetic Export Guide",
    )
    first_path = tmp_path / "nested" / "structured.json"
    second_path = tmp_path / "second.json"

    written = write_structured_document(structured, first_path)
    write_structured_document(structured, second_path)

    assert written == first_path
    assert json.loads(first_path.read_text(encoding="utf-8"))["schema_name"] == (
        "techdoc-structured-document"
    )
    assert first_path.read_bytes().endswith(b"\n")
    assert first_path.read_bytes() == second_path.read_bytes()
    assert "\u2603" in first_path.read_text(encoding="utf-8")


def test_write_structured_document_rejects_existing_destination_by_default(
    tmp_path: Path,
) -> None:
    output = tmp_path / "structured.json"
    output.write_text("old", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_structured_document(
            build_structured_document_artifact(_parser_document(), document_id="DOC"),
            output,
        )

    assert output.read_text(encoding="utf-8") == "old"


def test_write_structured_document_overwrites_only_when_explicit(
    tmp_path: Path,
) -> None:
    output = tmp_path / "structured.json"
    output.write_text("old", encoding="utf-8")

    write_structured_document(
        build_structured_document_artifact(_parser_document(), document_id="DOC"),
        output,
        overwrite=True,
    )

    assert (
        json.loads(output.read_text(encoding="utf-8"))["document"]["document_id"]
        == "DOC"
    )


def test_write_structured_document_rejects_directory_output(tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError):
        write_structured_document(
            build_structured_document_artifact(_parser_document(), document_id="DOC"),
            tmp_path,
        )


def test_write_structured_document_preserves_destination_after_serialization_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "structured.json"
    output.write_text("old", encoding="utf-8")

    def fail_to_json(
        self: object,
        indent: int | None = 2,
    ) -> str:
        raise RuntimeError("serialization failed")

    structured = build_structured_document_artifact(
        _parser_document(), document_id="DOC"
    )
    monkeypatch.setattr(type(structured), "to_json", fail_to_json)

    with pytest.raises(RuntimeError, match="serialization failed"):
        write_structured_document(structured, output, overwrite=True)

    assert output.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_structured_document_cleans_temporary_file_after_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "structured.json"

    def fail_replace(
        src: str | bytes | os.PathLike[str],
        dst: str | bytes | os.PathLike[str],
    ) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        write_structured_document(
            build_structured_document_artifact(_parser_document(), document_id="DOC"),
            output,
        )

    assert not output.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_export_structured_document_returns_checksums_and_preserves_document(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source bytes")
    output = tmp_path / "structured.json"
    document = _parser_document(source_path=str(source))
    before = copy.deepcopy(document.to_dict())

    artifact = export_structured_document(
        document,
        source_path=source,
        output_path=output,
        document_id="DOC-13G",
        document_title="Synthetic Export Guide",
    )

    data = json.loads(output.read_text(encoding="utf-8"))
    assert artifact.output_path == output
    assert artifact.schema_name == "techdoc-structured-document"
    assert artifact.schema_version == "0.1.0"
    assert artifact.source_sha256 == hashlib.sha256(b"source bytes").hexdigest()
    assert artifact.artifact_sha256 == hashlib.sha256(output.read_bytes()).hexdigest()
    assert artifact.document_id == "DOC-13G"
    assert data["document"]["source_hash"] == artifact.source_sha256
    assert data["document"]["source_filename"] == "source.pdf"
    assert str(output) not in json.dumps(data)
    assert document.to_dict() == before


def test_export_structured_document_rejects_input_output_conflict(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source bytes")

    with pytest.raises(ValueError, match="must not be the input source path"):
        export_structured_document(
            _parser_document(source_path=str(source)),
            source_path=source,
            output_path=source,
            document_id="DOC-13G",
        )


def test_manifest_adds_structured_document_entry_only_when_supplied(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source bytes")
    output = tmp_path / "structured.json"
    document = _parser_document(source_path=str(source))
    artifact = export_structured_document(
        document,
        source_path=source,
        output_path=output,
        document_id="DOC-13G",
    )

    baseline = create_output_manifest(document=document, document_json_path="doc.json")
    manifest = create_output_manifest(
        document=document,
        document_json_path="doc.json",
        structured_document_artifact=artifact.to_manifest_entry(),
    )

    assert baseline["outputs"] == {"document_json": "doc.json"}
    assert "artifacts" not in baseline
    assert manifest["outputs"]["document_json"] == "doc.json"
    assert manifest["outputs"]["structured_document"] == str(output)
    assert manifest["artifacts"] == [
        {
            "artifact_type": "structured_document",
            "path": str(output),
            "media_type": "application/json",
            "schema_name": "techdoc-structured-document",
            "schema_version": "0.1.0",
            "source_sha256": artifact.source_sha256,
            "artifact_sha256": artifact.artifact_sha256,
            "document_id": "DOC-13G",
        }
    ]


def test_cli_default_does_not_create_structured_document_output(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "manual.pdf"
    output_path = tmp_path / "manual.json"
    structured_path = tmp_path / "structured.json"
    _create_test_pdf(input_path)

    result = main([str(input_path), "--output", str(output_path)])

    assert result == 0
    assert output_path.exists()
    assert not structured_path.exists()


def test_cli_writes_structured_document_with_explicit_metadata(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "manual.pdf"
    output_path = tmp_path / "manual.json"
    structured_path = tmp_path / "structured.json"
    _create_test_pdf(input_path, text="1 Synthetic Export\nSee Section 1.")

    first = main(
        [
            str(input_path),
            "--output",
            str(output_path),
            "--structured-document-output",
            str(structured_path),
            "--structured-document-id",
            "DOC-13G",
            "--document-title",
            "Synthetic Export Guide",
            "--document-number",
            "SYN-001",
        ]
    )
    first_bytes = structured_path.read_bytes()
    second = main(
        [
            str(input_path),
            "--output",
            str(output_path),
            "--structured-document-output",
            str(structured_path),
            "--structured-document-id",
            "DOC-13G",
            "--document-title",
            "Synthetic Export Guide",
            "--document-number",
            "SYN-001",
            "--structured-document-overwrite",
        ]
    )

    data = json.loads(structured_path.read_text(encoding="utf-8"))
    assert first == 0
    assert second == 0
    assert structured_path.read_bytes() == first_bytes
    assert data["schema_name"] == "techdoc-structured-document"
    assert data["schema_version"] == "0.1.0"
    assert data["document"]["document_id"] == "DOC-13G"
    assert data["document"]["document_title"] == "Synthetic Export Guide"
    assert data["document"]["document_number"] == "SYN-001"
    assert data["document"]["source_hash"] == compute_source_sha256(input_path)


def test_cli_requires_document_id_when_structured_output_requested(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "manual.pdf"
    output_path = tmp_path / "manual.json"
    structured_path = tmp_path / "structured.json"
    _create_test_pdf(input_path)

    result = main(
        [
            str(input_path),
            "--output",
            str(output_path),
            "--structured-document-output",
            str(structured_path),
        ]
    )

    assert result == 1
    assert not output_path.exists()
    assert not structured_path.exists()


def test_cli_rejects_unused_structured_metadata(tmp_path: Path) -> None:
    input_path = tmp_path / "manual.pdf"
    output_path = tmp_path / "manual.json"
    _create_test_pdf(input_path)

    result = main(
        [
            str(input_path),
            "--output",
            str(output_path),
            "--structured-document-id",
            "DOC-13G",
        ]
    )

    assert result == 1
    assert not output_path.exists()


def test_cli_manifest_registers_structured_document_after_success(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "manual.pdf"
    output_path = tmp_path / "manual.json"
    structured_path = tmp_path / "structured.json"
    manifest_path = tmp_path / "manifest.json"
    _create_test_pdf(input_path)

    result = main(
        [
            str(input_path),
            "--output",
            str(output_path),
            "--structured-document-output",
            str(structured_path),
            "--structured-document-id",
            "DOC-13G",
            "--manifest-output",
            str(manifest_path),
        ]
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = manifest["artifacts"][0]
    assert result == 0
    assert manifest["outputs"]["structured_document"] == str(structured_path)
    assert artifact["artifact_type"] == "structured_document"
    assert artifact["schema_name"] == "techdoc-structured-document"
    assert artifact["schema_version"] == "0.1.0"
    assert artifact["media_type"] == "application/json"
    assert artifact["source_sha256"] == compute_source_sha256(input_path)
    assert (
        artifact["artifact_sha256"]
        == hashlib.sha256(structured_path.read_bytes()).hexdigest()
    )


def test_cli_artifact_failure_prevents_manifest_success_entry(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "manual.pdf"
    output_path = tmp_path / "manual.json"
    structured_path = tmp_path / "structured.json"
    manifest_path = tmp_path / "manifest.json"
    structured_path.write_text("existing", encoding="utf-8")
    _create_test_pdf(input_path)

    result = main(
        [
            str(input_path),
            "--output",
            str(output_path),
            "--structured-document-output",
            str(structured_path),
            "--structured-document-id",
            "DOC-13G",
            "--manifest-output",
            str(manifest_path),
        ]
    )

    assert result == 1
    assert not output_path.exists()
    assert structured_path.read_text(encoding="utf-8") == "existing"
    assert not manifest_path.exists()


def test_cli_rejects_structured_output_input_path_conflict_before_writing_json(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "manual.pdf"
    output_path = tmp_path / "manual.json"
    _create_test_pdf(input_path)

    result = main(
        [
            str(input_path),
            "--output",
            str(output_path),
            "--structured-document-output",
            str(input_path),
            "--structured-document-id",
            "DOC-13G",
        ]
    )

    assert result == 1
    assert not output_path.exists()


def _parser_document(source_path: str = "C:\\synthetic\\manual.pdf") -> Document:
    source = SourceLocation(
        document_path=source_path,
        page_number=1,
        bbox=BoundingBox(x0=72.0, y0=96.0, x1=420.0, y1=116.0),
        extraction_method="synthetic",
        confidence=1.0,
    )
    text = TextBlock(
        id="page-1-text-1",
        text="1 Synthetic Export Guide \u2603",
        source=source,
        normalized_text="1 Synthetic Export Guide \u2603",
    )
    heading = HeadingBlock(
        id="page-1-heading-1",
        source=source,
        text="1 Synthetic Export Guide \u2603",
        normalized_text="1 Synthetic Export Guide \u2603",
        level=1,
    )
    paragraph = ParagraphBlock(
        id="page-1-paragraph-1",
        text="See Section 1. Inspect the synthetic assembly.",
        source=source,
        source_text_block_ids=["page-1-text-1"],
    )
    table = TableBlock(
        id="page-1-table-1",
        source=source,
        text="Table 1 Synthetic Limits\nCondition Limit",
        caption="Table 1 Synthetic Limits",
        source_text_block_ids=["page-1-text-1"],
    )
    return Document(
        id="parser-id",
        source_path=source_path,
        metadata=DocumentMetadata(title="Synthetic PDF Metadata"),
        pages=[
            Page(
                page_number=1,
                has_native_text=True,
                blocks=[text, heading, paragraph, table],
                text_blocks=[text],
            )
        ],
    )


def _create_test_pdf(path: Path, text: str = "CLI generated PDF") -> None:
    document = fitz.open()
    page = document.new_page(width=240.0, height=120.0)
    page.insert_text((20.0, 50.0), text)
    document.save(path)
    document.close()
