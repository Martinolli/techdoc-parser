"""Tests for text normalization helpers."""

from techdoc_parser.normalization import normalize_text


def test_normalize_text_trims_leading_and_trailing_whitespace() -> None:
    """normalize_text should trim outer whitespace."""
    assert normalize_text("  Example text  \n") == "Example text"


def test_normalize_text_collapses_repeated_spaces_and_tabs() -> None:
    """normalize_text should collapse repeated spaces and tabs inside lines."""
    assert normalize_text("A   B\t\tC") == "A B C"


def test_normalize_text_normalizes_non_breaking_spaces() -> None:
    """normalize_text should convert non-breaking and thin spaces."""
    assert normalize_text("A\u00a0B\u2009C\u202fD") == "A B C D"


def test_normalize_text_normalizes_windows_line_endings() -> None:
    """normalize_text should convert Windows and old Mac line endings."""
    assert normalize_text("A\r\nB\rC") == "A\nB\nC"


def test_normalize_text_preserves_meaningful_line_breaks() -> None:
    """normalize_text should keep meaningful line breaks."""
    assert normalize_text("Line one\nLine two") == "Line one\nLine two"


def test_normalize_text_collapses_excessive_blank_lines() -> None:
    """normalize_text should collapse three or more newlines."""
    assert normalize_text("A\n\n\n\nB") == "A\n\nB"


def test_normalize_text_does_not_lowercase_text() -> None:
    """normalize_text should preserve casing."""
    assert normalize_text("Mixed CASE") == "Mixed CASE"


def test_normalize_text_preserves_punctuation_units_and_symbols() -> None:
    """normalize_text should preserve punctuation, units, and math symbols."""
    text = "Speed: 12.5 m/s; ΔP = 5 kPa."

    assert normalize_text(text) == text
