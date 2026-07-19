"""Tests for export metadata helpers."""

from techdoc_parser.version import get_export_metadata


def test_get_export_metadata_returns_schema_and_parser_versions() -> None:
    """Export metadata should identify schema and parser versions."""
    metadata = get_export_metadata()

    parser = metadata["parser"]

    assert metadata["schema_version"] == "0.1.0"
    assert isinstance(parser, dict)
    assert parser["name"] == "techdoc-parser"
    assert parser["version"]
