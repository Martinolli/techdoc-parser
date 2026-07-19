"""Versioned external contract models for parser artifacts."""

from techdoc_parser.contracts.structured_document import (
    STRUCTURED_DOCUMENT_SCHEMA_NAME,
    STRUCTURED_DOCUMENT_SCHEMA_VERSION,
    SUPPORTED_STRUCTURED_DOCUMENT_SCHEMA_VERSIONS,
    StructuredBoundingBox,
    StructuredDocument,
    StructuredDocumentBlock,
    StructuredDocumentMetadata,
    StructuredDocumentPage,
    StructuredDocumentSection,
    StructuredSourceSpan,
    build_structured_document,
    is_supported_structured_document_version,
    require_supported_structured_document_version,
    structured_document_to_dict,
    structured_document_to_json,
)

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
