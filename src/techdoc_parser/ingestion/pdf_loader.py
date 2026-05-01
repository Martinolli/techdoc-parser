"""Basic PDF ingestion using PyMuPDF."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import fitz  # type: ignore[import-untyped]

from techdoc_parser.core import (
    BoundingBox,
    Document,
    DocumentMetadata,
    Page,
    SourceLocation,
    TextBlock,
)
from techdoc_parser.normalization import normalize_text

logger = logging.getLogger(__name__)


class PDFLoader:
    """Load a native-text PDF into the core document model."""

    def __init__(self, path: str) -> None:
        """Create a PDF loader for a source path."""
        self.path = Path(path)
        self._validate_path()

    def load(self) -> Document:
        """Load the PDF into a Document."""
        logger.info("Loading PDF: %s", self.path)
        with fitz.open(self.path) as pdf_document:
            metadata = self._extract_metadata(pdf_document.metadata)
            document = Document(
                id=self.path.stem,
                source_path=str(self.path),
                metadata=metadata,
            )

            for page_index, pdf_page in enumerate(pdf_document, start=1):
                page = Page(
                    page_number=page_index,
                    width=float(pdf_page.rect.width),
                    height=float(pdf_page.rect.height),
                )
                self._add_text_blocks(page=page, pdf_page=pdf_page)
                self._update_page_text_status(page)
                document.pages.append(page)

        logger.info(
            "Finished loading PDF: %s (%s pages)",
            self.path,
            len(document.pages),
        )
        return document

    def _validate_path(self) -> None:
        if not self.path.exists() or not self.path.is_file():
            raise FileNotFoundError(
                f"PDF path does not exist or is not a file: {self.path}"
            )
        if self.path.suffix.lower() != ".pdf":
            raise ValueError(
                f"Unsupported file extension for PDFLoader: {self.path.suffix}"
            )

    def _add_text_blocks(self, page: Page, pdf_page: fitz.Page) -> None:
        raw_blocks = cast(list[tuple[Any, ...]], pdf_page.get_text("blocks"))
        text_block_index = 1

        for raw_block in raw_blocks:
            if len(raw_block) < 5:
                continue

            text = str(raw_block[4])
            if not text.strip():
                continue

            source = SourceLocation(
                document_path=str(self.path),
                page_number=page.page_number,
                bbox=BoundingBox(
                    x0=float(raw_block[0]),
                    y0=float(raw_block[1]),
                    x1=float(raw_block[2]),
                    y1=float(raw_block[3]),
                ),
                extraction_method="pymupdf",
                confidence=1.0,
            )
            block = TextBlock(
                id=f"page-{page.page_number}-text-{text_block_index}",
                text=text,
                source=source,
                normalized_text=normalize_text(text),
            )
            page.text_blocks.append(block)
            page.blocks.append(block)
            text_block_index += 1

    def _update_page_text_status(self, page: Page) -> None:
        page.has_native_text = len(page.text_blocks) > 0
        page.requires_ocr = not page.has_native_text

        if page.requires_ocr:
            logger.warning(
                "Page %s in %s appears to have no native text and may require OCR.",
                page.page_number,
                self.path,
            )

    @staticmethod
    def _extract_metadata(metadata: dict[str, Any]) -> DocumentMetadata:
        return DocumentMetadata(
            title=_metadata_value(metadata, "title"),
            author=_metadata_value(metadata, "author"),
            subject=_metadata_value(metadata, "subject"),
            keywords=_split_keywords(_metadata_value(metadata, "keywords")),
            producer=_metadata_value(metadata, "producer"),
            creator=_metadata_value(metadata, "creator"),
        )


def _metadata_value(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    return stripped if stripped else None


def _split_keywords(value: str | None) -> list[str]:
    if value is None:
        return []

    if "," in value:
        parts = value.split(",")
    elif ";" in value:
        parts = value.split(";")
    else:
        parts = value.split()

    return [part.strip() for part in parts if part.strip()]
