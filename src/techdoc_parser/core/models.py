"""Core data models for parsed technical documents."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class BoundingBox:
    """A rectangular source region in document coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        """Validate coordinate ordering."""
        if self.x1 < self.x0:
            raise ValueError("BoundingBox x1 must be greater than or equal to x0.")
        if self.y1 < self.y0:
            raise ValueError("BoundingBox y1 must be greater than or equal to y0.")

    def to_dict(self) -> dict[str, float]:
        """Return a JSON-serializable dictionary."""
        return {
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
        }


@dataclass
class SourceLocation:
    """Traceability metadata for extracted content."""

    document_path: str
    page_number: int | None = None
    bbox: BoundingBox | None = None
    extraction_method: str | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        """Validate source confidence."""
        if self.confidence is None:
            return
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("SourceLocation confidence must be between 0.0 and 1.0.")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        return {
            "document_path": self.document_path,
            "page_number": self.page_number,
            "bbox": self.bbox.to_dict() if self.bbox is not None else None,
            "extraction_method": self.extraction_method,
            "confidence": self.confidence,
        }


@dataclass
class DocumentMetadata:
    """Optional metadata extracted from a source document."""

    title: str | None = None
    author: str | None = None
    subject: str | None = None
    keywords: list[str] = field(default_factory=list)
    producer: str | None = None
    creator: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        return {
            "title": self.title,
            "author": self.author,
            "subject": self.subject,
            "keywords": self.keywords,
            "producer": self.producer,
            "creator": self.creator,
        }


@dataclass
class Block:
    """A generic extracted document block."""

    id: str
    source: SourceLocation
    block_type: str
    text: str | None = None
    normalized_text: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "source": self.source.to_dict(),
            "block_type": self.block_type,
            "text": self.text,
            "normalized_text": self.normalized_text,
        }


@dataclass(init=False)
class TextBlock(Block):
    """A regular text block extracted from a document page."""

    def __init__(
        self,
        id: str,
        text: str,
        source: SourceLocation,
        block_type: str = "text",
        normalized_text: str | None = None,
    ) -> None:
        """Create a text block."""
        super().__init__(
            id=id,
            source=source,
            block_type=block_type,
            text=text,
            normalized_text=normalized_text,
        )


@dataclass
class HeadingBlock(Block):
    """A heading block extracted from a document page."""

    block_type: str = field(default="heading", init=False)
    level: int = 1

    def __post_init__(self) -> None:
        """Validate heading level."""
        if self.level < 1:
            raise ValueError("HeadingBlock level must be greater than or equal to 1.")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        data = super().to_dict()
        data["level"] = self.level
        return data


@dataclass
class TableBlock(Block):
    """A table block extracted from a document page."""

    block_type: str = field(default="table", init=False)
    caption: str | None = None
    rows: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        data = super().to_dict()
        data["caption"] = self.caption
        data["rows"] = self.rows
        return data


@dataclass
class FormulaBlock(Block):
    """A formula block extracted from a document page."""

    block_type: str = field(default="formula", init=False)
    latex: str | None = None
    variables: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        data = super().to_dict()
        data["latex"] = self.latex
        data["variables"] = self.variables
        return data


@dataclass
class FigureBlock(Block):
    """A figure block extracted from a document page."""

    block_type: str = field(default="figure", init=False)
    caption: str | None = None
    image_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        data = super().to_dict()
        data["caption"] = self.caption
        data["image_path"] = self.image_path
        return data


@dataclass
class Page:
    """A page within a parsed document."""

    page_number: int
    width: float | None = None
    height: float | None = None
    text_blocks: list[TextBlock] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate page numbering."""
        if self.page_number < 1:
            raise ValueError("Page page_number must be greater than or equal to 1.")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        return {
            "page_number": self.page_number,
            "width": self.width,
            "height": self.height,
            "text_blocks": [block.to_dict() for block in self.text_blocks],
        }


@dataclass
class Document:
    """A parsed technical document."""

    id: str
    source_path: str
    metadata: DocumentMetadata
    pages: list[Page] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "source_path": self.source_path,
            "metadata": self.metadata.to_dict(),
            "pages": [page.to_dict() for page in self.pages],
        }

    def to_json(self, indent: int = 2) -> str:
        """Return the document as a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
