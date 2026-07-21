"""Map explicit cross-reference evidence into structured-document entities."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from techdoc_parser.contracts.structured_document import (
    StructuredDocumentBlock,
    StructuredDocumentSection,
)
from techdoc_parser.contracts.structured_document_entities import (
    StructuredEntityEvidence,
)
from techdoc_parser.structure.cross_references import (
    CrossReferenceCandidate,
    detect_cross_reference_candidates,
)

_TRAILING_PUNCTUATION_RE = re.compile(r"[.;:]+$")
_TABLE_LABEL_RE = re.compile(
    r"^\s*Table\s+(?P<identifier>[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*)\b",
    re.IGNORECASE,
)
_FIGURE_LABEL_RE = re.compile(
    r"^\s*(?:Figure|Fig\.)\s+(?P<identifier>[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*)\b",
    re.IGNORECASE,
)
_EQUATION_LABEL_RE = re.compile(
    r"^\s*(?:Equation|Eq\.)\s+(?P<identifier>[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*)\b",
    re.IGNORECASE,
)

_LOCAL_REFERENCE_TYPES = {
    "section",
    "clause",
    "paragraph",
    "table",
    "figure",
    "equation",
    "appendix",
    "annex",
    "chapter",
}


@dataclass(frozen=True)
class ResolvedCrossReferenceCandidate:
    """A cross-reference candidate after deterministic local resolution."""

    source_block_id: str
    raw_reference_text: str
    reference_type: str
    target_identifier: str | None
    resolution_status: str
    resolved_target_id: str | None = None
    page_number: int | None = None


def map_cross_reference_evidence(
    *,
    document_id: str,
    evidence: Sequence[StructuredEntityEvidence],
    sections: Sequence[StructuredDocumentSection] = (),
    tables: Sequence[Mapping[str, object]] = (),
    figures: Sequence[Mapping[str, object]] = (),
    equations: Sequence[Mapping[str, object]] = (),
) -> tuple[dict[str, object], ...]:
    """Return root cross-reference entities from explicit textual evidence."""
    evidence_by_id = {item.mapped_block.block_id: item for item in evidence}
    section_paths = _section_paths(sections)
    candidates = detect_cross_reference_candidates(
        [item.source_block for item in evidence],
        source_block_ids=[item.mapped_block.block_id for item in evidence],
    )
    resolved_candidates = resolve_cross_reference_candidates(
        candidates,
        sections=sections,
        tables=tables,
        figures=figures,
        equations=equations,
    )

    references: list[dict[str, object]] = []
    for candidate in resolved_candidates:
        evidence_item = evidence_by_id.get(candidate.source_block_id)
        if evidence_item is None:
            continue
        mapped_block = evidence_item.mapped_block
        reference = _base_reference(
            document_id=document_id,
            sequence_number=len(references) + 1,
            candidate=candidate,
            mapped_block=mapped_block,
            section_paths=section_paths,
        )
        references.append(reference)
    return tuple(references)


def resolve_cross_reference_candidates(
    candidates: Sequence[CrossReferenceCandidate],
    *,
    sections: Sequence[StructuredDocumentSection] = (),
    tables: Sequence[Mapping[str, object]] = (),
    figures: Sequence[Mapping[str, object]] = (),
    equations: Sequence[Mapping[str, object]] = (),
) -> tuple[ResolvedCrossReferenceCandidate, ...]:
    """Resolve candidates only by exact documented local identifiers."""
    indexes = _ResolutionIndexes.from_entities(
        sections=sections,
        tables=tables,
        figures=figures,
        equations=equations,
    )
    return tuple(_resolve_candidate(candidate, indexes) for candidate in candidates)


@dataclass(frozen=True)
class _ResolutionIndexes:
    sections: dict[str, tuple[str, ...]]
    tables: dict[str, tuple[str, ...]]
    figures: dict[str, tuple[str, ...]]
    equations: dict[str, tuple[str, ...]]

    @classmethod
    def from_entities(
        cls,
        *,
        sections: Sequence[StructuredDocumentSection],
        tables: Sequence[Mapping[str, object]],
        figures: Sequence[Mapping[str, object]],
        equations: Sequence[Mapping[str, object]],
    ) -> _ResolutionIndexes:
        return cls(
            sections=_section_index(sections),
            tables=_entity_index(
                tables,
                id_key="table_id",
                label_pattern=_TABLE_LABEL_RE,
                text_keys=("caption", "text"),
            ),
            figures=_entity_index(
                figures,
                id_key="figure_id",
                label_pattern=_FIGURE_LABEL_RE,
                text_keys=("caption", "source_caption_text"),
            ),
            equations=_entity_index(
                equations,
                id_key="equation_id",
                label_pattern=_EQUATION_LABEL_RE,
                text_keys=("equation_label", "raw_text"),
            ),
        )


def _resolve_candidate(
    candidate: CrossReferenceCandidate,
    indexes: _ResolutionIndexes,
) -> ResolvedCrossReferenceCandidate:
    if candidate.reference_type == "external_document":
        return _resolved_candidate(candidate, status="external")
    if candidate.reference_type not in _LOCAL_REFERENCE_TYPES:
        return _resolved_candidate(candidate, status="not_attempted")
    if candidate.target_identifier is None:
        return _resolved_candidate(candidate, status="not_attempted")

    targets = _target_ids_for_candidate(candidate, indexes)
    if not targets:
        return _resolved_candidate(candidate, status="unresolved")
    if len(targets) > 1:
        return _resolved_candidate(candidate, status="ambiguous")
    return _resolved_candidate(
        candidate,
        status="resolved",
        resolved_target_id=targets[0],
    )


def _target_ids_for_candidate(
    candidate: CrossReferenceCandidate,
    indexes: _ResolutionIndexes,
) -> tuple[str, ...]:
    key = _identifier_key(candidate.target_identifier)
    if candidate.reference_type in {
        "section",
        "clause",
        "appendix",
        "annex",
        "chapter",
    }:
        return indexes.sections.get(key, ())
    if candidate.reference_type == "table":
        return indexes.tables.get(key, ())
    if candidate.reference_type == "figure":
        return indexes.figures.get(key, ())
    if candidate.reference_type == "equation":
        return indexes.equations.get(key, ())
    return ()


def _resolved_candidate(
    candidate: CrossReferenceCandidate,
    *,
    status: str,
    resolved_target_id: str | None = None,
) -> ResolvedCrossReferenceCandidate:
    return ResolvedCrossReferenceCandidate(
        source_block_id=candidate.source_block_id,
        raw_reference_text=candidate.raw_reference_text,
        reference_type=candidate.reference_type,
        target_identifier=candidate.target_identifier,
        resolution_status=status,
        resolved_target_id=resolved_target_id,
        page_number=candidate.page_number,
    )


def _base_reference(
    *,
    document_id: str,
    sequence_number: int,
    candidate: ResolvedCrossReferenceCandidate,
    mapped_block: StructuredDocumentBlock,
    section_paths: dict[str, tuple[str, ...]],
) -> dict[str, object]:
    source_span = mapped_block.source_span.to_dict()
    reference: dict[str, object] = {
        "reference_id": f"{document_id}:r{sequence_number:04d}",
        "raw_text": candidate.raw_reference_text,
        "raw_reference_text": candidate.raw_reference_text,
        "reference_type": candidate.reference_type,
        "resolution_status": candidate.resolution_status,
        "source_block_ids": [mapped_block.block_id],
        "source_span": source_span,
    }
    _add_optional(reference, "target_identifier", candidate.target_identifier)
    _add_optional(reference, "target_id", candidate.resolved_target_id)
    _add_optional(reference, "page_start", mapped_block.source_span.page_start)
    _add_optional(reference, "page_end", mapped_block.source_span.page_end)
    _add_optional(
        reference,
        "pdf_page_index_start",
        mapped_block.source_span.pdf_page_index_start,
    )
    _add_optional(
        reference,
        "pdf_page_index_end",
        mapped_block.source_span.pdf_page_index_end,
    )
    _add_optional(reference, "page_id", mapped_block.page_id)
    _add_optional(reference, "page_number", mapped_block.page_number)
    _add_optional(reference, "pdf_page_index", mapped_block.pdf_page_index)
    _add_optional(reference, "section_id", mapped_block.section_id)
    if mapped_block.section_id is not None:
        section_path = section_paths.get(mapped_block.section_id)
        if section_path:
            reference["section_path"] = list(section_path)
    if mapped_block.bbox is not None:
        reference["bbox"] = mapped_block.bbox.to_dict()
    return reference


def _section_index(
    sections: Sequence[StructuredDocumentSection],
) -> dict[str, tuple[str, ...]]:
    pairs: list[tuple[str, str]] = []
    for section in sections:
        for identifier in (
            section.section_number,
            section.clause_identifier,
            _prefixed_section_identifier(section),
        ):
            key = _identifier_key(identifier)
            if key:
                pairs.append((key, section.section_id))
    return _group_targets(pairs)


def _prefixed_section_identifier(section: StructuredDocumentSection) -> str | None:
    if section.section_number is None:
        return None
    normalized = section.section_number.strip()
    if normalized.lower().startswith(("appendix ", "annex ", "chapter ")):
        return normalized
    return None


def _entity_index(
    entities: Sequence[Mapping[str, object]],
    *,
    id_key: str,
    label_pattern: re.Pattern[str],
    text_keys: Sequence[str],
) -> dict[str, tuple[str, ...]]:
    pairs: list[tuple[str, str]] = []
    for entity in entities:
        entity_id = _optional_str(entity.get(id_key))
        if entity_id is None:
            continue
        pairs.append((_identifier_key(entity_id), entity_id))
        for text_key in text_keys:
            text = _optional_str(entity.get(text_key))
            if text is None:
                continue
            label_match = label_pattern.match(text)
            if label_match is not None:
                pairs.append(
                    (_identifier_key(label_match.group("identifier")), entity_id)
                )
            pairs.append((_identifier_key(text), entity_id))
    return _group_targets((key, target) for key, target in pairs if key)


def _group_targets(pairs: Iterable[tuple[str, str]]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for key, target_id in pairs:
        grouped.setdefault(key, [])
        if target_id not in grouped[key]:
            grouped[key].append(target_id)
    return {key: tuple(targets) for key, targets in grouped.items()}


def _identifier_key(value: str | None) -> str:
    if value is None:
        return ""
    return _TRAILING_PUNCTUATION_RE.sub("", value.strip()).casefold()


def _optional_str(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def _section_paths(
    sections: Sequence[StructuredDocumentSection],
) -> dict[str, tuple[str, ...]]:
    return {section.section_id: section.path for section in sections}


def _add_optional(data: dict[str, object], key: str, value: object | None) -> None:
    if value is not None:
        data[key] = value


__all__ = [
    "ResolvedCrossReferenceCandidate",
    "map_cross_reference_evidence",
    "resolve_cross_reference_candidates",
]
