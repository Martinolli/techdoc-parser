"""Text normalization utilities."""

from __future__ import annotations

import re

_SPACE_TRANSLATION = str.maketrans(
    {
        "\u00a0": " ",
        "\u2000": " ",
        "\u2001": " ",
        "\u2002": " ",
        "\u2003": " ",
        "\u2004": " ",
        "\u2005": " ",
        "\u2006": " ",
        "\u2007": " ",
        "\u2008": " ",
        "\u2009": " ",
        "\u200a": " ",
        "\u202f": " ",
        "\u205f": " ",
    }
)


def normalize_text(text: str) -> str:
    """Normalize text while preserving content and meaningful line breaks."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.translate(_SPACE_TRANSLATION)
    normalized = "\n".join(normalize_line(line) for line in normalized.split("\n"))
    normalized = normalized.strip()
    return re.sub(r"\n{3,}", "\n\n", normalized)


def normalize_line(line: str) -> str:
    """Normalize spacing inside a single line."""
    return re.sub(r"[ \t]+", " ", line).rstrip()
