"""Models for the explicit, controlled OCR adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

OCR_ARTIFACT_SCHEMA_NAME = "techdoc-ocr-document"
OCR_ARTIFACT_SCHEMA_VERSION = "0.1.0"
SUPPORTED_OCR_ARTIFACT_SCHEMA_VERSIONS = frozenset({OCR_ARTIFACT_SCHEMA_VERSION})

OCR_MANIFEST_SCHEMA_NAME = "techdoc-ocr-manifest"
OCR_MANIFEST_SCHEMA_VERSION = "0.1.0"
SUPPORTED_OCR_MANIFEST_SCHEMA_VERSIONS = frozenset({OCR_MANIFEST_SCHEMA_VERSION})

CONTROLLED_OCR_ADAPTER_NAME = "controlled-tesseract-cli"
CONTROLLED_OCR_ADAPTER_VERSION = "0.1.0"

OCR_ALL_PAGES = "ocr_all_pages"
OCR_SELECTED_PAGES = "ocr_selected_pages"
AUTO_WHEN_NATIVE_TEXT_MISSING = "auto_when_native_text_missing"
SUPPORTED_OCR_MODES = frozenset(
    {OCR_ALL_PAGES, OCR_SELECTED_PAGES, AUTO_WHEN_NATIVE_TEXT_MISSING}
)

PROCESSED = "processed"
SKIPPED = "skipped"
FAILED = "failed"
TIMED_OUT = "timed_out"
SUPPORTED_PAGE_STATUSES = frozenset({PROCESSED, SKIPPED, FAILED, TIMED_OUT})

PASS = "PASS"
PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
FAIL = "FAIL"
SUPPORTED_OCR_OUTCOMES = frozenset({PASS, PASS_WITH_WARNINGS, FAIL})

REQUESTED_OCR_LANGUAGE_UNAVAILABLE = "REQUESTED_OCR_LANGUAGE_UNAVAILABLE"
GREEK_LANGUAGE_MODEL_UNAVAILABLE = "GREEK_LANGUAGE_MODEL_UNAVAILABLE"
GREEK_FIDELITY_NOT_ESTABLISHED = "GREEK_FIDELITY_NOT_ESTABLISHED"
MATHEMATICAL_FIDELITY_NOT_ESTABLISHED = "MATHEMATICAL_FIDELITY_NOT_ESTABLISHED"
AUTO_OCR_POLICY_UNDEFINED = "AUTO_OCR_POLICY_UNDEFINED"
OCR_ENGINE_NOT_AVAILABLE = "OCR_ENGINE_NOT_AVAILABLE"
OCR_RENDERING_FAILED = "OCR_RENDERING_FAILED"
OCR_PAGE_FAILED = "OCR_PAGE_FAILED"
OCR_PAGE_TIMED_OUT = "OCR_PAGE_TIMED_OUT"
OCR_EMPTY_OUTPUT = "OCR_EMPTY_OUTPUT"
OCR_STDERR_REPORTED = "OCR_STDERR_REPORTED"
SOURCE_DOCUMENT_NOT_FOUND = "SOURCE_DOCUMENT_NOT_FOUND"
INVALID_PAGE_SELECTION = "INVALID_PAGE_SELECTION"

LANGUAGE_PATTERN = re.compile(r"^[A-Za-z0-9_+-]+$")
SUPPORTED_PSM_VALUES = frozenset({3, 4, 6, 11})
SUPPORTED_OEM_VALUES = frozenset({0, 1, 2, 3})


@dataclass(frozen=True)
class ControlledOcrRequest:
    """One explicit controlled OCR request."""

    source_path: Path | str
    document_id: str
    mode: str = OCR_ALL_PAGES
    languages: tuple[str, ...] = ("eng",)
    selected_pages: tuple[int, ...] | None = None
    dpi: int = 300
    psm: int = 6
    oem: int = 1
    timeout_seconds: int = 30
    strict: bool = True
    preserve_rendered_pages: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_path", Path(self.source_path))
        object.__setattr__(
            self,
            "languages",
            tuple(language.strip() for language in self.languages),
        )
        if not self.document_id or "/" in self.document_id or "\\" in self.document_id:
            raise ValueError("document_id must be a non-empty portable identifier.")
        if self.mode not in SUPPORTED_OCR_MODES:
            raise ValueError(f"Unsupported OCR mode: {self.mode}")
        if not self.languages:
            raise ValueError("At least one OCR language is required.")
        invalid_languages = [
            language
            for language in self.languages
            if not language or not LANGUAGE_PATTERN.fullmatch(language)
        ]
        if invalid_languages:
            raise ValueError(f"Invalid OCR language ids: {invalid_languages}")
        if self.mode == OCR_SELECTED_PAGES and not self.selected_pages:
            raise ValueError("ocr_selected_pages requires selected_pages.")
        if self.selected_pages is not None:
            if any(page_number < 1 for page_number in self.selected_pages):
                raise ValueError("selected_pages are one-based positive integers.")
            object.__setattr__(
                self,
                "selected_pages",
                tuple(sorted(dict.fromkeys(self.selected_pages))),
            )
        if not 150 <= self.dpi <= 600:
            raise ValueError("dpi must be between 150 and 600.")
        if self.psm not in SUPPORTED_PSM_VALUES:
            raise ValueError(f"Unsupported Tesseract psm: {self.psm}")
        if self.oem not in SUPPORTED_OEM_VALUES:
            raise ValueError(f"Unsupported Tesseract oem: {self.oem}")
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive.")


@dataclass(frozen=True)
class OcrPageProvenance:
    """Deterministic page-level OCR provenance."""

    page_number: int
    pdf_page_index: int
    source_sha256: str
    source_size_bytes: int
    rendered_image_sha256: str | None
    raw_ocr_sha256: str | None
    normalized_ocr_sha256: str | None
    rendering_engine: str
    rendering_dpi: int
    ocr_engine: str
    ocr_engine_version: str | None
    ocr_languages: tuple[str, ...]
    ocr_mode: str
    psm: int
    oem: int


@dataclass(frozen=True)
class ControlledOcrPageResult:
    """Result for one OCR-attempted page."""

    page_number: int
    pdf_page_index: int
    status: str
    raw_ocr_text: str
    normalized_ocr_text: str
    provenance: OcrPageProvenance
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    stderr_excerpt: str | None = None
    exit_code: int | None = None
    rendered_image_png: bytes | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.status not in SUPPORTED_PAGE_STATUSES:
            raise ValueError(f"Unsupported OCR page status: {self.status}")
        if self.page_number != self.pdf_page_index + 1:
            raise ValueError("page_number must equal pdf_page_index + 1.")


@dataclass(frozen=True)
class ControlledOcrDocumentResult:
    """Complete controlled OCR adapter result."""

    request: ControlledOcrRequest
    outcome: str
    source_filename: str
    source_sha256: str | None
    source_size_bytes: int | None
    observed_page_count: int
    requested_pages: tuple[int, ...]
    processed_pages: tuple[int, ...]
    skipped_pages: tuple[int, ...]
    failed_pages: tuple[int, ...]
    page_results: tuple[ControlledOcrPageResult, ...]
    engine_version: str | None
    available_languages: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    adapter_name: str = CONTROLLED_OCR_ADAPTER_NAME
    adapter_version: str = CONTROLLED_OCR_ADAPTER_VERSION
    default_parser_behavior_changed: bool = False
    structured_document_schema_changed: bool = False
    aviationrag_activity: bool = False
    embeddings_or_vector_store_activity: bool = False

    def __post_init__(self) -> None:
        if self.outcome not in SUPPORTED_OCR_OUTCOMES:
            raise ValueError(f"Unsupported OCR document outcome: {self.outcome}")


@dataclass(frozen=True)
class ControlledOcrWriteResult:
    """Files written by the explicit OCR artifact writer."""

    output_dir: Path
    artifact_path: Path
    manifest_path: Path
    page_artifact_paths: tuple[Path, ...]
    rendered_page_paths: tuple[Path, ...]
    artifact_sha256: str
    manifest_sha256: str


@dataclass(frozen=True)
class OcrArtifactValidationResult:
    """Validation result for a controlled OCR document artifact."""

    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class OcrManifestValidationResult:
    """Validation result for a controlled OCR manifest artifact."""

    valid: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
