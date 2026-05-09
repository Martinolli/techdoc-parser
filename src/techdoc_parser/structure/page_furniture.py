"""Conservative page-furniture detection helpers."""

from __future__ import annotations

import re

from techdoc_parser.core import Page, TextBlock

_ROMAN_PAGE_NUMERALS = {
    "i",
    "ii",
    "iii",
    "iv",
    "v",
    "vi",
    "vii",
    "viii",
    "ix",
    "x",
    "xi",
    "xii",
}
_GENERIC_FOOTER_RE = re.compile(r"\|\s*Page\s+\d+\b", re.IGNORECASE)
_SOURCE_URL_RE = re.compile(r"source:\s*https?://", re.IGNORECASE)
_DOCUMENT_HEADER_RE = re.compile(
    r"^(?:MIL-STD-\d+[A-Z]?(?:\s+w/CHANGE\s+\d+)?|FTIAS\s+Manual)$",
    re.IGNORECASE,
)
_SECTION_HEADING_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\.\s+\S.+|FOREWORD|CONTENTS|"
    r"SUMMARY OF CHANGE 1 MODIFICATIONS)$",
    re.IGNORECASE,
)


def is_page_number_text(text: str) -> bool:
    """Return whether text is only a page number."""
    normalized = _normalize_spaces(text)
    if not normalized:
        return False
    if normalized.isdigit():
        return True
    return normalized.casefold() in _ROMAN_PAGE_NUMERALS


def is_source_footer_text(text: str) -> bool:
    """Return whether text looks like source/download footer text."""
    normalized = _normalize_spaces(text)
    lower = normalized.casefold()
    if _SOURCE_URL_RE.search(normalized) is not None:
        return True
    if "check the source to verify" in lower and "current version" in lower:
        return True
    return "source:" in lower and "verify" in lower


def is_likely_page_header_text(text: str) -> bool:
    """Return whether text looks like a repeated document header."""
    normalized = _normalize_spaces(text)
    if not normalized:
        return False
    if _SECTION_HEADING_RE.fullmatch(normalized) is not None:
        return False
    return _DOCUMENT_HEADER_RE.fullmatch(normalized) is not None


def classify_text_block_page_furniture(text_block: TextBlock, page: Page) -> None:
    """Set page-furniture flags directly on a TextBlock."""
    text = _text_for_detection(text_block)
    if not text:
        return

    near_top = _is_near_top(text_block, page)
    near_bottom = _is_near_bottom(text_block, page)

    if is_page_number_text(text):
        text_block.is_page_number = True
        text_block.is_page_furniture = True
        if near_top:
            text_block.is_page_header = True
        if near_bottom:
            text_block.is_page_footer = True

    if is_source_footer_text(text) or _is_generic_footer_text(text):
        text_block.is_page_footer = True
        text_block.is_page_furniture = True

    if near_top and is_likely_page_header_text(text):
        text_block.is_page_header = True
        text_block.is_page_furniture = True


def _text_for_detection(text_block: TextBlock) -> str:
    text = (
        text_block.normalized_text
        if text_block.normalized_text is not None
        else text_block.text
    )
    return _normalize_spaces(text or "")


def _is_generic_footer_text(text: str) -> bool:
    if len(text) > 140:
        return False
    return _GENERIC_FOOTER_RE.search(text) is not None


def _is_near_top(text_block: TextBlock, page: Page) -> bool:
    bbox = text_block.source.bbox
    if bbox is None or page.height is None or page.height <= 0:
        return False
    return bbox.y0 <= page.height * 0.12


def _is_near_bottom(text_block: TextBlock, page: Page) -> bool:
    bbox = text_block.source.bbox
    if bbox is None or page.height is None or page.height <= 0:
        return False
    return bbox.y1 >= page.height * 0.88


def _normalize_spaces(text: str) -> str:
    return " ".join(text.split())
