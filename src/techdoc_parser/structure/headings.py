"""Conservative heading detection heuristics."""

from __future__ import annotations

import re

from techdoc_parser.core import HeadingBlock, TextBlock

_FRONT_MATTER_HEADINGS = {
    "ABSTRACT",
    "EXECUTIVE SUMMARY",
    "CONTENTS",
}

_SHORT_TITLE_HEADINGS = {
    "BACKEND",
    "DATABASE",
    "DOCKER",
    "FRONTEND",
    "LIMITATIONS",
    "LOGS",
    "MIGRATIONS",
    "OVERVIEW",
    "PREREQUISITES",
}

_CHAPTER_RE = re.compile(r"^CHAPTER\s+\d+\s+-\s+\S.+$", re.IGNORECASE)
_ANNEX_RE = re.compile(r"^ANNEX\s+[A-Z]\s+-\s+\S.+$", re.IGNORECASE)
_SINGLE_NUMBERED_HEADING_RE = re.compile(r"^(\d+)\.\s+\S.+$")
_NESTED_NUMBERED_HEADING_RE = re.compile(r"^(\d+\.\d+(?:\.\d+)*)\s+\S.+$")
_ANNEX_SUBSECTION_RE = re.compile(r"^[A-Z]\.\d+(?:\.\d+)*\s+\S.+$")
_FOOTER_RE = re.compile(
    r"\|\s*Page\s+\d+\s+"
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},\s+\d{4}",
    re.IGNORECASE,
)
_SENTENCE_END_RE = re.compile(r"[.!?]$")


def is_heading_text(text: str) -> bool:
    """Return whether text looks like a conservative technical-document heading."""
    candidate = text.strip()
    if not candidate:
        return False

    if _is_rejected_candidate(candidate):
        return False

    normalized = _normalize_spaces(candidate)
    upper = normalized.upper()

    if upper in _FRONT_MATTER_HEADINGS | _SHORT_TITLE_HEADINGS:
        return True

    if _CHAPTER_RE.fullmatch(normalized) or _ANNEX_RE.fullmatch(normalized):
        return True

    if len(normalized) > 120:
        return False

    if _is_numbered_heading(normalized):
        return not _looks_like_sentence(normalized)

    if _ANNEX_SUBSECTION_RE.fullmatch(normalized):
        return not _looks_like_sentence(normalized)

    return False


def detect_heading_level(text: str) -> int:
    """Return a best-effort heading level for recognized heading text."""
    normalized = _normalize_spaces(text.strip())
    upper = normalized.upper()

    if upper in _FRONT_MATTER_HEADINGS:
        return 1
    if _CHAPTER_RE.fullmatch(normalized) or _ANNEX_RE.fullmatch(normalized):
        return 1

    numbered_heading = _numbered_heading_prefix(normalized)
    if numbered_heading is not None:
        return numbered_heading.count(".") + 1

    if _ANNEX_SUBSECTION_RE.fullmatch(normalized):
        return 2

    return 2


def create_heading_block_from_text_block(text_block: TextBlock) -> HeadingBlock | None:
    """Create a HeadingBlock from a TextBlock when the text looks like a heading."""
    text = (
        text_block.normalized_text
        if text_block.normalized_text is not None
        else text_block.text
    )
    if text is None or not is_heading_text(text):
        return None

    return HeadingBlock(
        id=_heading_id_from_text_block_id(text_block.id),
        source=text_block.source,
        text=text_block.text,
        normalized_text=text_block.normalized_text,
        level=detect_heading_level(text),
    )


def _is_rejected_candidate(text: str) -> bool:
    if text.startswith(("•", "-", "*")):
        return True
    if "....." in text:
        return True
    if "| Page " in text and _FOOTER_RE.search(text) is not None:
        return True
    if len(text) > 120 and not (
        _CHAPTER_RE.fullmatch(text) or _ANNEX_RE.fullmatch(text)
    ):
        return True
    return _looks_like_sentence(text)


def _looks_like_sentence(text: str) -> bool:
    if not _SENTENCE_END_RE.search(text):
        return False
    return not (
        _CHAPTER_RE.fullmatch(text)
        or _ANNEX_RE.fullmatch(text)
        or text.upper() in _FRONT_MATTER_HEADINGS
    )


def _normalize_spaces(text: str) -> str:
    return " ".join(text.split())


def _is_numbered_heading(text: str) -> bool:
    return _numbered_heading_prefix(text) is not None


def _numbered_heading_prefix(text: str) -> str | None:
    single_match = _SINGLE_NUMBERED_HEADING_RE.fullmatch(text)
    if single_match is not None:
        return single_match.group(1)

    nested_match = _NESTED_NUMBERED_HEADING_RE.fullmatch(text)
    if nested_match is not None:
        return nested_match.group(1)

    return None


def _heading_id_from_text_block_id(text_block_id: str) -> str:
    if "-text-" in text_block_id:
        return text_block_id.replace("-text-", "-heading-", 1)
    return f"{text_block_id}-heading"
