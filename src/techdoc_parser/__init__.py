"""Technical document parsing library."""

from techdoc_parser.core import (
    Block,
    BoundingBox,
    Chunk,
    Document,
    DocumentMetadata,
    FigureBlock,
    FormulaBlock,
    HeadingBlock,
    Page,
    SourceLocation,
    TableBlock,
    TableRegionBlock,
    TextBlock,
)
from techdoc_parser.parser import parse_document
from techdoc_parser.version import PARSER_VERSION

__all__ = [
    "Block",
    "BoundingBox",
    "Chunk",
    "Document",
    "DocumentMetadata",
    "FigureBlock",
    "FormulaBlock",
    "HeadingBlock",
    "Page",
    "SourceLocation",
    "TableBlock",
    "TableRegionBlock",
    "TextBlock",
    "__version__",
    "parse_document",
]

__version__ = PARSER_VERSION
