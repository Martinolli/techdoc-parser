"""Tests for the public package API."""

import techdoc_parser
from techdoc_parser import parse_document


def test_package_can_be_imported() -> None:
    """The package should be importable."""
    assert techdoc_parser is not None


def test_parse_document_exists() -> None:
    """The public parse_document function should be exported."""
    assert callable(parse_document)
