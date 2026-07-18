"""Validation report helpers for parsed documents and semantic chunks."""

from __future__ import annotations

from dataclasses import dataclass, field

from techdoc_parser.core import Chunk, Document, Page, TableBlock, TableRegionBlock
from techdoc_parser.structure import get_semantic_blocks_for_page
from techdoc_parser.structure.semantic import is_semantic_furniture_text

VALIDATION_INFO = "info"
VALIDATION_WARNING = "warning"
VALIDATION_ERROR = "error"
VERY_SHORT_CHUNK_CHAR_THRESHOLD = 30
VERY_LONG_CHUNK_CHAR_THRESHOLD = 4000
MANY_TABLE_CANDIDATES_THRESHOLD = 10


@dataclass
class ValidationIssue:
    """A single parsing or chunking quality issue."""

    code: str
    severity: str
    message: str
    page_number: int | None = None
    block_id: str | None = None
    chunk_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "page_number": self.page_number,
            "block_id": self.block_id,
            "chunk_id": self.chunk_id,
        }


@dataclass
class ValidationReport:
    """A parsing and chunking quality report."""

    document_id: str | None
    source_path: str | None
    issues: list[ValidationIssue] = field(default_factory=list)
    summary: dict[str, int | str | bool] = field(default_factory=dict)
    issue_count: int = field(init=False)
    warning_count: int = field(init=False)
    error_count: int = field(init=False)
    info_count: int = field(init=False)

    def __post_init__(self) -> None:
        """Calculate issue counts and report status flags."""
        self.issue_count = len(self.issues)
        self.warning_count = _count_issues_by_severity(
            self.issues,
            VALIDATION_WARNING,
        )
        self.error_count = _count_issues_by_severity(self.issues, VALIDATION_ERROR)
        self.info_count = _count_issues_by_severity(self.issues, VALIDATION_INFO)
        self.summary["has_errors"] = self.error_count > 0
        self.summary["has_warnings"] = self.warning_count > 0

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        return {
            "document_id": self.document_id,
            "source_path": self.source_path,
            "issue_count": self.issue_count,
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "info_count": self.info_count,
            "issues": [issue.to_dict() for issue in self.issues],
            "summary": dict(self.summary),
        }


