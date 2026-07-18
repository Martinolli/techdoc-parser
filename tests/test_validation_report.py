"""Tests for validation report generation."""

import json
from pathlib import Path

from techdoc_parser.core import (
    Chunk,
    Document,
    DocumentMetadata,
    HeadingBlock,
    Page,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
    TableRegionBlock,
    TextBlock,
)
from techdoc_parser.exporters import (
    export_validation_gate_json,
    export_validation_report_json,
    validation_decision_to_json,
    validation_gate_to_json,
    validation_report_to_json,
)
from techdoc_parser.validation import (
    ValidationDecision,
    ValidationIssue,
    ValidationReport,
    decide_ingestion_status,
    validate_chunks,
    validate_document,
    validate_document_and_chunks,
    validate_document_and_chunks_with_decision,
)


def _source(page_number: int = 1) -> SourceLocation:
    return SourceLocation(document_path="manual.pdf", page_number=page_number)


def _document(pages: list[Page]) -> Document:
    return Document(
        id="manual",
        source_path="manual.pdf",
        metadata=DocumentMetadata(title="Manual"),
        pages=pages,
    )


def _text_block(id: str = "text-1", text: str = "Body text.") -> TextBlock:
    return TextBlock(
        id=id,
        source=_source(),
        text=text,
        normalized_text=text,
    )


def _paragraph(
    id: str = "paragraph-1",
    text: str = "Body paragraph with enough text.",
) -> ParagraphBlock:
    return ParagraphBlock(
        id=id,
        source=_source(),
        text=text,
        normalized_text=text,
        source_text_block_ids=["text-1"],
    )


def _heading() -> HeadingBlock:
    return HeadingBlock(
        id="heading-1",
        source=_source(),
        text="1. Scope",
        normalized_text="1. Scope",
        level=1,
    )


def _chunk(
    id: str = "chunk-1",
    text: str = "Chunk text with enough content for validation.",
    *,
    metadata: dict[str, str] | None = None,
    source_page_numbers: list[int] | None = None,
    source_block_ids: list[str] | None = None,
    source_text_block_ids: list[str] | None = None,
) -> Chunk:
    return Chunk(
        id=id,
        document_id="manual",
        text=text,
        source_page_numbers=(
            source_page_numbers if source_page_numbers is not None else [1]
        ),
        source_block_ids=source_block_ids if source_block_ids is not None else ["p1"],
        source_text_block_ids=(
            source_text_block_ids if source_text_block_ids is not None else ["t1"]
        ),
        metadata=metadata if metadata is not None else {"section_title": "Scope"},
    )


def _codes(report: ValidationReport) -> list[str]:
    return [issue.code for issue in report.issues]


def _valid_page() -> Page:
    text_block = _text_block()
    paragraph = _paragraph()
    return Page(
        page_number=1,
        has_native_text=True,
        blocks=[text_block, paragraph],
        text_blocks=[text_block],
    )


def test_validation_issue_to_dict() -> None:
    """ValidationIssue should serialize all fields."""
    issue = ValidationIssue(
        code="chunk.empty_text",
        severity="error",
        message="Chunk text is empty.",
        page_number=2,
        block_id="block-1",
        chunk_id="chunk-1",
    )

    assert issue.to_dict() == {
        "code": "chunk.empty_text",
        "severity": "error",
        "message": "Chunk text is empty.",
        "page_number": 2,
        "block_id": "block-1",
        "chunk_id": "chunk-1",
    }


def test_validation_decision_to_dict() -> None:
    """ValidationDecision should serialize all fields."""
    decision = ValidationDecision(
        status="review",
        can_ingest=False,
        reason="Warnings require review.",
        issue_count=2,
        error_count=0,
        warning_count=1,
        info_count=1,
        review_reasons=["chunk.very_short: Chunk text is very short."],
    )

    assert decision.to_dict() == {
        "status": "review",
        "can_ingest": False,
        "reason": "Warnings require review.",
        "issue_count": 2,
        "error_count": 0,
        "warning_count": 1,
        "info_count": 1,
        "review_reasons": ["chunk.very_short: Chunk text is very short."],
    }


def test_validation_report_to_dict_counts_issues() -> None:
    """ValidationReport should calculate issue counts from severity."""
    report = ValidationReport(
        document_id="manual",
        source_path="manual.pdf",
        issues=[
            ValidationIssue("one", "error", "Error."),
            ValidationIssue("two", "warning", "Warning."),
            ValidationIssue("three", "info", "Info."),
        ],
        summary={"page_count": 1, "chunk_count": 1},
    )

    data = report.to_dict()

    assert data["issue_count"] == 3
    assert data["error_count"] == 1
    assert data["warning_count"] == 1
    assert data["info_count"] == 1
    assert data["summary"] == {
        "page_count": 1,
        "chunk_count": 1,
        "has_errors": True,
        "has_warnings": True,
    }


