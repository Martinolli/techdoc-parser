"""Internal foundation for the techdoc structured-document contract.

This module defines isolated contract records and deterministic serializers for
the external ``techdoc-structured-document / 0.1.0`` shape. It does not map the
current parser model, write files, inspect the filesystem, or integrate with
the CLI.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from techdoc_parser.version import PARSER_NAME, PARSER_VERSION

STRUCTURED_DOCUMENT_SCHEMA_NAME = "techdoc-structured-document"
STRUCTURED_DOCUMENT_SCHEMA_VERSION = "0.1.0"
SUPPORTED_STRUCTURED_DOCUMENT_SCHEMA_VERSIONS = frozenset(
    {STRUCTURED_DOCUMENT_SCHEMA_VERSION}
)


def is_supported_structured_document_version(schema_version: str) -> bool:
    """Return whether a structured-document schema version is supported."""
    return schema_version in SUPPORTED_STRUCTURED_DOCUMENT_SCHEMA_VERSIONS


def require_supported_structured_document_version(schema_version: str) -> None:
    """Raise if a structured-document schema version is unsupported."""
    if not is_supported_structured_document_version(schema_version):
        raise ValueError(
            f"Unsupported structured-document schema version: {schema_version!r}."
        )


@dataclass(frozen=True)
class StructuredBoundingBox:
    """A source bounding box in page coordinates."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        """Validate coordinate ordering."""
        if self.x1 < self.x0:
            raise ValueError("StructuredBoundingBox x1 must be >= x0.")
        if self.y1 < self.y0:
            raise ValueError("StructuredBoundingBox y1 must be >= y0.")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        return {
            "x0": self.x0,
            "y0": self.y0,
            "x1": self.x1,
            "y1": self.y1,
        }


@dataclass(frozen=True)
class StructuredSourceSpan:
    """Source span fields accepted by the structured-document contract."""

    page_start: int | str | None = None
    page_end: int | str | None = None
    pdf_page_index_start: int | None = None
    pdf_page_index_end: int | None = None
    printed_page_label_start: str | None = None
    printed_page_label_end: str | None = None
    bbox: StructuredBoundingBox | None = None
    source_block_ids: tuple[str, ...] = ()
    extraction_method: str | None = None
    char_start: int | None = None
    char_end: int | None = None

    def __post_init__(self) -> None:
        """Validate span ranges without filling unknown values."""
        _validate_optional_page_ref(self.page_start, "page_start")
        _validate_optional_page_ref(self.page_end, "page_end")
        if (
            isinstance(self.page_start, int)
            and isinstance(self.page_end, int)
            and self.page_start > self.page_end
        ):
            raise ValueError("page_start must not exceed page_end.")
        _validate_optional_non_negative_int(
            self.pdf_page_index_start,
            "pdf_page_index_start",
        )
        _validate_optional_non_negative_int(
            self.pdf_page_index_end,
            "pdf_page_index_end",
        )
        if (
            self.pdf_page_index_start is not None
            and self.pdf_page_index_end is not None
            and self.pdf_page_index_start > self.pdf_page_index_end
        ):
            raise ValueError("pdf_page_index_start must not exceed pdf_page_index_end.")
        _validate_optional_non_negative_int(self.char_start, "char_start")
        _validate_optional_non_negative_int(self.char_end, "char_end")
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_start > self.char_end
        ):
            raise ValueError("char_start must not exceed char_end.")
        for block_id in self.source_block_ids:
            _validate_non_empty_string(block_id, "source_block_ids")
        _validate_optional_non_empty_string(
            self.printed_page_label_start,
            "printed_page_label_start",
        )
        _validate_optional_non_empty_string(
            self.printed_page_label_end,
            "printed_page_label_end",
        )
        _validate_optional_non_empty_string(self.extraction_method, "extraction_method")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        data: dict[str, object] = {}
        _add_optional(data, "page_start", self.page_start)
        _add_optional(data, "page_end", self.page_end)
        _add_optional(data, "pdf_page_index_start", self.pdf_page_index_start)
        _add_optional(data, "pdf_page_index_end", self.pdf_page_index_end)
        _add_optional(
            data,
            "printed_page_label_start",
            self.printed_page_label_start,
        )
        _add_optional(data, "printed_page_label_end", self.printed_page_label_end)
        if self.bbox is not None:
            data["bbox"] = self.bbox.to_dict()
        if self.source_block_ids:
            data["source_block_ids"] = list(self.source_block_ids)
        _add_optional(data, "extraction_method", self.extraction_method)
        _add_optional(data, "char_start", self.char_start)
        _add_optional(data, "char_end", self.char_end)
        return data


@dataclass(frozen=True)
class StructuredDocumentMetadata:
    """Document-level metadata for a structured-document record."""

    document_id: str
    source_filename: str
    document_title: str | None = None
    canonical_title: str | None = None
    page_count: int | None = None
    source_hash: str | None = None
    revision: str | None = None
    issue: str | None = None
    effective_date: str | None = None

    def __post_init__(self) -> None:
        """Validate known metadata values."""
        _validate_non_empty_string(self.document_id, "document_id")
        _validate_non_empty_string(self.source_filename, "source_filename")
        _validate_optional_non_empty_string(self.document_title, "document_title")
        _validate_optional_non_empty_string(self.canonical_title, "canonical_title")
        _validate_optional_non_negative_int(self.page_count, "page_count")
        _validate_optional_non_empty_string(self.source_hash, "source_hash")
        _validate_optional_non_empty_string(self.revision, "revision")
        _validate_optional_non_empty_string(self.issue, "issue")
        _validate_optional_non_empty_string(self.effective_date, "effective_date")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        data: dict[str, object] = {
            "document_id": self.document_id,
            "source_filename": self.source_filename,
        }
        _add_optional(data, "document_title", self.document_title)
        _add_optional(data, "canonical_title", self.canonical_title)
        _add_optional(data, "page_count", self.page_count)
        _add_optional(data, "source_hash", self.source_hash)
        _add_optional(data, "revision", self.revision)
        _add_optional(data, "issue", self.issue)
        _add_optional(data, "effective_date", self.effective_date)
        return data


@dataclass(frozen=True)
class StructuredDocumentPage:
    """One physical page observation."""

    page_id: str
    pdf_page_index: int
    page_number: int
    printed_page_label: str | None = None

    def __post_init__(self) -> None:
        """Validate page identity fields."""
        _validate_non_empty_string(self.page_id, "page_id")
        _validate_non_negative_int(self.pdf_page_index, "pdf_page_index")
        _validate_positive_int(self.page_number, "page_number")
        _validate_optional_non_empty_string(
            self.printed_page_label,
            "printed_page_label",
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        return {
            "page_id": self.page_id,
            "pdf_page_index": self.pdf_page_index,
            "page_number": self.page_number,
            "printed_page_label": self.printed_page_label,
        }


@dataclass(frozen=True)
class StructuredDocumentSection:
    """One logical section node when a section tree is available."""

    section_id: str
    level: int
    title: str
    parent_section_id: str | None = None
    section_number: str | None = None
    path: tuple[str, ...] = ()
    source_span: StructuredSourceSpan | None = None
    raw_heading: str | None = None
    normalized_heading: str | None = None
    clause_identifier: str | None = None

    def __post_init__(self) -> None:
        """Validate section fields."""
        _validate_non_empty_string(self.section_id, "section_id")
        _validate_positive_int(self.level, "level")
        _validate_non_empty_string(self.title, "title")
        _validate_optional_non_empty_string(
            self.parent_section_id,
            "parent_section_id",
        )
        _validate_optional_non_empty_string(self.section_number, "section_number")
        _validate_optional_non_empty_string(self.raw_heading, "raw_heading")
        _validate_optional_non_empty_string(
            self.normalized_heading,
            "normalized_heading",
        )
        _validate_optional_non_empty_string(
            self.clause_identifier,
            "clause_identifier",
        )
        for path_item in self.path:
            _validate_non_empty_string(path_item, "path")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        data: dict[str, object] = {
            "section_id": self.section_id,
            "level": self.level,
            "title": self.title,
        }
        _add_optional(data, "parent_section_id", self.parent_section_id)
        _add_optional(data, "section_number", self.section_number)
        _add_optional(data, "raw_heading", self.raw_heading)
        _add_optional(data, "normalized_heading", self.normalized_heading)
        _add_optional(data, "clause_identifier", self.clause_identifier)
        if self.path:
            data["path"] = list(self.path)
        if self.source_span is not None:
            data["source_span"] = self.source_span.to_dict()
        return data


@dataclass(frozen=True)
class StructuredDocumentBlock:
    """One ordered content block in a structured-document record."""

    block_id: str
    block_type: str
    text: str
    source_span: StructuredSourceSpan
    document_block_index: int | None = None
    page_block_index: int | None = None
    page_id: str | None = None
    page_number: int | None = None
    pdf_page_index: int | None = None
    section_id: str | None = None
    normalized_text: str | None = None
    bbox: StructuredBoundingBox | None = None

    def __post_init__(self) -> None:
        """Validate block identity, content, and index fields."""
        _validate_non_empty_string(self.block_id, "block_id")
        _validate_non_empty_string(self.block_type, "block_type")
        _validate_non_empty_string(self.text, "text")
        _validate_optional_non_negative_int(
            self.document_block_index,
            "document_block_index",
        )
        _validate_optional_non_negative_int(self.page_block_index, "page_block_index")
        _validate_optional_non_empty_string(self.page_id, "page_id")
        _validate_optional_positive_int(self.page_number, "page_number")
        _validate_optional_non_negative_int(self.pdf_page_index, "pdf_page_index")
        _validate_optional_non_empty_string(self.section_id, "section_id")
        _validate_optional_non_empty_string(self.normalized_text, "normalized_text")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        data: dict[str, object] = {
            "block_id": self.block_id,
            "block_type": self.block_type,
            "text": self.text,
        }
        _add_optional(data, "document_block_index", self.document_block_index)
        _add_optional(data, "page_block_index", self.page_block_index)
        _add_optional(data, "page_id", self.page_id)
        _add_optional(data, "page_number", self.page_number)
        _add_optional(data, "pdf_page_index", self.pdf_page_index)
        _add_optional(data, "section_id", self.section_id)
        _add_optional(data, "normalized_text", self.normalized_text)
        data["source_span"] = self.source_span.to_dict()
        if self.bbox is not None:
            data["bbox"] = self.bbox.to_dict()
        return data


@dataclass(frozen=True)
class StructuredDocument:
    """Root structured-document contract object."""

    document: StructuredDocumentMetadata
    pages: tuple[StructuredDocumentPage, ...]
    sections: tuple[StructuredDocumentSection, ...] = ()
    blocks: tuple[StructuredDocumentBlock, ...] = ()
    tables: tuple[dict[str, object], ...] = ()
    figures: tuple[dict[str, object], ...] = ()
    equations: tuple[dict[str, object], ...] = ()
    admonitions: tuple[dict[str, object], ...] = ()
    cross_references: tuple[dict[str, object], ...] = ()
    schema_name: str = STRUCTURED_DOCUMENT_SCHEMA_NAME
    schema_version: str = STRUCTURED_DOCUMENT_SCHEMA_VERSION
    parser_name: str = PARSER_NAME
    parser_version: str = PARSER_VERSION

    def __post_init__(self) -> None:
        """Validate root identity and preserve caller-provided collections."""
        _validate_non_empty_string(self.schema_name, "schema_name")
        if self.schema_name != STRUCTURED_DOCUMENT_SCHEMA_NAME:
            raise ValueError(
                f"Unsupported structured-document schema name: {self.schema_name!r}."
            )
        require_supported_structured_document_version(self.schema_version)
        _validate_non_empty_string(self.parser_name, "parser_name")
        _validate_non_empty_string(self.parser_version, "parser_version")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        return structured_document_to_dict(self)

    def to_json(self, indent: int | None = 2) -> str:
        """Return deterministic structured-document JSON."""
        return structured_document_to_json(self, indent=indent)


def build_structured_document(
    *,
    document: StructuredDocumentMetadata,
    pages: Sequence[StructuredDocumentPage],
    sections: Sequence[StructuredDocumentSection] = (),
    blocks: Sequence[StructuredDocumentBlock] = (),
    tables: Sequence[Mapping[str, object]] = (),
    figures: Sequence[Mapping[str, object]] = (),
    equations: Sequence[Mapping[str, object]] = (),
    admonitions: Sequence[Mapping[str, object]] = (),
    cross_references: Sequence[Mapping[str, object]] = (),
    schema_version: str = STRUCTURED_DOCUMENT_SCHEMA_VERSION,
    parser_name: str = PARSER_NAME,
    parser_version: str = PARSER_VERSION,
) -> StructuredDocument:
    """Build a structured-document root while preserving caller order."""
    require_supported_structured_document_version(schema_version)
    return StructuredDocument(
        document=document,
        pages=tuple(pages),
        sections=tuple(sections),
        blocks=tuple(blocks),
        tables=_copy_mapping_sequence(tables),
        figures=_copy_mapping_sequence(figures),
        equations=_copy_mapping_sequence(equations),
        admonitions=_copy_mapping_sequence(admonitions),
        cross_references=_copy_mapping_sequence(cross_references),
        schema_version=schema_version,
        parser_name=parser_name,
        parser_version=parser_version,
    )


def structured_document_to_dict(
    structured_document: StructuredDocument,
) -> dict[str, object]:
    """Return a deterministic JSON-serializable structured-document object."""
    return {
        "schema_name": structured_document.schema_name,
        "schema_version": structured_document.schema_version,
        "parser_name": structured_document.parser_name,
        "parser_version": structured_document.parser_version,
        "document": structured_document.document.to_dict(),
        "pages": [page.to_dict() for page in structured_document.pages],
        "sections": [section.to_dict() for section in structured_document.sections],
        "blocks": [block.to_dict() for block in structured_document.blocks],
        "tables": [dict(table) for table in structured_document.tables],
        "figures": [dict(figure) for figure in structured_document.figures],
        "equations": [dict(equation) for equation in structured_document.equations],
        "admonitions": [
            dict(admonition) for admonition in structured_document.admonitions
        ],
        "cross_references": [
            dict(reference) for reference in structured_document.cross_references
        ],
    }


def structured_document_to_json(
    structured_document: StructuredDocument,
    *,
    indent: int | None = 2,
) -> str:
    """Return deterministic structured-document JSON without writing files."""
    return json.dumps(
        structured_document_to_dict(structured_document),
        ensure_ascii=False,
        indent=indent,
    )


def _copy_mapping_sequence(
    values: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    return tuple(dict(value) for value in values)


def _add_optional(data: dict[str, object], key: str, value: object | None) -> None:
    if value is not None:
        data[key] = value


def _validate_non_empty_string(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")


def _validate_optional_non_empty_string(value: str | None, field_name: str) -> None:
    if value is not None:
        _validate_non_empty_string(value, field_name)


def _validate_non_negative_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")


def _validate_optional_non_negative_int(
    value: int | None,
    field_name: str,
) -> None:
    if value is not None:
        _validate_non_negative_int(value, field_name)


def _validate_positive_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer.")


def _validate_optional_positive_int(value: int | None, field_name: str) -> None:
    if value is not None:
        _validate_positive_int(value, field_name)


def _validate_optional_page_ref(value: int | str | None, field_name: str) -> None:
    if value is None:
        return
    if isinstance(value, str):
        _validate_non_empty_string(value, field_name)
        return
    _validate_positive_int(value, field_name)


__all__ = [
    "STRUCTURED_DOCUMENT_SCHEMA_NAME",
    "STRUCTURED_DOCUMENT_SCHEMA_VERSION",
    "SUPPORTED_STRUCTURED_DOCUMENT_SCHEMA_VERSIONS",
    "StructuredBoundingBox",
    "StructuredDocument",
    "StructuredDocumentBlock",
    "StructuredDocumentMetadata",
    "StructuredDocumentPage",
    "StructuredDocumentSection",
    "StructuredSourceSpan",
    "build_structured_document",
    "is_supported_structured_document_version",
    "require_supported_structured_document_version",
    "structured_document_to_dict",
    "structured_document_to_json",
]
