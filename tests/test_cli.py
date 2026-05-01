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
