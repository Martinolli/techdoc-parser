"""Document structure detection helpers."""

from techdoc_parser.structure.headings import (
    create_heading_block_from_text_block,
    detect_heading_level,
    extract_heading_blocks_from_text_block,
    is_heading_text,
)
from techdoc_parser.structure.page_furniture import (
    classify_text_block_page_furniture,
    is_likely_page_header_text,
    is_page_number_text,
    is_source_footer_text,
)
from techdoc_parser.structure.paragraphs import create_paragraph_blocks_for_page

__all__ = [
    "classify_text_block_page_furniture",
    "create_heading_block_from_text_block",
    "create_paragraph_blocks_for_page",
    "detect_heading_level",
    "extract_heading_blocks_from_text_block",
    "is_heading_text",
    "is_likely_page_header_text",
    "is_page_number_text",
    "is_source_footer_text",
]
