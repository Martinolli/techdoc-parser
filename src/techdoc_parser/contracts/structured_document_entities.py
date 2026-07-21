"""Map existing table and figure-caption evidence into contract entities.

This module is intentionally contract-only. It does not detect new tables or
figures, reconstruct cells, infer assets, or mutate parser blocks.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from techdoc_parser.contracts.structured_document import (
    StructuredDocumentBlock,
    StructuredDocumentSection,
)
from techdoc_parser.core import Block, FigureBlock, TableBlock, TableRegionBlock


@dataclass(frozen=True)
class StructuredEntityEvidence:
    """A parser block paired with its already-mapped contract block."""

    source_block: Block
    mapped_block: StructuredDocumentBlock


def map_table_evidence(
    *,
    document_id: str,
    evidence: Sequence[StructuredEntityEvidence],
    sections: Sequence[StructuredDocumentSection] = (),
) -> tuple[dict[str, object], ...]:
    """Return root table entities for existing table candidate evidence.

    Root entities intentionally leave ``rows``, ``columns``, and ``cells`` empty
    because current parser evidence is candidate text/region evidence, not
    reconstructed table structure.
    """
    section_paths = _section_paths(sections)
    tables: list[dict[str, object]] = []
    for item in evidence:
        if not isinstance(item.source_block, TableBlock | TableRegionBlock):
            continue

        table = _base_entity(
            entity_id_key="table_id",
            entity_id=_entity_id(
                document_id=document_id,
                prefix="t",
                mapped_block=item.mapped_block,
                sequence_number=len(tables) + 1,
            ),
            mapped_block=item.mapped_block,
            section_paths=section_paths,
        )
        table["text"] = item.mapped_block.text
        table["columns"] = []
        table["rows"] = []
        table["cells"] = []
        table["header_rows"] = []
        table["merged_cells"] = []
        table["is_candidate"] = _is_candidate(item.source_block)
        table["extraction_status"] = (
            "region_only"
            if isinstance(item.source_block, TableRegionBlock)
            else "candidate"
        )

        _add_optional(table, "caption", _non_empty(item.source_block.caption))
        _add_sequence(
            table,
            "source_text_block_ids",
            item.source_block.source_text_block_ids,
        )
        if isinstance(item.source_block, TableRegionBlock):
            _add_sequence(
                table,
                "source_table_block_ids",
                item.source_block.source_table_block_ids,
            )
            _add_sequence(
                table,
                "source_paragraph_block_ids",
                item.source_block.source_paragraph_block_ids,
            )

        tables.append(table)
    return tuple(tables)


def map_figure_caption_evidence(
    *,
    document_id: str,
    evidence: Sequence[StructuredEntityEvidence],
    sections: Sequence[StructuredDocumentSection] = (),
) -> tuple[dict[str, object], ...]:
    """Return root figure entities for existing figure-caption candidates."""
    section_paths = _section_paths(sections)
    figures: list[dict[str, object]] = []
    for item in evidence:
        if not isinstance(item.source_block, FigureBlock):
            continue

        caption = _non_empty(item.source_block.text) or item.mapped_block.text
        figure = _base_entity(
            entity_id_key="figure_id",
            entity_id=_entity_id(
                document_id=document_id,
                prefix="f",
                mapped_block=item.mapped_block,
                sequence_number=len(figures) + 1,
            ),
            mapped_block=item.mapped_block,
            section_paths=section_paths,
        )
        figure["caption"] = caption
        figure["source_caption_text"] = item.mapped_block.text
        figure["is_candidate"] = _is_candidate(item.source_block)
        figure["extraction_status"] = "caption_candidate"
        _add_optional(
            figure,
            "normalized_caption",
            _normalized_caption(item.source_block, caption),
        )
        _add_sequence(
            figure,
            "source_text_block_ids",
            item.source_block.source_text_block_ids,
        )
        _add_optional(
            figure,
            "asset_reference",
            _non_empty(item.source_block.image_path),
        )

        figures.append(figure)
    return tuple(figures)


def _base_entity(
    *,
    entity_id_key: str,
    entity_id: str,
    mapped_block: StructuredDocumentBlock,
    section_paths: dict[str, tuple[str, ...]],
) -> dict[str, object]:
    source_span = mapped_block.source_span.to_dict()
    entity: dict[str, object] = {
        entity_id_key: entity_id,
        "page_start": mapped_block.source_span.page_start,
        "page_end": mapped_block.source_span.page_end,
        "pdf_page_index_start": mapped_block.source_span.pdf_page_index_start,
        "pdf_page_index_end": mapped_block.source_span.pdf_page_index_end,
        "source_block_ids": [mapped_block.block_id],
        "source_span": source_span,
    }
    _add_optional(entity, "page_id", mapped_block.page_id)
    _add_optional(entity, "page_number", mapped_block.page_number)
    _add_optional(entity, "pdf_page_index", mapped_block.pdf_page_index)
    _add_optional(entity, "section_id", mapped_block.section_id)
    if mapped_block.section_id is not None:
        section_path = section_paths.get(mapped_block.section_id)
        if section_path:
            entity["section_path"] = list(section_path)
    if mapped_block.bbox is not None:
        entity["bbox"] = mapped_block.bbox.to_dict()
    return entity


def _entity_id(
    *,
    document_id: str,
    prefix: str,
    mapped_block: StructuredDocumentBlock,
    sequence_number: int,
) -> str:
    pdf_page_index = mapped_block.pdf_page_index
    if pdf_page_index is None:
        pdf_page_index = mapped_block.source_span.pdf_page_index_start
    if pdf_page_index is None:
        return f"{document_id}:{prefix}{sequence_number:04d}"
    return f"{document_id}:p{pdf_page_index}:{prefix}{sequence_number:04d}"


def _section_paths(
    sections: Sequence[StructuredDocumentSection],
) -> dict[str, tuple[str, ...]]:
    return {section.section_id: section.path for section in sections}


def _is_candidate(block: TableBlock | TableRegionBlock | FigureBlock) -> bool:
    return bool(block.is_candidate)


def _normalized_caption(block: FigureBlock, caption: str) -> str | None:
    normalized = _non_empty(block.caption)
    if normalized is None or normalized == caption:
        return None
    return normalized


def _add_optional(data: dict[str, object], key: str, value: object | None) -> None:
    if value is not None:
        data[key] = value


def _add_sequence(data: dict[str, object], key: str, values: Iterable[str]) -> None:
    ordered = [value for value in values if value.strip()]
    if ordered:
        data[key] = ordered


def _non_empty(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value


__all__ = [
    "StructuredEntityEvidence",
    "map_figure_caption_evidence",
    "map_table_evidence",
]
