"""Explicit-label admonition evidence detection for structured-document mapping."""

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
from techdoc_parser.structure.equations import detect_equation_candidate

_LABEL_RE = re.compile(
    r"^\s*(?P<label>warning|caution|note|important|safety\s+notice)"
    r"(?P<separator>\s*[:\-]?)"
    r"(?P<body>\s+.+|$)",
    re.IGNORECASE,
)
_TYPE_BY_LABEL = {
    "warning": "WARNING",
    "caution": "CAUTION",
    "note": "NOTE",
    "important": "IMPORTANT",
    "safety notice": "SAFETY_NOTICE",
}


@dataclass(frozen=True)
class AdmonitionCandidate:
    """Truthful source evidence for an explicit-label admonition."""

    source_block_ids: tuple[str, ...]
    raw_label: str
    normalized_type: str
    body_text: str
    page_start: int
    page_end: int


def detect_admonition_candidates(
    blocks: Sequence[Block],
    *,
    source_block_ids: Sequence[str] | None = None,
    max_following_body_blocks: int = 2,
) -> tuple[AdmonitionCandidate, ...]:
    """Return explicit-label admonitions from ordered block evidence."""
    block_ids = _source_block_ids(blocks, source_block_ids)
    candidates: list[AdmonitionCandidate] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        parsed = _parse_admonition_label(block)
        if parsed is None:
            index += 1
            continue

        raw_label, normalized_type, same_block_body = parsed
        page_number = _page_number(block)
        if page_number is None:
            index += 1
            continue

        if same_block_body:
            candidates.append(
                AdmonitionCandidate(
                    source_block_ids=(block_ids[index],),
                    raw_label=raw_label,
                    normalized_type=normalized_type,
                    body_text=same_block_body,
                    page_start=page_number,
                    page_end=page_number,
                )
            )
            index += 1
            continue

        body_texts: list[str] = []
        body_ids: list[str] = [block_ids[index]]
        page_end = page_number
        lookahead = index + 1
        body_block_limit = (
            1 if raw_label.endswith((":", "-")) else max_following_body_blocks
        )
        while (
            lookahead < len(blocks)
            and len(body_texts) < body_block_limit
            and _can_follow_admonition_body(
                blocks[lookahead],
                label_page_number=page_number,
            )
        ):
            body = blocks[lookahead]
            body_text = body.text
            if not isinstance(body_text, str):
                break
            body_texts.append(body_text)
            body_ids.append(block_ids[lookahead])
            body_page = _page_number(body)
            if body_page is not None:
                page_end = body_page
            lookahead += 1

        if body_texts:
            candidates.append(
                AdmonitionCandidate(
                    source_block_ids=tuple(body_ids),
                    raw_label=raw_label,
                    normalized_type=normalized_type,
                    body_text="\n".join(body_texts),
                    page_start=page_number,
                    page_end=page_end,
                )
            )
            index = lookahead
            continue

        index += 1

    return tuple(candidates)


def _parse_admonition_label(block: Block) -> tuple[str, str, str | None] | None:
    if not _is_supported_label_block(block):
        return None
    if not isinstance(block.text, str) or not block.text.strip():
        return None

    match = _LABEL_RE.match(block.text)
    if not match:
        return None

    body = match.group("body") or ""
    separator = match.group("separator") or ""
    label = match.group("label")
    raw_label = label + separator
    normalized_key = re.sub(r"\s+", " ", label.strip().lower())
    normalized_type = _TYPE_BY_LABEL[normalized_key]

    body_text = body.strip()
    if separator.strip() == "" and body_text:
        return None
    if not body_text:
        return raw_label.strip(), normalized_type, None
    return raw_label.strip(), normalized_type, body_text


def _can_follow_admonition_body(block: Block, *, label_page_number: int) -> bool:
    if _page_number(block) != label_page_number:
        return False
    if not _is_supported_body_block(block):
        return False
    if _parse_admonition_label(block) is not None:
        return False
    if detect_equation_candidate(block) is not None:
        return False
    return isinstance(block.text, str) and bool(block.text.strip())


def _is_supported_label_block(block: Block) -> bool:
    if isinstance(block, HeadingBlock | TableBlock | TableRegionBlock | FigureBlock):
        return False
    if isinstance(block, TextBlock):
        return False
    if isinstance(block, FormulaBlock):
        return False
    return block.block_type in {"paragraph", "unknown"}


def _is_supported_body_block(block: Block) -> bool:
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


def _page_number(block: Block) -> int | None:
    return block.source.page_number if block.source else None


__all__ = [
    "AdmonitionCandidate",
    "detect_admonition_candidates",
]
