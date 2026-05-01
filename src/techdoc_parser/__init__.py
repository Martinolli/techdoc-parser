"""Technical document parsing library."""

from techdoc_parser.core import (
    Block,
    BoundingBox,
    Document,
    DocumentMetadata,
    FigureBlock,
    FormulaBlock,
    HeadingBlock,
    Page,
    SourceLocation,
    TableBlock,
    TextBlock,
)
from techdoc_parser.parser import parse_document

__all__ = [
    "Block",
    "BoundingBox",
    "Document",
    "DocumentMetadata",
    "FigureBlock",
    "FormulaBlock",
    "HeadingBlock",
    "Page",
    "SourceLocation",
    "TableBlock",
    "TextBlock",
    "parse_document",
]
