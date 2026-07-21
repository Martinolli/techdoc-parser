"""Map equation and admonition evidence into structured-document entities.

This module is intentionally contract-only. It does not change parser
extraction, infer mathematical meaning, classify safety severity, or mutate
parser blocks.
"""

from __future__ import annotations

from collections.abc import Sequence

from techdoc_parser.contracts.structured_document import (
    StructuredBoundingBox,
    StructuredDocumentBlock,
    StructuredDocumentSection,
    StructuredSourceSpan,
)
from techdoc_parser.contracts.structured_document_entities import (
    StructuredEntityEvidence,
)
from techdoc_parser.structure.admonitions import detect_admonition_candidates
from techdoc_parser.structure.equations import detect_equation_candidate


def map_equation_evidence(
    *,
    document_id: str,
    evidence: Sequence[StructuredEntityEvidence],
    sections: Sequence[StructuredDocumentSection] = (),
) -> tuple[dict[str, object], ...]:
    """Return root equation entities for conservative equation evidence."""
    section_paths = _section_paths(sections)
    equations: list[dict[str, object]] = []
    seen_source_blocks: set[str] = set()
    for item in evidence:
        candidate = detect_equation_candidate(
            item.source_block,
            source_block_id=item.mapped_block.block_id,
        )
        if candidate is None or candidate.source_block_id in seen_source_blocks:
            continue
        seen_source_blocks.add(candidate.source_block_id)

        equation = _base_entity(
            entity_id_key="equation_id",
            entity_id=_entity_id(
                document_id=document_id,
                prefix="e",
                sequence_number=len(equations) + 1,
            ),
            mapped_blocks=(item.mapped_block,),
            section_paths=section_paths,
        )
        equation["raw_text"] = candidate.raw_text
        _add_optional(equation, "equation_label", candidate.label)
        _add_optional(
            equation,
            "normalized_representation",
            candidate.normalized_representation,
        )
        equations.append(equation)
    return tuple(equations)


def map_admonition_evidence(
    *,
    document_id: str,
    evidence: Sequence[StructuredEntityEvidence],
    sections: Sequence[StructuredDocumentSection] = (),
) -> tuple[dict[str, object], ...]:
    """Return root admonition entities for explicit-label admonition evidence."""
    section_paths = _section_paths(sections)
    evidence_by_id = {item.mapped_block.block_id: item for item in evidence}
    candidates = detect_admonition_candidates(
        [item.source_block for item in evidence],
        source_block_ids=[item.mapped_block.block_id for item in evidence],
    )
    admonitions: list[dict[str, object]] = []
    for candidate in candidates:
        candidate_blocks = tuple(
            evidence_by_id[block_id].mapped_block
            for block_id in candidate.source_block_ids
            if block_id in evidence_by_id
        )
        if not candidate_blocks:
            continue

        admonition = _base_entity(
            entity_id_key="admonition_id",
            entity_id=_entity_id(
                document_id=document_id,
                prefix="a",
                sequence_number=len(admonitions) + 1,
            ),
            mapped_blocks=candidate_blocks,
            section_paths=section_paths,
        )
        admonition["admonition_type"] = candidate.normalized_type
        admonition["normalized_type"] = candidate.normalized_type
        admonition["raw_label"] = candidate.raw_label
        admonition["body_text"] = candidate.body_text
        admonitions.append(admonition)
    return tuple(admonitions)


def _base_entity(
    *,
    entity_id_key: str,
    entity_id: str,
    mapped_blocks: Sequence[StructuredDocumentBlock],
    section_paths: dict[str, tuple[str, ...]],
) -> dict[str, object]:
    source_span = _source_span_for_blocks(mapped_blocks)
    first_block = mapped_blocks[0]
    entity: dict[str, object] = {
        entity_id_key: entity_id,
        "page_start": source_span.page_start,
        "page_end": source_span.page_end,
        "pdf_page_index_start": source_span.pdf_page_index_start,
        "pdf_page_index_end": source_span.pdf_page_index_end,
        "source_block_ids": list(source_span.source_block_ids),
        "source_span": source_span.to_dict(),
    }
    _add_optional(entity, "page_id", first_block.page_id)
    _add_optional(entity, "page_number", first_block.page_number)
    _add_optional(entity, "pdf_page_index", first_block.pdf_page_index)

    section_id = _common_section_id(mapped_blocks)
    _add_optional(entity, "section_id", section_id)
    if section_id is not None:
        section_path = section_paths.get(section_id)
        if section_path:
            entity["section_path"] = list(section_path)

    if len(mapped_blocks) == 1 and first_block.bbox is not None:
        entity["bbox"] = first_block.bbox.to_dict()
    return entity


def _source_span_for_blocks(
    mapped_blocks: Sequence[StructuredDocumentBlock],
) -> StructuredSourceSpan:
    source_spans = [block.source_span for block in mapped_blocks]
    page_starts = [
        _required_int(span.page_start, field_name="page_start") for span in source_spans
    ]
    page_ends = [
        _required_int(span.page_end, field_name="page_end") for span in source_spans
    ]
    pdf_page_index_starts = [
        span.pdf_page_index_start
        for span in source_spans
        if span.pdf_page_index_start is not None
    ]
    pdf_page_index_ends = [
        span.pdf_page_index_end
        for span in source_spans
        if span.pdf_page_index_end is not None
    ]
    extraction_methods = {
        span.extraction_method for span in source_spans if span.extraction_method
    }
    extraction_method = (
        next(iter(extraction_methods)) if len(extraction_methods) == 1 else None
    )
    bbox = _single_block_bbox(mapped_blocks)
    return StructuredSourceSpan(
        page_start=min(page_starts),
        page_end=max(page_ends),
        pdf_page_index_start=min(pdf_page_index_starts),
        pdf_page_index_end=max(pdf_page_index_ends),
        bbox=bbox,
        source_block_ids=tuple(block.block_id for block in mapped_blocks),
        extraction_method=extraction_method,
    )


def _single_block_bbox(
    mapped_blocks: Sequence[StructuredDocumentBlock],
) -> StructuredBoundingBox | None:
    if len(mapped_blocks) != 1:
        return None
    return mapped_blocks[0].bbox


def _required_int(value: int | str | None, *, field_name: str) -> int:
    if value is None:
        raise ValueError(f"Cannot map entity with missing {field_name}.")
    return int(value)


def _common_section_id(
    mapped_blocks: Sequence[StructuredDocumentBlock],
) -> str | None:
    section_ids = {block.section_id for block in mapped_blocks}
    if len(section_ids) != 1:
        return None
    return next(iter(section_ids))


def _entity_id(*, document_id: str, prefix: str, sequence_number: int) -> str:
    return f"{document_id}:{prefix}{sequence_number:04d}"


def _section_paths(
    sections: Sequence[StructuredDocumentSection],
) -> dict[str, tuple[str, ...]]:
    return {section.section_id: section.path for section in sections}


def _add_optional(data: dict[str, object], key: str, value: object | None) -> None:
    if value is not None:
        data[key] = value


__all__ = [
    "map_admonition_evidence",
    "map_equation_evidence",
]
