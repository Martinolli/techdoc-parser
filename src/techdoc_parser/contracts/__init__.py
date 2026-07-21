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
from techdoc_parser.contracts.structured_document_confidence import (
    CONFIDENCE_FIELDS,
    add_confidence_if_available,
    map_ocr_confidence,
    map_source_extraction_confidence,
    map_structure_confidence,
    normalize_confidence,
)
from techdoc_parser.contracts.structured_document_entities import (
    StructuredEntityEvidence,
    map_figure_caption_evidence,
    map_table_evidence,
)
from techdoc_parser.contracts.structured_document_equations_admonitions import (
    map_admonition_evidence,
    map_equation_evidence,
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
from techdoc_parser.contracts.structured_document_references import (
    ResolvedCrossReferenceCandidate,
    map_cross_reference_evidence,
    resolve_cross_reference_candidates,
)

__all__ = [
    "STRUCTURED_DOCUMENT_SCHEMA_NAME",
    "STRUCTURED_DOCUMENT_SCHEMA_VERSION",
    "SUPPORTED_STRUCTURED_DOCUMENT_SCHEMA_VERSIONS",
    "CONFIDENCE_FIELDS",
    "ResolvedCrossReferenceCandidate",
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
    "add_confidence_if_available",
    "build_structured_document",
    "enrich_structured_document_hierarchy",
    "is_supported_structured_document_version",
    "map_block_type_to_content_type",
    "map_admonition_evidence",
    "map_document_to_structured_document",
    "map_document_with_options",
    "map_equation_evidence",
    "map_figure_caption_evidence",
    "map_cross_reference_evidence",
    "map_ocr_confidence",
    "map_source_extraction_confidence",
    "map_structure_confidence",
    "normalize_confidence",
    "map_table_evidence",
    "require_supported_structured_document_version",
    "resolve_cross_reference_candidates",
    "structured_document_to_dict",
    "structured_document_to_json",
]
