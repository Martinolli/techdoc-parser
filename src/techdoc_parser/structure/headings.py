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
_TASK_RE = re.compile(r"^TASK\s+\d+(?:\s+\S.+)?$", re.IGNORECASE)
_TASK_SECTION_RE = re.compile(
    r"^TASK\s+SECTION\s+\d+\s+-\s+\S.+$",
    re.IGNORECASE,
)
_APPENDIX_RE = re.compile(r"^APPENDIX\s+[A-Z]\s+\S.+$", re.IGNORECASE)
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
_HEADER_RE = re.compile(r"^MIL-STD-\d+[A-Z]?$", re.IGNORECASE)
_ROMAN_NUMERAL_RE = re.compile(r"^[IVXLCDM]+$", re.IGNORECASE)
_ACRONYM_RE = re.compile(r"^[A-Z][A-Z0-9-]{1,7}$")


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

    if _is_task_or_appendix_heading(normalized):
        return True

    if len(normalized) > 120:
        return False

    if _is_numbered_heading(normalized):
        return _is_conservative_numbered_heading(normalized)

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
    if _is_task_or_appendix_heading(normalized):
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


def extract_heading_blocks_from_text_block(text_block: TextBlock) -> list[HeadingBlock]:
    """Extract whole-block and line-level headings from a TextBlock."""
    source_text = (
        text_block.normalized_text
        if text_block.normalized_text is not None
        else text_block.text
    )
    if source_text is None:
        return []

    headings: list[HeadingBlock] = []
    seen_normalized: set[str] = set()

    whole_block_heading = create_heading_block_from_text_block(text_block)
    if whole_block_heading is not None:
        headings.append(whole_block_heading)
        seen_normalized.add(
            _dedupe_key(whole_block_heading.normalized_text or whole_block_heading.text)
        )

    line_heading_index = 1
    for raw_line in source_text.splitlines():
        line = _normalize_spaces(raw_line.strip())
        if not line or not is_heading_text(line):
            continue

        key = _dedupe_key(line)
        if key in seen_normalized:
            continue

        headings.append(
            HeadingBlock(
                id=f"{text_block.id}-line-heading-{line_heading_index}",
                source=text_block.source,
                text=line,
                normalized_text=line,
                level=detect_heading_level(line),
            )
        )
        seen_normalized.add(key)
        line_heading_index += 1

    return headings


def _is_rejected_candidate(text: str) -> bool:
    upper = _normalize_spaces(text).upper()
    if upper in _FRONT_MATTER_HEADINGS | _SHORT_TITLE_HEADINGS:
        return False
    if _is_task_or_appendix_heading(text):
        return False

    if text.startswith(("•", "-", "*")):
        return True
    if len(text) < 3 and text.upper() not in _FRONT_MATTER_HEADINGS:
        return True
    if "....." in text:
        return True
    if "http://" in text.lower() or "https://" in text.lower() or "@" in text:
        return True
    if "| Page " in text and _FOOTER_RE.search(text) is not None:
        return True
    if _HEADER_RE.fullmatch(text):
        return True
    if text.isdigit():
        return True
    if _ROMAN_NUMERAL_RE.fullmatch(text):
        return True
    if _ACRONYM_RE.fullmatch(text):
        return True
    if len(text) > 120 and not (
        _CHAPTER_RE.fullmatch(text)
        or _ANNEX_RE.fullmatch(text)
        or _is_task_or_appendix_heading(text)
    ):
        return True
    return _looks_like_sentence(text)


def _looks_like_sentence(text: str) -> bool:
    if not _SENTENCE_END_RE.search(text):
        return False
    numbered_heading = _numbered_heading_prefix(text)
    if numbered_heading is not None and _is_mil_std_numbered_prefix(numbered_heading):
        return False
    return not (
        _CHAPTER_RE.fullmatch(text)
        or _ANNEX_RE.fullmatch(text)
        or _is_task_or_appendix_heading(text)
        or text.upper() in _FRONT_MATTER_HEADINGS
    )


def _normalize_spaces(text: str) -> str:
    return " ".join(text.split())


def _is_numbered_heading(text: str) -> bool:
    return _numbered_heading_prefix(text) is not None


def _is_conservative_numbered_heading(text: str) -> bool:
    prefix = _numbered_heading_prefix(text)
    if prefix is None:
        return False

    title = _numbered_heading_title(text, prefix)
    if title is None or not title.strip():
        return False

    if len(title) > 100:
        return False

    if ". " in title.rstrip("."):
        return False

    if title.endswith(".") and not _is_mil_std_numbered_prefix(prefix):
        return False

    return not (
        title.endswith((".", "!", "?"))
        and not (_is_mil_std_numbered_prefix(prefix) and len(title) <= 80)
    )


def _numbered_heading_prefix(text: str) -> str | None:
    single_match = _SINGLE_NUMBERED_HEADING_RE.fullmatch(text)
    if single_match is not None:
        return single_match.group(1)

    nested_match = _NESTED_NUMBERED_HEADING_RE.fullmatch(text)
    if nested_match is not None:
        return nested_match.group(1)

    return None


def _numbered_heading_title(text: str, prefix: str) -> str | None:
    title_start = len(prefix) + 2 if "." not in prefix else len(prefix) + 1

    if title_start >= len(text):
        return None

    return text[title_start:].strip()


def _is_mil_std_numbered_prefix(prefix: str) -> bool:
    first_part = prefix.split(".", maxsplit=1)[0]
    return first_part.isdigit() and int(first_part) >= 100


def _is_task_or_appendix_heading(text: str) -> bool:
    return (
        _TASK_RE.fullmatch(text) is not None
        or _TASK_SECTION_RE.fullmatch(text) is not None
        or _APPENDIX_RE.fullmatch(text) is not None
    )


def _dedupe_key(text: str | None) -> str:
    return _normalize_spaces(text or "").casefold()


def _heading_id_from_text_block_id(text_block_id: str) -> str:
    if "-text-" in text_block_id:
        return text_block_id.replace("-text-", "-heading-", 1)
    return f"{text_block_id}-heading"