def test_decide_ingestion_status_fails_for_error_report() -> None:
    """Validation errors should fail the ingestion gate."""
    report = ValidationReport(
        document_id="manual",
        source_path="manual.pdf",
        issues=[ValidationIssue("document.empty", "error", "Document is empty.")],
    )

    decision = decide_ingestion_status(report)

    assert decision.status == "fail"
    assert decision.can_ingest is False
    assert "errors" in decision.reason
    assert decision.review_reasons == ["document.empty: Document is empty."]


def test_decide_ingestion_status_reviews_warning_report() -> None:
    """Warnings without errors should require review."""
    report = ValidationReport(
        document_id="manual",
        source_path="manual.pdf",
        issues=[
            ValidationIssue(
                "chunk.very_short",
                "warning",
                "Chunk text is very short.",
            )
        ],
    )

    decision = decide_ingestion_status(report)

    assert decision.status == "review"
    assert decision.can_ingest is False
    assert "warnings" in decision.reason
    assert decision.review_reasons == ["chunk.very_short: Chunk text is very short."]


def test_decide_ingestion_status_passes_info_only_report() -> None:
    """Info-only reports should pass automated ingestion."""
    report = ValidationReport(
        document_id="manual",
        source_path="manual.pdf",
        issues=[
            ValidationIssue(
                "chunk.missing_section_metadata",
                "info",
                "Chunk has no section metadata.",
            )
        ],
    )

    decision = decide_ingestion_status(report)

    assert decision.status == "pass"
    assert decision.can_ingest is True
    assert decision.info_count == 1


def test_decide_ingestion_status_passes_clean_report() -> None:
    """Clean reports should pass automated ingestion."""
    report = ValidationReport(
        document_id="manual",
        source_path="manual.pdf",
    )

    decision = decide_ingestion_status(report)

    assert decision.status == "pass"
    assert decision.can_ingest is True
    assert decision.review_reasons == []


def test_validate_document_empty_document_creates_error() -> None:
    """Empty documents should be reported as errors."""
    report = validate_document(_document([]))

    assert "document.empty" in _codes(report)
    assert report.error_count == 1
    assert report.summary["page_count"] == 0


def test_validate_document_page_requires_ocr_creates_warning() -> None:
    """Pages requiring OCR should be reported as warnings."""
    page = Page(page_number=1, requires_ocr=True)

    report = validate_document(_document([page]))

    assert "page.requires_ocr" in _codes(report)
    assert report.warning_count >= 1
    assert report.summary["pages_requiring_ocr"] == 1


def test_validate_document_page_with_no_text_blocks_creates_warning() -> None:
    """Pages with no text blocks should be reported."""
    page = Page(page_number=1)

    report = validate_document(_document([page]))

    assert "page.no_text_blocks" in _codes(report)


def test_validate_document_native_text_without_semantic_blocks_creates_warning() -> (
    None
):
    """Pages with native text but no semantic blocks should be reported."""
    text_block = _text_block()
    page = Page(
        page_number=1,
        has_native_text=True,
        blocks=[text_block],
        text_blocks=[text_block],
    )

    report = validate_document(_document([page]))

    assert "page.no_semantic_blocks" in _codes(report)
    assert report.summary["pages_without_semantic_blocks"] == 1


def test_validate_document_many_table_candidates_creates_warning() -> None:
    """Many table fragments without a grouped region should be reported."""
    tables = [
        TableBlock(
            id=f"table-{index}",
            source=_source(),
            text="A    B",
            normalized_text="A B",
            source_text_block_ids=[f"text-{index}"],
        )
        for index in range(11)
    ]
    page = Page(page_number=1, blocks=tables)

    report = validate_document(_document([page]))

    assert "page.many_table_candidates" in _codes(report)


def test_validate_document_multiple_table_regions_creates_info() -> None:
    """Multiple table regions should be informational."""
    regions = [
        TableRegionBlock(
            id=f"table-region-{index}",
            source=_source(),
            text="A B",
            normalized_text="A B",
            source_text_block_ids=[f"text-{index}"],
        )
        for index in range(2)
    ]
    page = Page(page_number=1, blocks=regions)

    report = validate_document(_document([page]))

    assert "page.multiple_table_regions" in _codes(report)
    assert report.info_count == 1


def test_validate_chunks_empty_list_creates_error() -> None:
    """Empty chunk lists should be reported as errors."""
    report = validate_chunks([])

    assert "chunks.empty" in _codes(report)
    assert report.error_count == 1
    assert report.summary["chunk_count"] == 0


def test_validate_chunks_empty_text_creates_error() -> None:
    """Empty chunk text should be reported."""
    report = validate_chunks([_chunk(text="   ")])

    assert "chunk.empty_text" in _codes(report)
    assert report.summary["chunks_empty_text"] == 1


def test_validate_chunks_very_short_warning_unless_section_metadata() -> None:
    """Short chunks without section metadata should be warnings."""
    report_without_metadata = validate_chunks([_chunk(text="Short.", metadata={})])
    report_with_metadata = validate_chunks(
        [_chunk(text="Short.", metadata={"section_title": "Scope"})]
    )

    assert "chunk.very_short" in _codes(report_without_metadata)
    assert "chunk.very_short" not in _codes(report_with_metadata)


