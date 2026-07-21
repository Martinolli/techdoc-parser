"""Section hierarchy enrichment for structured-document contract blocks.

This module derives contract-only section nodes from existing parser heading
blocks. It does not detect headings, reorder parser blocks, or infer provenance
that is not already present on mapped blocks.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace

from techdoc_parser.contracts.structured_document import (
    StructuredBoundingBox,
    StructuredDocumentBlock,
    StructuredDocumentSection,
    StructuredSourceSpan,
)
from techdoc_parser.core import HeadingBlock

_APPENDIX_OR_ANNEX_RE = re.compile(
    r"^(?P<number>(?:APPENDIX|ANNEX)\s+[A-Z0-9]+)(?:[\s.\-:]+)(?P<title>\S.*)$",
    re.IGNORECASE,
)
_CLAUSE_RE = re.compile(
    r"^(?P<clause>(?:AMC|GM)\d*\s+\S+)\s+(?P<title>\S.*)$",
    re.IGNORECASE,
)
_NUMBERED_HEADING_RE = re.compile(
    r"^(?P<number>\d+(?:\.\d+)*(?:\([A-Za-z0-9]+\))?)(?:[.)])?\s+(?P<title>\S.*)$"
)


@dataclass(frozen=True)
class StructuredHeadingEvidence:
    """A parser heading block paired with its mapped contract block."""

    heading: HeadingBlock
    mapped_block: StructuredDocumentBlock
    include_normalized_heading: bool = True


@dataclass(frozen=True)
class SectionHierarchyResult:
    """Contract sections and blocks after section assignment."""

    sections: tuple[StructuredDocumentSection, ...]
    blocks: tuple[StructuredDocumentBlock, ...]


@dataclass(frozen=True)
class _ParsedHeading:
    title: str
    path_item: str
    section_number: str | None = None
    clause_identifier: str | None = None


@dataclass(frozen=True)
class _SectionStackItem:
    section_id: str
    level: int
    path: tuple[str, ...]


def enrich_structured_document_hierarchy(
    *,
    document_id: str,
    heading_evidence: Sequence[StructuredHeadingEvidence],
    blocks: Sequence[StructuredDocumentBlock],
) -> SectionHierarchyResult:
    """Return sections and section-linked blocks from existing heading evidence."""
    if not heading_evidence:
        return SectionHierarchyResult(sections=(), blocks=tuple(blocks))
    if not document_id.strip():
        raise ValueError("document_id must be a non-empty string.")

    block_positions = _block_positions(blocks)
    ordered_headings = sorted(
        heading_evidence,
        key=lambda evidence: _heading_position(evidence, block_positions),
    )

    sections: list[StructuredDocumentSection] = []
    stack: list[_SectionStackItem] = []
    heading_block_to_section: dict[str, str] = {}

    for sequence_number, evidence in enumerate(ordered_headings, start=1):
        raw_heading = _heading_text(evidence.heading)
        parsed = _parse_heading_text(raw_heading)
        level = evidence.heading.level
        while stack and stack[-1].level >= level:
            stack.pop()

        parent = stack[-1] if stack else None
        section_id = f"{document_id}:s{sequence_number:04d}"
        path = (
            (*parent.path, parsed.path_item)
            if parent is not None
            else (parsed.path_item,)
        )
        section = StructuredDocumentSection(
            section_id=section_id,
            level=level,
            title=parsed.title,
            parent_section_id=parent.section_id if parent is not None else None,
            section_number=parsed.section_number,
            path=path,
            raw_heading=raw_heading,
            normalized_heading=_normalized_heading(evidence),
            clause_identifier=parsed.clause_identifier,
        )
        sections.append(section)
        heading_block_to_section[evidence.mapped_block.block_id] = section_id
        stack.append(_SectionStackItem(section_id=section_id, level=level, path=path))

    enriched_blocks, section_blocks = _assign_blocks_to_sections(
        blocks=blocks,
        heading_block_to_section=heading_block_to_section,
        section_ids=(section.section_id for section in sections),
    )
    enriched_sections = tuple(
        replace(
            section,
            source_span=_source_span_for_section(section_blocks[section.section_id]),
        )
        for section in sections
    )
    return SectionHierarchyResult(sections=enriched_sections, blocks=enriched_blocks)


def _block_positions(
    blocks: Sequence[StructuredDocumentBlock],
) -> dict[str, int]:
    return {block.block_id: index for index, block in enumerate(blocks)}


def _heading_position(
    evidence: StructuredHeadingEvidence,
    block_positions: dict[str, int],
) -> int:
    try:
        return block_positions[evidence.mapped_block.block_id]
    except KeyError as exc:
        raise ValueError(
            f"Heading block {evidence.mapped_block.block_id!r} is not in blocks."
        ) from exc


def _parse_heading_text(raw_heading: str) -> _ParsedHeading:
    stripped = raw_heading.strip()
    if not stripped:
        raise ValueError("Heading text must be a non-empty string.")

    appendix_match = _APPENDIX_OR_ANNEX_RE.match(stripped)
    if appendix_match:
        section_number = appendix_match.group("number")
        title = appendix_match.group("title").strip()
        return _ParsedHeading(
            section_number=section_number,
            title=title,
            path_item=_path_item(section_number, title),
        )

    clause_match = _CLAUSE_RE.match(stripped)
    if clause_match:
        clause_identifier = clause_match.group("clause")
        title = clause_match.group("title").strip()
        return _ParsedHeading(
            section_number=clause_identifier,
            title=title,
            path_item=_path_item(clause_identifier, title),
            clause_identifier=clause_identifier,
        )

    numbered_match = _NUMBERED_HEADING_RE.match(stripped)
    if numbered_match:
        section_number = numbered_match.group("number")
        title = numbered_match.group("title").strip()
        return _ParsedHeading(
            section_number=section_number,
            title=title,
            path_item=_path_item(section_number, title),
        )

    return _ParsedHeading(title=stripped, path_item=stripped)


def _path_item(section_number: str, title: str) -> str:
    return f"{section_number} {title}".strip()


def _heading_text(heading: HeadingBlock) -> str:
    if heading.text is None or not heading.text.strip():
        raise ValueError("Heading text must be a non-empty string.")
    return heading.text


def _normalized_heading(evidence: StructuredHeadingEvidence) -> str | None:
    if not evidence.include_normalized_heading:
        return None
    heading = evidence.heading
    if heading.normalized_text is None or not heading.normalized_text.strip():
        return None
    return heading.normalized_text


def _assign_blocks_to_sections(
    *,
    blocks: Sequence[StructuredDocumentBlock],
    heading_block_to_section: dict[str, str],
    section_ids: Iterable[str],
) -> tuple[
    tuple[StructuredDocumentBlock, ...],
    dict[str, list[StructuredDocumentBlock]],
]:
    section_blocks: dict[str, list[StructuredDocumentBlock]] = {
        section_id: [] for section_id in section_ids
    }
    enriched_blocks: list[StructuredDocumentBlock] = []
    active_section_id: str | None = None

    for block in blocks:
        heading_section_id = heading_block_to_section.get(block.block_id)
        if heading_section_id is not None:
            active_section_id = heading_section_id

        if active_section_id is None or block.section_id == active_section_id:
            enriched_block = block
        else:
            enriched_block = replace(block, section_id=active_section_id)

        enriched_blocks.append(enriched_block)
        if active_section_id is not None:
            section_blocks[active_section_id].append(enriched_block)

    return tuple(enriched_blocks), section_blocks


def _source_span_for_section(
    blocks: Sequence[StructuredDocumentBlock],
) -> StructuredSourceSpan | None:
    if not blocks:
        return None

    spans = tuple(block.source_span for block in blocks)
    source_block_ids = _ordered_unique(block.block_id for block in blocks)
    return StructuredSourceSpan(
        page_start=_min_page_ref(span.page_start for span in spans),
        page_end=_max_page_ref(span.page_end for span in spans),
        pdf_page_index_start=_min_int(span.pdf_page_index_start for span in spans),
        pdf_page_index_end=_max_int(span.pdf_page_index_end for span in spans),
        printed_page_label_start=spans[0].printed_page_label_start,
        printed_page_label_end=spans[-1].printed_page_label_end,
        bbox=_single_block_bbox(blocks),
        source_block_ids=source_block_ids,
        extraction_method=_common_extraction_method(spans),
        char_start=spans[0].char_start if len(spans) == 1 else None,
        char_end=spans[0].char_end if len(spans) == 1 else None,
    )


def _single_block_bbox(
    blocks: Sequence[StructuredDocumentBlock],
) -> StructuredBoundingBox | None:
    if len(blocks) != 1:
        return None
    return blocks[0].source_span.bbox


def _common_extraction_method(
    spans: Sequence[StructuredSourceSpan],
) -> str | None:
    methods = {
        span.extraction_method for span in spans if span.extraction_method is not None
    }
    if len(methods) == 1:
        return next(iter(methods))
    return None


def _min_page_ref(values: Iterable[int | str | None]) -> int | None:
    integer_values = [value for value in values if isinstance(value, int)]
    return min(integer_values) if integer_values else None


def _max_page_ref(values: Iterable[int | str | None]) -> int | None:
    integer_values = [value for value in values if isinstance(value, int)]
    return max(integer_values) if integer_values else None


def _min_int(values: Iterable[int | None]) -> int | None:
    integer_values = [value for value in values if value is not None]
    return min(integer_values) if integer_values else None


def _max_int(values: Iterable[int | None]) -> int | None:
    integer_values = [value for value in values if value is not None]
    return max(integer_values) if integer_values else None


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)


__all__ = [
    "SectionHierarchyResult",
    "StructuredHeadingEvidence",
    "enrich_structured_document_hierarchy",
]
