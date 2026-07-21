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
from techdoc_parser.contracts.structured_document_entities import (
    StructuredEntityEvidence,
    map_figure_caption_evidence,
    map_table_evidence,
)
from techdoc_parser.contracts.structured_document_hierarchy import (
    SectionHierarchyResult,
    StructuredHeadingEvidence,
    enrich_structured_document_hierarchy,
)
from techdoc_parser.contracts.structured_document_mapper import (
    StructuredDocumentMappingOptions,
    map_block_type_to_content_type,
    map_document_to_structured_document,
    map_document_with_options,
)

__all__ = [
    "STRUCTURED_DOCUMENT_SCHEMA_NAME",
    "STRUCTURED_DOCUMENT_SCHEMA_VERSION",
    "SUPPORTED_STRUCTURED_DOCUMENT_SCHEMA_VERSIONS",
    "StructuredBoundingBox",
    "StructuredDocument",
    "StructuredDocumentMappingOptions",
    "StructuredDocumentBlock",
    "StructuredDocumentMetadata",
    "StructuredDocumentPage",
    "StructuredDocumentSection",
    "StructuredEntityEvidence",
    "StructuredHeadingEvidence",
    "StructuredSourceSpan",
    "SectionHierarchyResult",
    "build_structured_document",
    "enrich_structured_document_hierarchy",
    "is_supported_structured_document_version",
    "map_block_type_to_content_type",
    "map_document_to_structured_document",
    "map_document_with_options",
    "map_figure_caption_evidence",
    "map_table_evidence",
    "require_supported_structured_document_version",
    "structured_document_to_dict",
    "structured_document_to_json",
]
