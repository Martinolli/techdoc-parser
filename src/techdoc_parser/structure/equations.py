"""Conservative equation evidence detection for structured-document mapping."""

from __future__ import annotations

import re
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

_EXPLICIT_LABEL_RE = re.compile(
    r"^\s*(?P<label>(?:Equation|Eq\.)\s+[A-Za-z0-9][A-Za-z0-9.-]*)\s*[:\-]\s*"
    r"(?P<body>\S.*)$",
    re.IGNORECASE,
)
_TRAILING_LABEL_RE = re.compile(r"\s+(?P<label>\([A-Za-z0-9][A-Za-z0-9.-]*\))\s*$")
_RELATION_OPERATOR_RE = re.compile(r"(?:=|≈|≃|≤|≥|≠|<|>)")
_LETTER_RE = re.compile(r"[A-Za-zΑ-Ωα-ω]")
_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_PUNCTUATED_PROSE_END_RE = re.compile(r"[.!?]\s*$")

_PROSE_PREFIX_RE = re.compile(
    r"^\s*(?:revision|rev|version|issue|date|page|section|chapter|part|p/n|"
    r"part\s+number|document\s+number|doc(?:ument)?\s+id)\b",
    re.IGNORECASE,
)
_PROSE_PHRASE_RE = re.compile(
    r"\b(?:is|are|was|were|shall|should|must|refer|see|note|warning|caution|"
    r"important|section|table|figure|page|revision|version)\b",
    re.IGNORECASE,
)
_PAGE_OF_RE = re.compile(r"^\s*page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class EquationCandidate:
    """Truthful source evidence for a detected equation-like block."""

    source_block_id: str
    raw_text: str
    page_number: int
    label: str | None = None
    normalized_representation: str | None = None


def detect_equation_candidate(
    block: Block,
    *,
    source_block_id: str | None = None,
) -> EquationCandidate | None:
    """Return an equation candidate for explicit or formula evidence only."""
    if not _is_supported_equation_block(block):
        return None

    raw_text = block.text
    if not isinstance(raw_text, str) or not raw_text.strip():
        if isinstance(block, FormulaBlock) and block.latex and block.latex.strip():
            raw_text = block.latex
        else:
            return None

    page_number = block.source.page_number if block.source else None
    if page_number is None:
        return None

    label, expression = _split_equation_label(raw_text)
    if isinstance(block, FormulaBlock):
        expression_text = (
            expression.strip() if expression is not None else raw_text.strip()
        )
        if not expression_text:
            return None
        normalized = _non_empty(block.latex)
        return EquationCandidate(
            source_block_id=source_block_id or _block_id(block),
            raw_text=raw_text,
            page_number=page_number,
            label=label,
            normalized_representation=normalized,
        )

    expression_text = expression if expression is not None else raw_text
    if not _looks_like_equation(expression_text):
        return None

    return EquationCandidate(
        source_block_id=source_block_id or _block_id(block),
        raw_text=raw_text,
        page_number=page_number,
        label=label,
        normalized_representation=None,
    )


def _is_supported_equation_block(block: Block) -> bool:
    if isinstance(block, FormulaBlock):
        return True
    if isinstance(block, HeadingBlock | TableBlock | TableRegionBlock | FigureBlock):
        return False
    if isinstance(block, TextBlock):
        return False
    return block.block_type in {"paragraph", "formula", "equation"}


def _split_equation_label(raw_text: str) -> tuple[str | None, str | None]:
    explicit_match = _EXPLICIT_LABEL_RE.match(raw_text)
    if explicit_match:
        return explicit_match.group("label").strip(), explicit_match.group("body")

    trailing_match = _TRAILING_LABEL_RE.search(raw_text)
    if trailing_match:
        body = raw_text[: trailing_match.start()]
        if _looks_like_equation(body):
            return trailing_match.group("label").strip(), body

    return None, None


def _looks_like_equation(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if "\n" in stripped:
        return False
    if _PAGE_OF_RE.match(stripped):
        return False
    if _PROSE_PREFIX_RE.match(stripped):
        return False
    if not _RELATION_OPERATOR_RE.search(stripped):
        return False
    if not _operator_has_lettered_sides(stripped):
        return False

    words = _WORD_RE.findall(stripped)
    if len(words) > 4:
        return False
    if len(words) > 2 and _PROSE_PHRASE_RE.search(stripped):
        return False
    return not (_PUNCTUATED_PROSE_END_RE.search(stripped) and len(words) > 1)


def _operator_has_lettered_sides(text: str) -> bool:
    for match in _RELATION_OPERATOR_RE.finditer(text):
        left = text[: match.start()]
        right = text[match.end() :]
        if _LETTER_RE.search(left) and _LETTER_RE.search(right):
            return True
    return False


def _block_id(block: Block) -> str:
    if block.id.strip():
        return block.id
    return ""


def _non_empty(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value


__all__ = [
    "EquationCandidate",
    "detect_equation_candidate",
]
