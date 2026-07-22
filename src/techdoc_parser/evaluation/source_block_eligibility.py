"""Shared source-block eligibility policy for evaluation diagnostics.

This module is evaluation-only. It classifies whether a parser block should be
required in chunk source references, without changing parser or chunker output.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from techdoc_parser.chunking.semantic import block_to_chunk_text
from techdoc_parser.core import Block, Chunk, HeadingBlock, TextBlock

REQUIRED_DIRECT_CHUNK = "required_direct_chunk"
SATISFIED_BY_ENTITY_CHUNK = "satisfied_by_entity_chunk"
EXCLUDED_HEADING = "excluded_heading"
EXCLUDED_BLANK = "excluded_blank"
EXCLUDED_METADATA = "excluded_metadata"
EXCLUDED_NON_SEMANTIC = "excluded_non_semantic"
UNSUPPORTED = "unsupported"

ELIGIBILITY_STATES = (
    REQUIRED_DIRECT_CHUNK,
    SATISFIED_BY_ENTITY_CHUNK,
    EXCLUDED_HEADING,
    EXCLUDED_BLANK,
    EXCLUDED_METADATA,
    EXCLUDED_NON_SEMANTIC,
    UNSUPPORTED,
)


@dataclass(frozen=True)
class SourceBlockEligibility:
    """Evaluation-only eligibility result for one parser source block."""

    block_id: str | None
    state: str
    reason_code: str
    covered_by_chunk_ids: tuple[str, ...] = ()
    covered_by_entity_ids: tuple[str, ...] = ()
    source_text_block_ids: tuple[str, ...] = ()

    @property
    def is_required(self) -> bool:
        """Return whether this block participates in coverage denominators."""
        return self.state in {REQUIRED_DIRECT_CHUNK, SATISFIED_BY_ENTITY_CHUNK}

    @property
    def is_covered(self) -> bool:
        """Return whether the block is represented by selected chunk evidence."""
        return bool(self.covered_by_chunk_ids)


@dataclass(frozen=True)
class SourceBlockEligibilityPolicy:
    """Configuration for evaluation-only source-block eligibility."""

    require_heading_chunks: bool = False
    allow_entity_source_text_replacement: bool = True


def classify_source_block_chunk_eligibility(
    block: Block,
    chunks: Sequence[Chunk],
    *,
    entities: Mapping[str, object] | None = None,
    policy: SourceBlockEligibilityPolicy | None = None,
) -> SourceBlockEligibility:
    """Classify source-block chunk eligibility under the shared policy."""
    active_policy = policy or SourceBlockEligibilityPolicy()
    block_id = block.id or None
    if block_id is None:
        return SourceBlockEligibility(
            block_id=None,
            state=UNSUPPORTED,
            reason_code="missing_block_id",
        )
    if isinstance(block, TextBlock) and block.is_page_furniture:
        return SourceBlockEligibility(
            block_id=block_id,
            state=EXCLUDED_METADATA,
            reason_code="page_furniture",
        )
    if isinstance(block, HeadingBlock) and not active_policy.require_heading_chunks:
        return SourceBlockEligibility(
            block_id=block_id,
            state=EXCLUDED_HEADING,
            reason_code="heading_context_not_direct_chunk_requirement",
        )
    raw_text = _block_text(block)
    if not raw_text.strip():
        return SourceBlockEligibility(
            block_id=block_id,
            state=EXCLUDED_BLANK,
            reason_code="blank_block_text",
        )
    if not block_to_chunk_text(block):
        return SourceBlockEligibility(
            block_id=block_id,
            state=EXCLUDED_NON_SEMANTIC,
            reason_code="non_emitting_chunk_text",
        )

    source_text_block_ids = _source_text_block_ids(block)
    direct_chunk_ids = _chunk_ids_covering_block(block_id, chunks)
    entity_ids = _entity_ids_for_source_block(entities or {}, block_id)
    entity_chunk_ids: tuple[str, ...] = ()
    if active_policy.allow_entity_source_text_replacement and source_text_block_ids:
        entity_chunk_ids = _chunk_ids_covering_any_source_text(
            source_text_block_ids,
            chunks,
        )

    if direct_chunk_ids:
        if _is_entity_derived(block):
            return SourceBlockEligibility(
                block_id=block_id,
                state=SATISFIED_BY_ENTITY_CHUNK,
                reason_code="entity_block_directly_chunked",
                covered_by_chunk_ids=direct_chunk_ids,
                covered_by_entity_ids=entity_ids,
                source_text_block_ids=source_text_block_ids,
            )
        return SourceBlockEligibility(
            block_id=block_id,
            state=REQUIRED_DIRECT_CHUNK,
            reason_code="direct_chunk_reference_present",
            covered_by_chunk_ids=direct_chunk_ids,
            covered_by_entity_ids=entity_ids,
            source_text_block_ids=source_text_block_ids,
        )

    if entity_chunk_ids:
        return SourceBlockEligibility(
            block_id=block_id,
            state=SATISFIED_BY_ENTITY_CHUNK,
            reason_code="source_text_represented_by_entity_chunk",
            covered_by_chunk_ids=entity_chunk_ids,
            covered_by_entity_ids=entity_ids,
            source_text_block_ids=source_text_block_ids,
        )

    return SourceBlockEligibility(
        block_id=block_id,
        state=REQUIRED_DIRECT_CHUNK,
        reason_code="direct_chunk_reference_required",
        covered_by_entity_ids=entity_ids,
        source_text_block_ids=source_text_block_ids,
    )


def summarize_source_block_eligibility(
    eligibilities: Sequence[SourceBlockEligibility],
) -> dict[str, int]:
    """Return deterministic state counts for sanitized reports."""
    counts = Counter(eligibility.state for eligibility in eligibilities)
    return {state: counts[state] for state in ELIGIBILITY_STATES if counts[state]}


def missing_required_source_block_ids(
    eligibilities: Sequence[SourceBlockEligibility],
) -> tuple[str, ...]:
    """Return required block IDs not represented by selected chunks."""
    return tuple(
        sorted(
            eligibility.block_id
            for eligibility in eligibilities
            if eligibility.block_id
            and eligibility.state == REQUIRED_DIRECT_CHUNK
            and not eligibility.is_covered
        )
    )


def eligible_source_block_ids(
    eligibilities: Sequence[SourceBlockEligibility],
) -> tuple[str, ...]:
    """Return required/satisfied block IDs in deterministic order."""
    return tuple(
        eligibility.block_id
        for eligibility in eligibilities
        if eligibility.block_id and eligibility.is_required
    )


def covered_source_block_ids(
    eligibilities: Sequence[SourceBlockEligibility],
) -> tuple[str, ...]:
    """Return covered required/satisfied block IDs in deterministic order."""
    return tuple(
        eligibility.block_id
        for eligibility in eligibilities
        if eligibility.block_id and eligibility.is_required and eligibility.is_covered
    )


def _chunk_ids_covering_block(
    block_id: str,
    chunks: Sequence[Chunk],
) -> tuple[str, ...]:
    return tuple(
        chunk.id
        for chunk in chunks
        if block_id in chunk.source_block_ids or block_id in chunk.source_text_block_ids
    )


def _chunk_ids_covering_any_source_text(
    source_text_block_ids: Sequence[str],
    chunks: Sequence[Chunk],
) -> tuple[str, ...]:
    source_ids = set(source_text_block_ids)
    return tuple(
        chunk.id
        for chunk in chunks
        if source_ids.intersection(chunk.source_text_block_ids)
        or source_ids.intersection(chunk.source_block_ids)
    )


def _entity_ids_for_source_block(
    entities: Mapping[str, object],
    block_id: str,
) -> tuple[str, ...]:
    entity_ids: list[str] = []
    for entity in _iter_entities(entities):
        source_ids = _string_sequence(entity.get("source_block_ids"))
        source_ids += _string_sequence(entity.get("source_text_block_ids"))
        if block_id not in set(source_ids):
            continue
        entity_id = _entity_id(entity)
        if entity_id:
            entity_ids.append(entity_id)
    return tuple(sorted(dict.fromkeys(entity_ids)))


def _iter_entities(entities: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    result: list[Mapping[str, object]] = []
    for value in entities.values():
        if isinstance(value, Mapping):
            result.append(value)
        elif isinstance(value, Sequence) and not isinstance(value, str):
            result.extend(item for item in value if isinstance(item, Mapping))
    return tuple(result)


def _entity_id(entity: Mapping[str, object]) -> str | None:
    for key in (
        "table_id",
        "figure_id",
        "equation_id",
        "admonition_id",
        "cross_reference_id",
        "entity_id",
        "id",
    ):
        value = entity.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _source_text_block_ids(block: Block) -> tuple[str, ...]:
    ids: list[str] = []
    for attr in (
        "source_text_block_ids",
        "source_table_block_ids",
        "source_paragraph_block_ids",
    ):
        value = getattr(block, attr, None)
        ids.extend(_string_sequence(value))
    return tuple(dict.fromkeys(ids))


def _string_sequence(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _block_text(block: Block) -> str:
    text = block.normalized_text or block.text
    if text is None:
        text = getattr(block, "caption", None)
    if text is None:
        text = getattr(block, "latex", None)
    return str(text or "")


def _is_entity_derived(block: Block) -> bool:
    return block.block_type in {
        "table",
        "table_region",
        "figure",
        "formula",
        "equation",
        "admonition",
        "cross_reference",
    }


__all__ = [
    "ELIGIBILITY_STATES",
    "EXCLUDED_BLANK",
    "EXCLUDED_HEADING",
    "EXCLUDED_METADATA",
    "EXCLUDED_NON_SEMANTIC",
    "REQUIRED_DIRECT_CHUNK",
    "SATISFIED_BY_ENTITY_CHUNK",
    "UNSUPPORTED",
    "SourceBlockEligibility",
    "SourceBlockEligibilityPolicy",
    "classify_source_block_chunk_eligibility",
    "covered_source_block_ids",
    "eligible_source_block_ids",
    "missing_required_source_block_ids",
    "summarize_source_block_eligibility",
]
