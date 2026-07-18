"""Tests for the command-line interface."""

import json
from pathlib import Path

import fitz

from techdoc_parser.cli import main


def _create_test_pdf(path: Path, text: str = "CLI generated PDF") -> None:
    document = fitz.open()
    page = document.new_page(width=200.0, height=100.0)
    page.insert_text((20.0, 50.0), text)
    document.save(path)
    document.close()


def test_cli_parses_generated_pdf_and_writes_json(tmp_path: Path) -> None:
    """CLI should parse a PDF and write JSON output."""
    input_path = tmp_path / "manual.pdf"
    output_path = tmp_path / "output" / "manual.json"
    _create_test_pdf(input_path)

    result = main([str(input_path), "--output", str(output_path)])

    assert result == 0
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["id"] == "manual"
    assert len(data["pages"]) == 1


def test_cli_can_write_semantic_chunks_json(tmp_path: Path) -> None:
    """CLI should optionally write semantic chunks JSON output."""
    input_path = tmp_path / "manual.pdf"
    output_path = tmp_path / "output" / "manual.json"
    chunks_output_path = tmp_path / "output" / "chunks.json"
    _create_test_pdf(input_path, text="This generated PDF creates a body paragraph.")

    result = main(
        [
            str(input_path),
            "--output",
            str(output_path),
            "--chunks-output",
            str(chunks_output_path),
            "--chunk-max-chars",
            "80",
        ]
    )

    assert result == 0
    assert output_path.exists()
    assert chunks_output_path.exists()

    chunks_data = json.loads(chunks_output_path.read_text(encoding="utf-8"))
    assert chunks_data["chunk_count"] >= 1
    assert chunks_data["chunks"]
    assert "source_page_numbers" in chunks_data["chunks"][0]


def test_cli_can_write_validation_report_json(tmp_path: Path) -> None:
    """CLI should optionally write validation report JSON output."""
    input_path = tmp_path / "manual.pdf"
    output_path = tmp_path / "output" / "manual.json"
    chunks_output_path = tmp_path / "output" / "chunks.json"
    validation_output_path = tmp_path / "output" / "validation.json"
    _create_test_pdf(input_path, text="This generated PDF creates a body paragraph.")

    result = main(
        [
            str(input_path),
            "--output",
            str(output_path),
            "--chunks-output",
            str(chunks_output_path),
            "--validation-output",
            str(validation_output_path),
        ]
    )

    assert result == 0
    assert output_path.exists()
    assert chunks_output_path.exists()
    assert validation_output_path.exists()

    validation_data = json.loads(validation_output_path.read_text(encoding="utf-8"))
    assert "issue_count" in validation_data
    assert validation_data["summary"]["page_count"] == 1
    assert "chunk_count" in validation_data["summary"]


def test_cli_creates_chunks_internally_for_validation(tmp_path: Path) -> None:
    """CLI validation should not require chunks JSON output."""
    input_path = tmp_path / "manual.pdf"
    output_path = tmp_path / "output" / "manual.json"
    validation_output_path = tmp_path / "output" / "validation.json"
    _create_test_pdf(input_path, text="This generated PDF creates a body paragraph.")

    result = main(
        [
            str(input_path),
            "--output",
            str(output_path),
            "--validation-output",
            str(validation_output_path),
        ]
    )

    assert result == 0
    assert output_path.exists()
    assert validation_output_path.exists()

    validation_data = json.loads(validation_output_path.read_text(encoding="utf-8"))
    assert "issue_count" in validation_data
    assert validation_data["summary"]["chunk_count"] >= 1


def test_cli_returns_one_for_unsupported_file_type(tmp_path: Path) -> None:
    """CLI should report unsupported input types as user errors."""
    input_path = tmp_path / "manual.txt"
    output_path = tmp_path / "manual.json"
    input_path.write_text("not a pdf", encoding="utf-8")

    result = main([str(input_path), "--output", str(output_path)])

    assert result == 1
    assert not output_path.exists()


def test_cli_returns_one_for_missing_input_file(tmp_path: Path) -> None:
    """CLI should report missing input files as user errors."""
    input_path = tmp_path / "missing.pdf"
    output_path = tmp_path / "manual.json"

    result = main([str(input_path), "--output", str(output_path)])

    assert result == 1
    assert not output_path.exists()