def test_validate_chunks_very_long_creates_warning() -> None:
    """Very long chunk text should be reported."""
    report = validate_chunks([_chunk(text="A" * 4001)])

    assert "chunk.very_long" in _codes(report)
    assert report.summary["chunks_very_long"] == 1


def test_validate_chunks_missing_source_page_numbers_creates_warning() -> None:
    """Chunks should carry source page numbers."""
    report = validate_chunks([_chunk(source_page_numbers=[])])

    assert "chunk.missing_source_pages" in _codes(report)
    assert report.summary["chunks_missing_sources"] == 1


def test_validate_chunks_missing_source_block_ids_creates_warning() -> None:
    """Chunks should carry source block ids."""
    report = validate_chunks([_chunk(source_block_ids=[])])

    assert "chunk.missing_source_blocks" in _codes(report)
    assert report.summary["chunks_missing_sources"] == 1


def test_validate_chunks_missing_source_text_block_ids_creates_info() -> None:
    """Missing source text block ids should be informational."""
    report = validate_chunks([_chunk(source_text_block_ids=[])])

    assert "chunk.missing_source_text_blocks" in _codes(report)
    assert report.info_count == 1


def test_validate_chunks_furniture_leak_creates_warning() -> None:
    """Standalone furniture lines in chunks should be reported."""
    report = validate_chunks([_chunk(text="Body content.\n\n4040.26B")])

    assert "chunk.possible_furniture_leak" in _codes(report)


def test_validate_chunks_missing_section_metadata_creates_info() -> None:
    """Chunks without section metadata should be informational."""
    report = validate_chunks([_chunk(metadata={})])

    assert "chunk.missing_section_metadata" in _codes(report)


def test_validate_document_and_chunks_combines_reports() -> None:
    """Combined validation should include document and chunk issues."""
    text_block = _text_block()
    page = Page(
        page_number=1,
        has_native_text=True,
        blocks=[text_block],
        text_blocks=[text_block],
    )
    report = validate_document_and_chunks(_document([page]), [_chunk(text="")])

    assert "page.no_semantic_blocks" in _codes(report)
    assert "chunk.empty_text" in _codes(report)
    assert report.summary["page_count"] == 1
    assert report.summary["chunk_count"] == 1
    assert report.summary["has_errors"] is True
    assert report.summary["has_warnings"] is True


def test_validate_document_and_chunks_with_decision_fails_empty_inputs() -> None:
    """Combined validation with empty document/chunks should fail."""
    report, decision = validate_document_and_chunks_with_decision(_document([]), [])

    assert "document.empty" in _codes(report)
    assert "chunks.empty" in _codes(report)
    assert decision.status == "fail"
    assert decision.can_ingest is False


def test_validate_document_and_chunks_with_decision_passes_valid_inputs() -> None:
    """Combined validation with valid simple inputs should pass."""
    report, decision = validate_document_and_chunks_with_decision(
        _document([_valid_page()]),
        [_chunk()],
    )

    assert report.issue_count == 0
    assert decision.status == "pass"
    assert decision.can_ingest is True


def test_validation_report_to_json_returns_valid_json() -> None:
    """Validation report JSON helper should serialize report data."""
    report = validate_chunks([_chunk(metadata={})])

    data = json.loads(validation_report_to_json(report))

    assert data["issue_count"] == report.issue_count
    assert data["summary"]["chunk_count"] == 1


def test_validation_decision_to_json_returns_valid_json() -> None:
    """Validation decision JSON helper should serialize decision data."""
    decision = decide_ingestion_status(ValidationReport("manual", "manual.pdf"))

    data = json.loads(validation_decision_to_json(decision))

    assert data["status"] == "pass"
    assert data["can_ingest"] is True


def test_validation_gate_to_json_returns_valid_json() -> None:
    """Validation gate JSON helper should include decision and report."""
    report = validate_document_and_chunks(_document([_valid_page()]), [_chunk()])
    decision = decide_ingestion_status(report)

    data = json.loads(validation_gate_to_json(report, decision))

    assert data["decision"]["status"] == "pass"
    assert data["report"]["issue_count"] == report.issue_count


def test_export_validation_report_json_writes_file(tmp_path: Path) -> None:
    """Validation report exporter should write JSON to disk."""
    report = validate_document_and_chunks(
        _document([Page(page_number=1, blocks=[_heading()])]),
        [_chunk()],
    )
    output_path = tmp_path / "nested" / "validation.json"

    export_validation_report_json(report, output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["issue_count"] == report.issue_count
    assert data["summary"]["page_count"] == 1


def test_export_validation_gate_json_writes_file(tmp_path: Path) -> None:
    """Validation gate exporter should write decision and report JSON."""
    report = validate_document_and_chunks(_document([_valid_page()]), [_chunk()])
    decision = decide_ingestion_status(report)
    output_path = tmp_path / "nested" / "gate.json"

    export_validation_gate_json(report, decision, output_path)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["decision"]["status"] == "pass"
    assert data["report"]["summary"]["page_count"] == 1