@dataclass
class ValidationDecision:
    """A simple downstream ingestion-readiness decision."""

    status: str
    can_ingest: bool
    reason: str
    issue_count: int
    error_count: int
    warning_count: int
    info_count: int
    review_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable dictionary."""
        return {
            "status": self.status,
            "can_ingest": self.can_ingest,
            "reason": self.reason,
            "issue_count": self.issue_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "review_reasons": self.review_reasons,
        }


def decide_ingestion_status(report: ValidationReport) -> ValidationDecision:
    """Convert a validation report into an ingestion-readiness decision."""
    if report.error_count > 0:
        return ValidationDecision(
            status="fail",
            can_ingest=False,
            reason="Validation errors are present; do not ingest automatically.",
            issue_count=report.issue_count,
            error_count=report.error_count,
            warning_count=report.warning_count,
            info_count=report.info_count,
            review_reasons=_issue_reasons(report.issues, VALIDATION_ERROR),
        )

    if report.warning_count > 0:
        return ValidationDecision(
            status="review",
            can_ingest=False,
            reason="Validation warnings require review before automated ingestion.",
            issue_count=report.issue_count,
            error_count=report.error_count,
            warning_count=report.warning_count,
            info_count=report.info_count,
            review_reasons=_issue_reasons(report.issues, VALIDATION_WARNING),
        )

    return ValidationDecision(
        status="pass",
        can_ingest=True,
        reason="No blocking validation findings are present.",
        issue_count=report.issue_count,
        error_count=report.error_count,
        warning_count=report.warning_count,
        info_count=report.info_count,
        review_reasons=[],
    )


def validate_document(document: Document) -> ValidationReport:
    """Validate parsed document structure and return a quality report."""
    issues: list[ValidationIssue] = []
    pages_requiring_ocr = 0
    pages_without_semantic_blocks = 0
    pages_furniture_only = 0

    if not document.pages:
        issues.append(
            ValidationIssue(
                code="document.empty",
                severity=VALIDATION_ERROR,
                message="Document contains no pages.",
            )
        )

    for page in document.pages:
        if page.requires_ocr:
            pages_requiring_ocr += 1
            issues.append(
                ValidationIssue(
                    code="page.requires_ocr",
                    severity=VALIDATION_WARNING,
                    message="Page requires OCR before reliable text extraction.",
                    page_number=page.page_number,
                )
            )

        if not page.text_blocks:
            issues.append(
                ValidationIssue(
                    code="page.no_text_blocks",
                    severity=VALIDATION_WARNING,
                    message="Page has no extracted text blocks.",
                    page_number=page.page_number,
                )
            )

        semantic_blocks = get_semantic_blocks_for_page(page)
        if page.has_native_text and not page.requires_ocr and not semantic_blocks:
            if is_furniture_only_page(page):
                pages_furniture_only += 1
                issues.append(
                    ValidationIssue(
                        code="page.furniture_only",
                        severity=VALIDATION_INFO,
                        message=(
                            "Page contains only page furniture or intentionally "
                            "blank content."
                        ),
                        page_number=page.page_number,
                    )
                )
            else:
                pages_without_semantic_blocks += 1
                issues.append(
                    ValidationIssue(
                        code="page.no_semantic_blocks",
                        severity=VALIDATION_WARNING,
                        message="Page has native text but no semantic blocks.",
                        page_number=page.page_number,
                    )
                )

        table_blocks = [block for block in page.blocks if isinstance(block, TableBlock)]
        table_regions = [
            block for block in page.blocks if isinstance(block, TableRegionBlock)
        ]
        if len(table_blocks) > MANY_TABLE_CANDIDATES_THRESHOLD and not table_regions:
            issues.append(
                ValidationIssue(
                    code="page.many_table_candidates",
                    severity=VALIDATION_WARNING,
                    message=(
                        "Page has many table candidates and no grouped table region."
                    ),
                    page_number=page.page_number,
                )
            )

        if len(table_regions) > 1:
            issues.append(
                ValidationIssue(
                    code="page.multiple_table_regions",
                    severity=VALIDATION_INFO,
                    message="Page has multiple table region candidates.",
                    page_number=page.page_number,
                )
            )

    return ValidationReport(
        document_id=document.id,
        source_path=document.source_path,
        issues=issues,
        summary={
            "page_count": len(document.pages),
            "chunk_count": 0,
            "pages_requiring_ocr": pages_requiring_ocr,
            "pages_without_semantic_blocks": pages_without_semantic_blocks,
            "pages_furniture_only": pages_furniture_only,
            "chunks_empty_text": 0,
            "chunks_very_short": 0,
            "chunks_very_long": 0,
            "chunks_missing_sources": 0,
        },
    )


def validate_chunks(chunks: list[Chunk]) -> ValidationReport:
    """Validate semantic chunks and return a quality report."""
    issues: list[ValidationIssue] = []
    chunks_empty_text = 0
    chunks_very_short = 0
    chunks_very_long = 0
    chunks_missing_sources = 0

    if not chunks:
        issues.append(
            ValidationIssue(
                code="chunks.empty",
                severity=VALIDATION_ERROR,
                message="No chunks were produced.",
            )
        )

    for chunk in chunks:
        stripped_text = chunk.text.strip()
        non_whitespace_length = len("".join(chunk.text.split()))

        if not stripped_text:
            chunks_empty_text += 1
            issues.append(
                ValidationIssue(
                    code="chunk.empty_text",
                    severity=VALIDATION_ERROR,
                    message="Chunk text is empty.",
                    chunk_id=chunk.id,
                )
            )
        elif (
            non_whitespace_length < VERY_SHORT_CHUNK_CHAR_THRESHOLD
            and "section_title" not in chunk.metadata
        ):
            chunks_very_short += 1
            issues.append(
                ValidationIssue(
                    code="chunk.very_short",
                    severity=VALIDATION_WARNING,
                    message="Chunk text is very short.",
                    chunk_id=chunk.id,
                )
            )

        if len(chunk.text) > VERY_LONG_CHUNK_CHAR_THRESHOLD:
            chunks_very_long += 1
            issues.append(
                ValidationIssue(
                    code="chunk.very_long",
                    severity=VALIDATION_WARNING,
                    message="Chunk text is very long.",
                    chunk_id=chunk.id,
                )
            )

        missing_source_page_numbers = not chunk.source_page_numbers
        missing_source_block_ids = not chunk.source_block_ids
        if missing_source_page_numbers:
            issues.append(
                ValidationIssue(
                    code="chunk.missing_source_pages",
                    severity=VALIDATION_WARNING,
                    message="Chunk has no source page numbers.",
                    chunk_id=chunk.id,
                )
            )
        if missing_source_block_ids:
            issues.append(
                ValidationIssue(
                    code="chunk.missing_source_blocks",
                    severity=VALIDATION_WARNING,
                    message="Chunk has no source block ids.",
                    chunk_id=chunk.id,
                )
            )
        if missing_source_page_numbers or missing_source_block_ids:
            chunks_missing_sources += 1

        if not chunk.source_text_block_ids:
            issues.append(
                ValidationIssue(
                    code="chunk.missing_source_text_blocks",
                    severity=VALIDATION_INFO,
                    message="Chunk has no source text block ids.",
                    chunk_id=chunk.id,
                )
            )

        if _has_possible_furniture_leak(chunk.text):
            issues.append(
                ValidationIssue(
                    code="chunk.possible_furniture_leak",
                    severity=VALIDATION_WARNING,
                    message="Chunk contains a line that looks like document furniture.",
                    chunk_id=chunk.id,
                )
            )

        if (
            "section_title" not in chunk.metadata
            and "section_path" not in chunk.metadata
        ):
            issues.append(
                ValidationIssue(
                    code="chunk.missing_section_metadata",
                    severity=VALIDATION_INFO,
                    message="Chunk has no section title or section path metadata.",
                    chunk_id=chunk.id,
                )
            )

    return ValidationReport(
        document_id=_chunk_document_id(chunks),
        source_path=None,
        issues=issues,
        summary={
            "page_count": 0,
            "chunk_count": len(chunks),
            "pages_requiring_ocr": 0,
            "pages_without_semantic_blocks": 0,
            "pages_furniture_only": 0,
            "chunks_empty_text": chunks_empty_text,
            "chunks_very_short": chunks_very_short,
            "chunks_very_long": chunks_very_long,
            "chunks_missing_sources": chunks_missing_sources,
        },
    )


def validate_document_and_chunks(
    document: Document,
    chunks: list[Chunk],
) -> ValidationReport:
    """Validate a parsed document and its semantic chunks in one report."""
    document_report = validate_document(document)
    chunk_report = validate_chunks(chunks)
    issues = [*document_report.issues, *chunk_report.issues]

    return ValidationReport(
        document_id=document.id,
        source_path=document.source_path,
        issues=issues,
        summary={
            "page_count": len(document.pages),
            "chunk_count": len(chunks),
            "pages_requiring_ocr": _summary_int(
                document_report,
                "pages_requiring_ocr",
            ),
            "pages_without_semantic_blocks": _summary_int(
                document_report,
                "pages_without_semantic_blocks",
            ),
            "pages_furniture_only": _summary_int(
                document_report,
                "pages_furniture_only",
            ),
            "chunks_empty_text": _summary_int(chunk_report, "chunks_empty_text"),
            "chunks_very_short": _summary_int(chunk_report, "chunks_very_short"),
            "chunks_very_long": _summary_int(chunk_report, "chunks_very_long"),
            "chunks_missing_sources": _summary_int(
                chunk_report,
                "chunks_missing_sources",
            ),
        },
    )


def validate_document_and_chunks_with_decision(
    document: Document,
    chunks: list[Chunk],
) -> tuple[ValidationReport, ValidationDecision]:
    """Validate a document and chunks, then return a gate decision."""
    report = validate_document_and_chunks(document, chunks)
    return report, decide_ingestion_status(report)


def is_furniture_only_page(page: Page) -> bool:
    """Return whether page text is only furniture or intentionally blank content."""
    if not page.text_blocks:
        return False

    for text_block in page.text_blocks:
        text = " ".join((text_block.normalized_text or text_block.text or "").split())
        if not text:
            continue
        if _has_text_block_furniture_flag(text_block):
            continue
        if is_semantic_furniture_text(text):
            continue
        return False
    return True


def _has_possible_furniture_leak(text: str) -> bool:
    for line in text.splitlines():
        stripped_line = line.strip()
        if stripped_line and is_semantic_furniture_text(stripped_line):
            return True
    return False


def _has_text_block_furniture_flag(text_block: object) -> bool:
    return bool(
        getattr(text_block, "is_page_furniture", False)
        or getattr(text_block, "is_page_header", False)
        or getattr(text_block, "is_page_footer", False)
        or getattr(text_block, "is_page_number", False)
    )


def _chunk_document_id(chunks: list[Chunk]) -> str | None:
    if not chunks:
        return None
    document_id = chunks[0].document_id
    if all(chunk.document_id == document_id for chunk in chunks):
        return document_id
    return None


def _summary_int(report: ValidationReport, key: str) -> int:
    value = report.summary.get(key, 0)
    if isinstance(value, bool | str):
        return 0
    return value


def _count_issues_by_severity(
    issues: list[ValidationIssue],
    severity: str,
) -> int:
    return sum(1 for issue in issues if issue.severity == severity)


def _issue_reasons(
    issues: list[ValidationIssue],
    severity: str,
) -> list[str]:
    reasons: list[str] = []
    seen: set[str] = set()
    for issue in issues:
        if issue.severity != severity:
            continue
        reason = f"{issue.code}: {issue.message}"
        if reason in seen:
            continue
        reasons.append(reason)
        seen.add(reason)
    return reasons
