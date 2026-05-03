"""Document structure detection helpers."""

from techdoc_parser.structure.headings import (
    create_heading_block_from_text_block,
    detect_heading_level,
    is_heading_text,
)

__all__ = [
    "create_heading_block_from_text_block",
    "detect_heading_level",
    "is_heading_text",
]
