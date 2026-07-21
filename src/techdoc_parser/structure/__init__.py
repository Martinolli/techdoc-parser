"""Document structure detection helpers."""

from techdoc_parser.structure.admonitions import (
    AdmonitionCandidate,
    detect_admonition_candidates,
)
from techdoc_parser.structure.cross_references import (
    CrossReferenceCandidate,
    detect_cross_reference_candidates,
)
from techdoc_parser.structure.equations import (
    EquationCandidate,
    detect_equation_candidate,
)
from techdoc_parser.structure.figures import (
    create_figure_blocks_for_page,
    is_figure_caption_text,
)
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
from techdoc_parser.structure.semantic import get_semantic_blocks_for_page
from techdoc_parser.structure.table_regions import create_table_region_blocks_for_page
from techdoc_parser.structure.tables import (
    create_table_blocks_for_page,
    is_table_candidate_text,
)

__all__ = [
    "AdmonitionCandidate",
    "CrossReferenceCandidate",
    "EquationCandidate",
    "classify_text_block_page_furniture",
    "create_figure_blocks_for_page",
    "create_heading_block_from_text_block",
    "create_paragraph_blocks_for_page",
    "create_table_blocks_for_page",
    "create_table_region_blocks_for_page",
    "detect_admonition_candidates",
    "detect_cross_reference_candidates",
    "detect_equation_candidate",
    "detect_heading_level",
    "extract_heading_blocks_from_text_block",
    "get_semantic_blocks_for_page",
    "is_figure_caption_text",
    "is_heading_text",
    "is_likely_page_header_text",
    "is_page_number_text",
    "is_source_footer_text",
    "is_table_candidate_text",
]
