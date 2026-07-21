"""Explicit textual cross-reference detection for structured-document mapping."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from techdoc_parser.core import (
    Block,
    FigureBlock,
    FormulaBlock,
    HeadingBlock,
    TableBlock,
    TableRegionBlock,
    TextBlock,
)
from techdoc_parser.structure.admonitions import detect_admonition_candidates

_INTRO_RE = re.compile(
    r"\b(?:see|refer to|in accordance with|as specified in|as described in|"
    r"according to)\s+",
    re.IGNORECASE,
)
_CONNECTOR_RE = re.compile(r"\s*(?:,|and)\s+", re.IGNORECASE)
_SECTION_TARGET_RE = re.compile(
    r"(?P<label>Section|Clause|Paragraph|Para\.)\s+"
    r"(?P<identifier>\d+(?:\.\d+)*(?:\([A-Za-z0-9]+\))?)(?=$|[\s.;:,])",
    re.IGNORECASE,
)
_ENTITY_TARGET_RE = re.compile(
    r"(?P<label>Table|Figure|Fig\.|Equation|Eq\.)\s+"
    r"(?P<identifier>[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*(?:\([A-Za-z0-9]+\))?)"
    r"(?=$|[\s.;:,])",
    re.IGNORECASE,
)
_APPENDIX_TARGET_RE = re.compile(
    r"(?P<label>Appendix|Annex|Chapter)\s+"
    r"(?P<identifier>[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*)\b",
    re.IGNORECASE,
)
_AMC_GM_TARGET_RE = re.compile(
    r"(?P<identifier>(?:AMC|GM)\d*\s+[A-Za-z0-9.()-]+)(?=$|[\s.;:,])",
    re.IGNORECASE,
)
_DOCUMENT_TARGET_RE = re.compile(
    r"(?P<label>document)\s+" r"(?P<identifier>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)\b",
    re.IGNORECASE,
)
_TRAILING_PUNCTUATION_RE = re.compile(r"[.;:]")


@dataclass(frozen=True)
class CrossReferenceCandidate:
    """One explicit source cross-reference occurrence."""

    source_block_id: str
    raw_reference_text: str
    reference_type: str
    target_identifier: str | None
    resolution_status: str
    resolved_target_id: str | None = None
    page_number: int | None = None


@dataclass(frozen=True)
class _ParsedTarget:
    reference_type: str
    target_identifier: str
    start: int
    end: int
    raw_end: int


def detect_cross_reference_candidates(
    blocks: Sequence[Block],
    *,
    source_block_ids: Sequence[str] | None = None,
) -> tuple[CrossReferenceCandidate, ...]:
    """Return explicit textual cross-reference candidates in source order."""
    block_ids = _source_block_ids(blocks, source_block_ids)
    candidates: list[CrossReferenceCandidate] = []
    for block, block_id in zip(blocks, block_ids, strict=True):
        if not _is_supported_reference_block(block):
            continue
        text = block.text
        if not isinstance(text, str) or not text.strip():
            continue
        if detect_admonition_candidates([block], source_block_ids=[block_id]):
            continue

        for candidate in _detect_block_references(
            text=text,
            block=block,
            source_block_id=block_id,
        ):
            candidates.append(candidate)
    return tuple(candidates)


def _detect_block_references(
    *,
    text: str,
    block: Block,
    source_block_id: str,
) -> tuple[CrossReferenceCandidate, ...]:
    candidates: list[CrossReferenceCandidate] = []
    for intro_match in _INTRO_RE.finditer(text):
        parsed = _parse_target_at(text, intro_match.end())
        if parsed is None:
            continue

        candidates.append(
            _candidate_from_target(
                text=text,
                raw_start=intro_match.start(),
                parsed=parsed,
                block=block,
                source_block_id=source_block_id,
            )
        )
        cursor = parsed.raw_end
        while True:
            connector = _CONNECTOR_RE.match(text, cursor)
            if connector is None:
                break
            next_parsed = _parse_target_at(text, connector.end())
            if next_parsed is None:
                break
            candidates.append(
                _candidate_from_target(
                    text=text,
                    raw_start=next_parsed.start,
                    parsed=next_parsed,
                    block=block,
                    source_block_id=source_block_id,
                )
            )
            cursor = next_parsed.raw_end
    return tuple(candidates)


def _candidate_from_target(
    *,
    text: str,
    raw_start: int,
    parsed: _ParsedTarget,
    block: Block,
    source_block_id: str,
) -> CrossReferenceCandidate:
    return CrossReferenceCandidate(
        source_block_id=source_block_id,
        raw_reference_text=text[raw_start : parsed.raw_end],
        reference_type=parsed.reference_type,
        target_identifier=parsed.target_identifier,
        resolution_status=(
            "external"
            if parsed.reference_type == "external_document"
            else "not_attempted"
        ),
        page_number=block.source.page_number if block.source else None,
    )


def _parse_target_at(text: str, position: int) -> _ParsedTarget | None:
    start = _skip_spaces(text, position)
    for parser in (
        _parse_section_like_target,
        _parse_entity_target,
        _parse_appendix_target,
        _parse_amc_gm_target,
        _parse_document_target,
    ):
        parsed = parser(text, start)
        if parsed is not None:
            return parsed
    return None


def _parse_section_like_target(text: str, start: int) -> _ParsedTarget | None:
    match = _SECTION_TARGET_RE.match(text, start)
    if match is None:
        return None
    label = match.group("label").lower().rstrip(".")
    reference_type = "paragraph" if label in {"paragraph", "para"} else label
    return _target_from_match(
        text=text,
        match=match,
        reference_type=reference_type,
        target_identifier=match.group("identifier"),
    )


def _parse_entity_target(text: str, start: int) -> _ParsedTarget | None:
    match = _ENTITY_TARGET_RE.match(text, start)
    if match is None:
        return None
    label = match.group("label").lower().rstrip(".")
    reference_type = {
        "fig": "figure",
        "eq": "equation",
    }.get(label, label)
    return _target_from_match(
        text=text,
        match=match,
        reference_type=reference_type,
        target_identifier=match.group("identifier"),
    )


def _parse_appendix_target(text: str, start: int) -> _ParsedTarget | None:
    match = _APPENDIX_TARGET_RE.match(text, start)
    if match is None:
        return None
    label = match.group("label").lower()
    return _target_from_match(
        text=text,
        match=match,
        reference_type=label,
        target_identifier=f"{match.group('label')} {match.group('identifier')}",
    )


def _parse_amc_gm_target(text: str, start: int) -> _ParsedTarget | None:
    match = _AMC_GM_TARGET_RE.match(text, start)
    if match is None:
        return None
    return _target_from_match(
        text=text,
        match=match,
        reference_type="clause",
        target_identifier=match.group("identifier"),
    )


def _parse_document_target(text: str, start: int) -> _ParsedTarget | None:
    match = _DOCUMENT_TARGET_RE.match(text, start)
    if match is None:
        return None
    return _target_from_match(
        text=text,
        match=match,
        reference_type="external_document",
        target_identifier=match.group("identifier"),
    )


def _target_from_match(
    *,
    text: str,
    match: re.Match[str],
    reference_type: str,
    target_identifier: str,
) -> _ParsedTarget:
    return _ParsedTarget(
        reference_type=reference_type,
        target_identifier=_target_identifier(target_identifier),
        start=match.start(),
        end=match.end(),
        raw_end=_raw_end(text, match.end()),
    )


def _raw_end(text: str, end: int) -> int:
    if end < len(text) and _TRAILING_PUNCTUATION_RE.fullmatch(text[end]):
        return end + 1
    return end


def _target_identifier(value: str) -> str:
    return value.strip().rstrip(".;:")


def _skip_spaces(text: str, position: int) -> int:
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def _is_supported_reference_block(block: Block) -> bool:
    if isinstance(block, HeadingBlock | TableBlock | TableRegionBlock | FigureBlock):
        return False
    if isinstance(block, TextBlock):
        return False
    if isinstance(block, FormulaBlock):
        return False
    return block.block_type in {"paragraph", "unknown"}


def _source_block_ids(
    blocks: Sequence[Block],
    source_block_ids: Sequence[str] | None,
) -> tuple[str, ...]:
    if source_block_ids is None:
        return tuple(block.id for block in blocks)
    if len(source_block_ids) != len(blocks):
        raise ValueError("source_block_ids must match blocks length")
    return tuple(source_block_ids)


__all__ = [
    "CrossReferenceCandidate",
    "detect_cross_reference_candidates",
]
