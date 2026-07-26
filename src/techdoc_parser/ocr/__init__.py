"""Controlled OCR adapter APIs.

This package is explicitly opt-in. It does not change the default parser
workflow, StructuredDocument output, validation behavior, or manifest shape.
"""

from techdoc_parser.ocr.artifact import (
    controlled_ocr_result_to_artifact_dict,
    controlled_ocr_result_to_json,
    load_ocr_document_artifact,
    ocr_artifact_to_page_texts,
    validate_ocr_artifact,
)
from techdoc_parser.ocr.manifest import (
    controlled_ocr_manifest_to_json,
    create_controlled_ocr_manifest,
    validate_ocr_manifest,
)
from techdoc_parser.ocr.models import (
    AUTO_WHEN_NATIVE_TEXT_MISSING,
    CONTROLLED_OCR_ADAPTER_NAME,
    CONTROLLED_OCR_ADAPTER_VERSION,
    FAIL,
    OCR_ALL_PAGES,
    OCR_SELECTED_PAGES,
    PASS,
    PASS_WITH_WARNINGS,
    ControlledOcrDocumentResult,
    ControlledOcrPageResult,
    ControlledOcrRequest,
    ControlledOcrWriteResult,
    OcrArtifactValidationResult,
    OcrManifestValidationResult,
    OcrPageProvenance,
)
from techdoc_parser.ocr.tesseract_adapter import (
    TesseractProcessResult,
    run_controlled_tesseract_ocr,
)
from techdoc_parser.ocr.writer import write_controlled_ocr_artifacts

__all__ = [
    "AUTO_WHEN_NATIVE_TEXT_MISSING",
    "CONTROLLED_OCR_ADAPTER_NAME",
    "CONTROLLED_OCR_ADAPTER_VERSION",
    "FAIL",
    "OCR_ALL_PAGES",
    "OCR_SELECTED_PAGES",
    "PASS",
    "PASS_WITH_WARNINGS",
    "ControlledOcrDocumentResult",
    "ControlledOcrPageResult",
    "ControlledOcrRequest",
    "ControlledOcrWriteResult",
    "OcrArtifactValidationResult",
    "OcrManifestValidationResult",
    "OcrPageProvenance",
    "TesseractProcessResult",
    "controlled_ocr_manifest_to_json",
    "controlled_ocr_result_to_artifact_dict",
    "controlled_ocr_result_to_json",
    "create_controlled_ocr_manifest",
    "load_ocr_document_artifact",
    "ocr_artifact_to_page_texts",
    "run_controlled_tesseract_ocr",
    "validate_ocr_artifact",
    "validate_ocr_manifest",
    "write_controlled_ocr_artifacts",
]
