"""Tests for validation Markdown export."""

from pathlib import Path

from techdoc_parser.exporters import (
    export_validation_gate_markdown,
    export_validation_report_markdown,
    validation_gate_to_markdown,
    validation_report_to_markdown,
)
from techdoc_parser.validation import (
    ValidationDecision,
    ValidationIssue,
    ValidationReport,
    decide_ingestion_status,
)


def _report() -> ValidationReport:
    return ValidationReport(
        document_id="manual",
        source_path="manual.pdf",
        issues=[
            ValidationIssue(
                code="page.requires_ocr",
                severity="warning",
                message="Page requires OCR before reliable text extraction.",
                page_number=2,
            ),
            ValidationIssue(
                code="page.furniture_only",
                severity="info",
                message="Page contains only page furniture.",
                page_number=3,
            ),
        ],
        summary={
            "page_count": 3,
            "chunk_count": 4,
            "pages_requiring_ocr": 1,
            "pages_without_semantic_blocks": 0,
            "pages_furniture_only": 1,
            "chunks_empty_text": 0,
            "chunks_very_short": 0,
            "chunks_very_long": 0,
            "chunks_missing_sources": 0,
        },
    )


def test_validation_report_to_markdown_renders_report() -> None:
    """Validation report Markdown should include document, summary, and issues."""
    markdown = validation_report_to_markdown(_report())

    assert "# Validation Report" in markdown
    assert "document_id: manual" in markdown
    assert "page.requires_ocr" in markdown
    assert "page.furniture_only" in markdown
    assert "| Severity | Code | Page | Block | Chunk | Message |" in markdown


def test_validation_gate_to_markdown_renders_decision() -> None:
    """Validation gate Markdown should include decision and review reasons."""
    report = _report()
    decision = decide_ingestion_status(report)

    markdown = validation_gate_to_markdown(report, decision)

    assert "# Validation Gate Summary" in markdown
    assert "Status: REVIEW" in markdown
    assert "Can ingest: no" in markdown
    assert "Reason:" in markdown
    assert "## Review Reasons" in markdown
    assert "page.requires_ocr" in markdown
    assert "| Severity | Code | Page | Block | Chunk | Message |" in markdown


def test_validation_report_to_markdown_handles_empty_issues() -> None:
    """Empty reports should state that no issues were found."""
    report = ValidationReport(document_id="manual", source_path="manual.pdf")

    markdown = validation_report_to_markdown(report)

    assert "No validation issues found." in markdown


def test_validation_report_to_markdown_escapes_table_pipes() -> None:
    """Issue table cells should escape pipe characters."""
    report = ValidationReport(
        document_id="manual",
        source_path="manual.pdf",
        issues=[
            ValidationIssue(
                code="chunk.pipe|code",
                severity="warning",
                message="Message with | pipe.",
            )
        ],
    )

    markdown = validation_report_to_markdown(report)

    assert "chunk.pipe\\|code" in markdown
    assert "Message with \\| pipe." in markdown


def test_export_validation_report_markdown_writes_file(tmp_path: Path) -> None:
    """Validation report Markdown exporter should write output."""
    output_path = tmp_path / "nested" / "report.md"

    export_validation_report_markdown(_report(), output_path)

    assert output_path.exists()
    assert "# Validation Report" in output_path.read_text(encoding="utf-8")


def test_export_validation_gate_markdown_writes_file(tmp_path: Path) -> None:
    """Validation gate Markdown exporter should write output."""
    report = _report()
    decision = ValidationDecision(
        status="review",
        can_ingest=False,
        reason="Validation warnings require review before automated ingestion.",
        issue_count=report.issue_count,
        error_count=report.error_count,
        warning_count=report.warning_count,
        info_count=report.info_count,
        review_reasons=["page.requires_ocr: Page requires OCR."],
    )
    output_path = tmp_path / "nested" / "gate.md"

    export_validation_gate_markdown(report, decision, output_path)

    content = output_path.read_text(encoding="utf-8")
    assert output_path.exists()
    assert "# Validation Gate Summary" in content
    assert "Status: REVIEW" in content
