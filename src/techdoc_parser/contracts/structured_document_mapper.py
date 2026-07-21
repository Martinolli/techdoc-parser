"""Pure mapper from parser core models to the structured-document contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath, PureWindowsPath

from techdoc_parser.contracts.structured_document import (
    StructuredBoundingBox,
    StructuredDocument,
    StructuredDocumentBlock,
    StructuredDocumentMetadata,
    StructuredDocumentPage,
    StructuredDocumentSection,
    StructuredSourceSpan,
    build_structured_document,
)
from techdoc_parser.contracts.structured_document_hierarchy import (
    StructuredHeadingEvidence,
    enrich_structured_document_hierarchy,
)
from techdoc_parser.core import (
    Block,
    BoundingBox,
    Document,
    HeadingBlock,
    Page,
    TextBlock,
)

_BLOCK_TYPE_TO_CONTENT_TYPE = {
    "text": "paragraph",
    "paragraph": "paragraph",
    "heading": "section_heading",
    "table": "table",
    "table_region": "table",
    "figure": "figure_caption",
    "formula": "equation",
}


@dataclass(frozen=True)
class StructuredDocumentMappingOptions:
    """Caller-supplied metadata and toggles for parser-model mapping."""

    document_id: str
    document_title: str | None = None
    revision: str | None = None
    issue: str | None = None
    effective_date: str | None = None
    source_checksum: str | None = None
    include_normalized_text: bool = True
    include_sections: bool = True


def map_document_to_structured_document(
    document: Document,
    *,
    document_id: str,
    document_title: str | None = None,
    revision: str | None = None,
    issue: str | None = None,
    effective_date: str | None = None,
    source_checksum: str | None = None,
    include_normalized_text: bool = True,
    include_sections: bool = True,
) -> StructuredDocument:
    """Map a parser ``Document`` to a structured-document contract object.

    The mapper is pure and additive: it builds new contract objects from fields
    already present on parser objects plus explicit caller metadata. It does not
    read files, write files, invoke exporters, mutate parser objects, or infer
    unavailable document-control provenance.
    """
    options = StructuredDocumentMappingOptions(
        document_id=document_id,
        document_title=document_title,
        revision=revision,
        issue=issue,
        effective_date=effective_date,
        source_checksum=source_checksum,
        include_normalized_text=include_normalized_text,
        include_sections=include_sections,
    )
    return map_document_with_options(document, options)


def map_document_with_options(
    document: Document,
    options: StructuredDocumentMappingOptions,
) -> StructuredDocument:
    """Map a parser ``Document`` using immutable mapping options."""
    pages = [_map_page(page) for page in document.pages]
    blocks: list[StructuredDocumentBlock] = []
    heading_evidence: list[StructuredHeadingEvidence] = []

    for page in document.pages:
        page_id = _page_id_for_page(page)
        page_pdf_index = _pdf_page_index_from_page_number(page.page_number)
        for page_block_index, block in enumerate(page.blocks):
            mapped_block = _map_block(
                block=block,
                page=page,
                page_id=page_id,
                page_pdf_index=page_pdf_index,
                page_block_index=page_block_index,
                document_block_index=len(blocks),
                document_id=options.document_id,
                include_normalized_text=options.include_normalized_text,
            )
            blocks.append(mapped_block)
            if isinstance(block, HeadingBlock):
                heading_evidence.append(
                    StructuredHeadingEvidence(
                        heading=block,
                        mapped_block=mapped_block,
                        include_normalized_heading=options.include_normalized_text,
                    )
                )

    sections: tuple[StructuredDocumentSection, ...] = ()
    if options.include_sections:
        hierarchy = enrich_structured_document_hierarchy(
            document_id=options.document_id,
            heading_evidence=heading_evidence,
            blocks=blocks,
        )
        sections = hierarchy.sections
        blocks = list(hierarchy.blocks)

    metadata = StructuredDocumentMetadata(
        document_id=options.document_id,
        source_filename=_source_filename(document.source_path),
        document_title=options.document_title,
        canonical_title=document.metadata.title,
        page_count=len(pages),
        source_hash=options.source_checksum,
        revision=options.revision,
        issue=options.issue,
        effective_date=options.effective_date,
    )
    return build_structured_document(
        document=metadata,
        pages=pages,
        blocks=blocks,
        sections=sections,
        tables=(),
        figures=(),
        equations=(),
        admonitions=(),
        cross_references=(),
    )


def map_block_type_to_content_type(block: Block) -> str:
    """Return the target content type for one parser block."""
    if isinstance(block, TextBlock) and _is_page_metadata_block(block):
        return "metadata"
    return _BLOCK_TYPE_TO_CONTENT_TYPE.get(block.block_type, "unknown")


def _map_page(page: Page) -> StructuredDocumentPage:
    return StructuredDocumentPage(
        page_id=_page_id_for_page(page),
        pdf_page_index=_pdf_page_index_from_page_number(page.page_number),
        page_number=page.page_number,
        printed_page_label=None,
    )


def _map_block(
    *,
    block: Block,
    page: Page,
    page_id: str,
    page_pdf_index: int,
    page_block_index: int,
    document_block_index: int,
    document_id: str,
    include_normalized_text: bool,
) -> StructuredDocumentBlock:
    block_id = _block_id(
        block=block,
        document_id=document_id,
        pdf_page_index=page_pdf_index,
        page_block_index=page_block_index,
    )
    text = _block_text(block)
    bbox = _map_bbox(block.source.bbox) if block.source and block.source.bbox else None

    return StructuredDocumentBlock(
        block_id=block_id,
        block_type=map_block_type_to_content_type(block),
        text=text,
        document_block_index=document_block_index,
        page_block_index=page_block_index,
        page_id=page_id,
        page_number=page.page_number,
        pdf_page_index=page_pdf_index,
        normalized_text=_normalized_text(block, include_normalized_text),
        source_span=_map_source_span(block, page, block_id, bbox),
        bbox=bbox,
    )


def _map_source_span(
    block: Block,
    page: Page,
    block_id: str,
    bbox: StructuredBoundingBox | None,
) -> StructuredSourceSpan:
    source_page_number = (
        block.source.page_number
        if block.source is not None and block.source.page_number is not None
        else page.page_number
    )
    pdf_page_index = _pdf_page_index_from_page_number(source_page_number)

    return StructuredSourceSpan(
        page_start=source_page_number,
        page_end=source_page_number,
        pdf_page_index_start=pdf_page_index,
        pdf_page_index_end=pdf_page_index,
        bbox=bbox,
        source_block_ids=(block_id,),
        extraction_method=block.source.extraction_method if block.source else None,
    )


def _block_id(
    *,
    block: Block,
    document_id: str,
    pdf_page_index: int,
    page_block_index: int,
) -> str:
    if block.id.strip():
        return block.id
    return f"{document_id}:p{pdf_page_index}:b{page_block_index}"


def _block_text(block: Block) -> str:
    if block.text is None or not block.text.strip():
        raise ValueError(
            f"Cannot map parser block {block.id!r} without non-empty raw text."
        )
    return block.text


def _normalized_text(block: Block, include_normalized_text: bool) -> str | None:
    if not include_normalized_text:
        return None
    if block.normalized_text is None or not block.normalized_text.strip():
        return None
    return block.normalized_text


def _map_bbox(bbox: BoundingBox) -> StructuredBoundingBox:
    return StructuredBoundingBox(
        x0=bbox.x0,
        y0=bbox.y0,
        x1=bbox.x1,
        y1=bbox.y1,
    )


def _page_id_for_page(page: Page) -> str:
    return f"page-{page.page_number:04d}"


def _pdf_page_index_from_page_number(page_number: int) -> int:
    return page_number - 1


def _source_filename(source_path: str) -> str:
    if "\\" in source_path or PureWindowsPath(source_path).drive:
        return PureWindowsPath(source_path).name
    return PurePath(source_path).name


def _is_page_metadata_block(block: TextBlock) -> bool:
    return bool(
        block.is_page_header
        or block.is_page_footer
        or block.is_page_number
        or block.is_page_furniture
    )


__all__ = [
    "StructuredDocumentMappingOptions",
    "map_block_type_to_content_type",
    "map_document_to_structured_document",
    "map_document_with_options",
]
