"""Owner visual-review and P0 pilot acceptance helpers.

This module is evaluation-only. It does not parse PDFs, run OCR, change parser
behavior, write files, call external services, or make visual correctness
decisions automatically.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import PureWindowsPath
from typing import Any

from techdoc_parser.evaluation.source_accuracy import (
    FAIL,
    PASS,
    REVIEW,
    STATUS_FAIL,
    STATUS_NOT_APPLICABLE,
    STATUS_PASS,
    STATUS_REVIEW,
    SourceAccuracyFinding,
    SourceAccuracyMetricResult,
    SourceAccuracyPageResult,
    source_accuracy_page_result_to_dict,
)

PENDING = "pending"
COMPLETED = "completed"
NEEDS_SECOND_REVIEW = "needs_second_review"
BLOCKED = "blocked"

ACCEPTED = "ACCEPTED"
ACCEPTED_WITH_LIMITATIONS = "ACCEPTED_WITH_LIMITATIONS"
REJECTED = "REJECTED"
INCOMPLETE = "INCOMPLETE"

CONFIRMED_PARSER_DEFECT = "CONFIRMED_PARSER_DEFECT"
VISUAL_REVIEW_SCOPE = "owner_visual_review_p0_pages"

VISUAL_REVIEW_STATUSES = (
    PENDING,
    COMPLETED,
    NEEDS_SECOND_REVIEW,
    BLOCKED,
)
VISUAL_CHECK_VALUES = (
    STATUS_PASS,
    STATUS_REVIEW,
    STATUS_FAIL,
    STATUS_NOT_APPLICABLE,
    PENDING,
)
REQUIRED_VISUAL_CHECK_FIELDS = (
    "text_complete",
    "text_exact_enough",
    "reading_order_correct",
    "headings_correct",
    "section_assignment_correct",
    "page_provenance_correct",
    "table_evidence_usable",
    "figure_caption_correct",
    "equation_preserved",
    "admonition_exact",
    "cross_references_preserved",
    "chunks_coherent",
    "fabricated_content_absent",
)
VISUAL_FINDING_CODES = (
    "VISUAL_TEXT_OMISSION",
    "VISUAL_TEXT_DUPLICATION",
    "VISUAL_READING_ORDER_ERROR",
    "VISUAL_HEADING_ERROR",
    "VISUAL_SECTION_ASSIGNMENT_ERROR",
    "VISUAL_PAGE_PROVENANCE_ERROR",
    "VISUAL_TABLE_UNUSABLE",
    "VISUAL_CAPTION_MISMATCH",
    "VISUAL_EQUATION_CORRUPTION",
    "VISUAL_ADMONITION_MISMATCH",
    "VISUAL_REFERENCE_MISMATCH",
    "VISUAL_CHUNK_INCOHERENCE",
    "VISUAL_FABRICATION_DETECTED",
    "VISUAL_LAYOUT_LIMITATION",
)
PROTECTED_DATA_FIELDS = frozenset(
    {
        "absolute_path",
        "document_path",
        "equation_text",
        "extracted_text",
        "full_pdf",
        "image_path",
        "parser_blocks",
        "parser_chunks",
        "pdf_path",
        "procedure_text",
        "source_path",
        "source_proxy",
        "source_text",
        "table_contents",
        "text",
    }
)
MAX_SANITIZED_NOTES_LENGTH = 500


@dataclass(frozen=True)
class VisualReviewDecision:
    """One explicit owner visual-review decision for one approved P0 page."""

    document_key: str
    pdf_page_index: int
    page_number: int
    reviewer_id: str | None
    review_status: str
    checklist: Mapping[str, str]
    finding_codes: tuple[str, ...]
    sanitized_notes: str | None


@dataclass(frozen=True)
class P0PilotAcceptanceResult:
    """Deterministic P0 pilot visual-review acceptance result."""

    outcome: str
    page_results: tuple[SourceAccuracyPageResult, ...]
    document_outcomes: Mapping[str, str]
    visual_review_counts: Mapping[str, int]
    confirmed_defect_counts: Mapping[str, int]
    accepted_limitation_codes: tuple[str, ...]
    blocking_finding_codes: tuple[str, ...]
    corrective_phase_recommendations: tuple[str, ...]
    summary: Mapping[str, Any]


def default_visual_review_decision(
    *,
    document_key: str,
    pdf_page_index: int,
    page_number: int,
    reviewer_id: str | None = None,
) -> VisualReviewDecision:
    """Return an explicit all-pending review decision template."""
    return VisualReviewDecision(
        document_key=document_key,
        pdf_page_index=pdf_page_index,
        page_number=page_number,
        reviewer_id=reviewer_id,
        review_status=PENDING,
        checklist={field: PENDING for field in REQUIRED_VISUAL_CHECK_FIELDS},
        finding_codes=(),
        sanitized_notes=None,
    )


def visual_review_decision_to_dict(
    decision: VisualReviewDecision,
    *,
    reviewer_role: str = "owner_reviewer",
) -> dict[str, Any]:
    """Serialize a visual decision without protected source content."""
    return {
        "document_key": decision.document_key,
        "pdf_page_index": decision.pdf_page_index,
        "page_number": decision.page_number,
        "reviewer_role": reviewer_role,
        "reviewer_id": decision.reviewer_id,
        "review_status": decision.review_status,
        "checklist": dict(decision.checklist),
        "finding_codes": list(decision.finding_codes),
        "sanitized_notes": decision.sanitized_notes,
    }


def validate_visual_review_checklist(
    checklist: Mapping[str, Any],
    *,
    expected_document_key: str,
    expected_pdf_page_index: int,
) -> VisualReviewDecision:
    """Validate one visual-review checklist and reject unsafe payloads."""
    if not isinstance(checklist, Mapping):
        raise ValueError("Visual review checklist must be an object.")
    _reject_protected_payload(checklist)
    allowed = {
        "document_key",
        "pdf_page_index",
        "page_number",
        "reviewer_role",
        "reviewer_id",
        "review_status",
        "checklist",
        "finding_codes",
        "sanitized_notes",
    }
    unknown = set(checklist) - allowed
    if unknown:
        raise ValueError(f"Unknown visual-review fields: {sorted(unknown)}")

    document_key = _required_string(checklist, "document_key")
    if document_key != expected_document_key:
        raise ValueError("Visual review document_key does not match expected page.")

    pdf_page_index = _required_int(checklist, "pdf_page_index")
    if pdf_page_index != expected_pdf_page_index:
        raise ValueError("Visual review pdf_page_index does not match expected page.")

    page_number = _required_int(checklist, "page_number")
    if page_number != pdf_page_index + 1:
        raise ValueError("Visual review page_number must equal pdf_page_index + 1.")

    reviewer_id = _optional_short_string(checklist.get("reviewer_id"), "reviewer_id")
    review_status = _required_string(checklist, "review_status")
    if review_status not in VISUAL_REVIEW_STATUSES:
        raise ValueError(f"Invalid visual review status: {review_status}")

    raw_checks = checklist.get("checklist")
    if not isinstance(raw_checks, Mapping):
        raise ValueError("Visual review checklist must include checklist object.")
    unknown_checks = set(raw_checks) - set(REQUIRED_VISUAL_CHECK_FIELDS)
    if unknown_checks:
        raise ValueError(f"Unknown visual checklist fields: {sorted(unknown_checks)}")
    missing_checks = set(REQUIRED_VISUAL_CHECK_FIELDS) - set(raw_checks)
    if missing_checks:
        raise ValueError(f"Missing visual checklist fields: {sorted(missing_checks)}")
    normalized_checks: dict[str, str] = {}
    for field_name in REQUIRED_VISUAL_CHECK_FIELDS:
        value = raw_checks.get(field_name)
        if not isinstance(value, str) or value not in VISUAL_CHECK_VALUES:
            raise ValueError(f"Invalid checklist value for {field_name}: {value}")
        normalized_checks[field_name] = value

    finding_codes = _string_tuple(checklist.get("finding_codes"), "finding_codes")
    unknown_codes = set(finding_codes) - set(VISUAL_FINDING_CODES)
    if unknown_codes:
        raise ValueError(f"Unknown visual finding codes: {sorted(unknown_codes)}")

    sanitized_notes = _optional_short_string(
        checklist.get("sanitized_notes"),
        "sanitized_notes",
        max_length=MAX_SANITIZED_NOTES_LENGTH,
    )
    return VisualReviewDecision(
        document_key=document_key,
        pdf_page_index=pdf_page_index,
        page_number=page_number,
        reviewer_id=reviewer_id,
        review_status=review_status,
        checklist=normalized_checks,
        finding_codes=finding_codes,
        sanitized_notes=sanitized_notes,
    )


def merge_visual_review_decision(
    page_result: SourceAccuracyPageResult,
    decision: VisualReviewDecision,
) -> SourceAccuracyPageResult:
    """Merge explicit visual-review evidence into an automated page result."""
    if page_result.document_key != decision.document_key:
        raise ValueError("Visual review document_key does not match page result.")
    if page_result.pdf_page_index != decision.pdf_page_index:
        raise ValueError("Visual review pdf_page_index does not match page result.")
    if page_result.page_number != decision.page_number:
        raise ValueError("Visual review page_number does not match page result.")

    visual_findings = _visual_findings_from_decision(
        decision,
        start_sequence=len(page_result.findings) + 1,
    )
    outcome = _visual_outcome(decision)
    findings = (*page_result.findings, *visual_findings)
    conflicts = _conflict_findings(
        page_result=page_result,
        decision=decision,
        visual_outcome=outcome,
        start_sequence=len(findings) + 1,
    )
    findings = (*findings, *conflicts)
    final_outcome = _final_page_outcome(
        automated_outcome=page_result.automated_outcome,
        decision=decision,
        visual_outcome=outcome,
        findings=findings,
    )
    visual_metric = SourceAccuracyMetricResult(
        name="owner_visual_review",
        status=_visual_metric_status(decision, outcome),
        value=decision.review_status,
        message="Owner visual-review decision recorded separately from automation.",
        details={
            "pending_checks": _checks_with_value(decision, PENDING),
            "review_checks": _checks_with_value(decision, STATUS_REVIEW),
            "failed_checks": _checks_with_value(decision, STATUS_FAIL),
            "finding_codes": list(decision.finding_codes),
        },
    )
    return replace(
        page_result,
        visual_review_status=decision.review_status,
        visual_review_outcome=outcome,
        final_page_outcome=final_outcome,
        metrics=(*page_result.metrics, visual_metric),
        findings=findings,
    )


def assess_p0_pilot_acceptance(
    page_results: Sequence[SourceAccuracyPageResult],
) -> P0PilotAcceptanceResult:
    """Aggregate page outcomes into document and corpus acceptance outcomes."""
    pages = tuple(
        sorted(page_results, key=lambda page: (page.document_key, page.pdf_page_index))
    )
    by_document: dict[str, list[SourceAccuracyPageResult]] = {}
    for page in pages:
        by_document.setdefault(page.document_key, []).append(page)

    document_outcomes = {
        key: _document_outcome(value) for key, value in sorted(by_document.items())
    }
    if not pages or any(
        outcome == INCOMPLETE for outcome in document_outcomes.values()
    ):
        outcome = INCOMPLETE
    elif any(outcome == REJECTED for outcome in document_outcomes.values()):
        outcome = REJECTED
    elif any(
        outcome == ACCEPTED_WITH_LIMITATIONS for outcome in document_outcomes.values()
    ):
        outcome = ACCEPTED_WITH_LIMITATIONS
    else:
        outcome = ACCEPTED

    findings = [finding for page in pages for finding in page.findings]
    confirmed_defects = [
        finding for finding in findings if finding.category == CONFIRMED_PARSER_DEFECT
    ]
    blocking_codes = tuple(
        dict.fromkeys(
            finding.code for finding in findings if _is_blocking_finding(finding)
        )
    )
    accepted_limitations = tuple(
        dict.fromkeys(
            finding.code
            for page in pages
            for finding in page.findings
            if page.visual_review_status in {COMPLETED, NEEDS_SECOND_REVIEW}
            and page.final_page_outcome == REVIEW
            and not _is_blocking_finding(finding)
        )
    )
    recommendations = _corrective_recommendations(outcome, blocking_codes)
    summary = {
        "page_count": len(pages),
        "document_count": len(document_outcomes),
        "page_outcome_counts": dict(Counter(page.final_page_outcome for page in pages)),
        "completion_percentage": _completion_percentage(pages),
        "pending_pages": sum(
            1 for page in pages if page.visual_review_status == PENDING
        ),
        "completed_pages": sum(
            1 for page in pages if page.visual_review_status == COMPLETED
        ),
        "second_review_pages": sum(
            1 for page in pages if page.visual_review_status == NEEDS_SECOND_REVIEW
        ),
        "blocked_pages": sum(
            1 for page in pages if page.visual_review_status == BLOCKED
        ),
        "pages_with_review_checks": sum(
            1 for page in pages if _page_has_visual_metric_detail(page, "review_checks")
        ),
        "pages_with_failed_checks": sum(
            1 for page in pages if _page_has_visual_metric_detail(page, "failed_checks")
        ),
        "pages_with_all_applicable_checks_passed": sum(
            1
            for page in pages
            if page.visual_review_status == COMPLETED
            and page.visual_review_outcome == PASS
        ),
    }
    return P0PilotAcceptanceResult(
        outcome=outcome,
        page_results=pages,
        document_outcomes=document_outcomes,
        visual_review_counts=dict(Counter(page.visual_review_status for page in pages)),
        confirmed_defect_counts=dict(
            Counter(finding.code for finding in confirmed_defects)
        ),
        accepted_limitation_codes=accepted_limitations,
        blocking_finding_codes=blocking_codes,
        corrective_phase_recommendations=recommendations,
        summary=summary,
    )


def p0_pilot_acceptance_result_to_dict(
    result: P0PilotAcceptanceResult,
) -> dict[str, Any]:
    """Serialize acceptance result as sanitized JSON-safe data."""
    return {
        "outcome": result.outcome,
        "visual_review_scope": VISUAL_REVIEW_SCOPE,
        "document_outcomes": dict(result.document_outcomes),
        "visual_review_counts": dict(result.visual_review_counts),
        "confirmed_defect_counts": dict(result.confirmed_defect_counts),
        "accepted_limitation_codes": list(result.accepted_limitation_codes),
        "blocking_finding_codes": list(result.blocking_finding_codes),
        "corrective_phase_recommendations": list(
            result.corrective_phase_recommendations
        ),
        "summary": dict(result.summary),
        "page_results": [
            _sanitized_visual_page_summary(page) for page in result.page_results
        ],
        "privacy": {
            "sanitized": True,
            "source_text_committed": False,
            "rendered_images_committed": False,
            "full_document_accuracy_evaluated": False,
            "ocr_run": False,
        },
    }


def p0_pilot_acceptance_result_to_json(result: P0PilotAcceptanceResult) -> str:
    """Serialize acceptance result deterministically."""
    return (
        json.dumps(
            p0_pilot_acceptance_result_to_dict(result),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def load_source_accuracy_page_results_from_report(
    data: Mapping[str, Any],
) -> tuple[SourceAccuracyPageResult, ...]:
    """Load sanitized source-accuracy page results from a policy-v2 report."""
    pages = data.get("page_results")
    if not isinstance(pages, Sequence) or isinstance(pages, str):
        raise ValueError("Automated source-accuracy report must contain page_results.")
    return tuple(
        _page_result_from_dict(page) for page in pages if isinstance(page, Mapping)
    )


def _page_result_from_dict(data: Mapping[str, Any]) -> SourceAccuracyPageResult:
    evidence_modes = _string_tuple(data.get("evidence_modes"), "evidence_modes")
    if len(evidence_modes) != 2:
        raise ValueError("Source-accuracy page evidence_modes must contain 2 values.")
    return SourceAccuracyPageResult(
        document_key=_required_string(data, "document_key"),
        filename=_required_string(data, "filename"),
        pdf_page_index=_required_int(data, "pdf_page_index"),
        page_number=_required_int(data, "page_number"),
        printed_page_label=_optional_string(data.get("printed_page_label")),
        evaluation_roles=_string_tuple(
            data.get("evaluation_roles"), "evaluation_roles"
        ),
        automated_outcome=_required_string(data, "automated_outcome"),
        visual_review_status=_required_string(data, "visual_review_status"),
        visual_review_outcome=_required_string(data, "visual_review_outcome"),
        final_page_outcome=_required_string(data, "final_page_outcome"),
        metrics=tuple(
            _metric_from_dict(item)
            for item in _sequence_of_mappings(data.get("metrics"))
        ),
        findings=tuple(
            _finding_from_dict(item)
            for item in _sequence_of_mappings(data.get("findings"))
        ),
        parser_counts=_int_mapping(data.get("parser_counts")),
        source_proxy_counts=dict(_mapping_or_empty(data.get("source_proxy_counts"))),
        review_artifact_labels=_string_tuple(
            data.get("review_artifact_labels"),
            "review_artifact_labels",
        ),
        source_accuracy_scope=_required_string(data, "source_accuracy_scope"),
        evidence_modes=(evidence_modes[0], evidence_modes[1]),
        full_document_accuracy_evaluated=bool(
            data.get("full_document_accuracy_evaluated")
        ),
        ocr_accuracy_evaluated=bool(data.get("ocr_accuracy_evaluated")),
        visual_layout_accuracy_evaluated=_required_string(
            data,
            "visual_layout_accuracy_evaluated",
        ),
        context_pages=tuple(
            value for value in data.get("context_pages", ()) if isinstance(value, int)
        ),
        operational_full_document_parse=bool(
            data.get("operational_full_document_parse")
        ),
        sr22_text_classification=_optional_string(data.get("sr22_text_classification")),
        original_automated_outcome=_optional_string(
            data.get("original_automated_outcome")
        ),
        policy_corrections=(),
        source_block_eligibility_summary=_int_mapping(
            data.get("source_block_eligibility_summary")
        ),
    )


def _metric_from_dict(data: Mapping[str, Any]) -> SourceAccuracyMetricResult:
    return SourceAccuracyMetricResult(
        name=_required_string(data, "name"),
        status=_required_string(data, "status"),
        value=data.get("value"),
        threshold=data.get("threshold"),
        unit=_optional_string(data.get("unit")),
        message=str(data.get("message", "")),
        details=dict(_mapping_or_empty(data.get("details"))),
    )


def _finding_from_dict(data: Mapping[str, Any]) -> SourceAccuracyFinding:
    return SourceAccuracyFinding(
        finding_id=_required_string(data, "finding_id"),
        document_key=_required_string(data, "document_key"),
        pdf_page_index=_required_int(data, "pdf_page_index"),
        page_number=_required_int(data, "page_number"),
        category=_required_string(data, "category"),
        severity=_required_string(data, "severity"),
        code=_required_string(data, "code"),
        message=_required_string(data, "message"),
        source_entity_ids=_string_tuple(
            data.get("source_entity_ids"), "source_entity_ids"
        ),
        parser_entity_ids=_string_tuple(
            data.get("parser_entity_ids"), "parser_entity_ids"
        ),
        metric_name=_optional_string(data.get("metric_name")),
        requires_manual_review=bool(data.get("requires_manual_review")),
        details=dict(_mapping_or_empty(data.get("details"))),
    )


def _visual_findings_from_decision(
    decision: VisualReviewDecision,
    *,
    start_sequence: int,
) -> tuple[SourceAccuracyFinding, ...]:
    findings: list[SourceAccuracyFinding] = []
    sequence = start_sequence
    for field_name, value in sorted(decision.checklist.items()):
        if value not in {STATUS_FAIL, STATUS_REVIEW, PENDING}:
            continue
        if value == PENDING and decision.review_status == PENDING:
            continue
        code, severity, category, message = _visual_finding_policy(field_name, value)
        findings.append(
            SourceAccuracyFinding(
                finding_id=_visual_finding_id(decision, sequence),
                document_key=decision.document_key,
                pdf_page_index=decision.pdf_page_index,
                page_number=decision.page_number,
                category=category,
                severity=severity,
                code=code,
                message=message,
                metric_name=f"visual_{field_name}",
                requires_manual_review=value != STATUS_FAIL,
                details={
                    "checklist_field": field_name,
                    "checklist_value": value,
                    "affected_parser_stage": _affected_stage(field_name),
                    "recommended_owner": "techdoc-parser",
                    "recommended_corrective_phase": _recommended_phase(field_name),
                    "sanitized_notes_present": decision.sanitized_notes is not None,
                },
            )
        )
        sequence += 1
    for code in decision.finding_codes:
        findings.append(
            SourceAccuracyFinding(
                finding_id=_visual_finding_id(decision, sequence),
                document_key=decision.document_key,
                pdf_page_index=decision.pdf_page_index,
                page_number=decision.page_number,
                category=CONFIRMED_PARSER_DEFECT,
                severity="major",
                code=code,
                message="Owner visual review recorded a generalized finding code.",
                metric_name="owner_visual_review",
                details={
                    "recommended_owner": "techdoc-parser",
                    "recommended_corrective_phase": "targeted_parser_correction",
                    "sanitized_notes_present": decision.sanitized_notes is not None,
                },
            )
        )
        sequence += 1
    return tuple(findings)


def _conflict_findings(
    *,
    page_result: SourceAccuracyPageResult,
    decision: VisualReviewDecision,
    visual_outcome: str,
    start_sequence: int,
) -> tuple[SourceAccuracyFinding, ...]:
    code = None
    message = None
    if page_result.automated_outcome == PASS and visual_outcome == FAIL:
        code = "AUTOMATED_PASS_VISUAL_FAIL"
        message = "Automated PASS conflicts with visually confirmed FAIL."
    elif page_result.automated_outcome == REVIEW and visual_outcome == PASS:
        code = "AUTOMATED_REVIEW_VISUAL_PASS"
        message = "Automated REVIEW conflicts with completed visual PASS."
    elif page_result.automated_outcome == FAIL and visual_outcome == PASS:
        code = "AUTOMATED_FAIL_VISUAL_PASS"
        message = "Automated FAIL conflicts with completed visual PASS."
    if code is None or message is None:
        return ()
    return (
        SourceAccuracyFinding(
            finding_id=_visual_finding_id(decision, start_sequence),
            document_key=decision.document_key,
            pdf_page_index=decision.pdf_page_index,
            page_number=decision.page_number,
            category="EVALUATION_FRAMEWORK_ISSUE",
            severity="informational",
            code=code,
            message=message,
            metric_name="automated_visual_conflict",
            requires_manual_review=True,
            details={
                "automated_outcome": page_result.automated_outcome,
                "visual_outcome": visual_outcome,
                "disposition": "recorded_without_overwriting_automated_evidence",
            },
        ),
    )


def _visual_outcome(decision: VisualReviewDecision) -> str:
    values = set(decision.checklist.values())
    if STATUS_FAIL in values or decision.finding_codes:
        return FAIL
    if (
        PENDING in values
        or STATUS_REVIEW in values
        or decision.review_status in {PENDING, NEEDS_SECOND_REVIEW, BLOCKED}
    ):
        return REVIEW
    return PASS


def _final_page_outcome(
    *,
    automated_outcome: str,
    decision: VisualReviewDecision,
    visual_outcome: str,
    findings: Sequence[SourceAccuracyFinding],
) -> str:
    if automated_outcome == FAIL:
        return FAIL
    if visual_outcome == FAIL:
        return FAIL
    if any(_is_blocking_finding(finding) for finding in findings):
        return FAIL
    if decision.review_status != COMPLETED:
        return REVIEW
    if PENDING in set(decision.checklist.values()):
        return REVIEW
    if STATUS_REVIEW in set(decision.checklist.values()):
        return REVIEW
    return PASS


def _visual_metric_status(decision: VisualReviewDecision, outcome: str) -> str:
    if outcome == FAIL:
        return STATUS_FAIL
    if decision.review_status == COMPLETED and outcome == PASS:
        return STATUS_PASS
    return STATUS_REVIEW


def _document_outcome(pages: Sequence[SourceAccuracyPageResult]) -> str:
    if any(page.visual_review_status in {PENDING, BLOCKED} for page in pages):
        return INCOMPLETE
    if any(page.final_page_outcome == FAIL for page in pages):
        return REJECTED
    if any(page.final_page_outcome == REVIEW for page in pages):
        return ACCEPTED_WITH_LIMITATIONS
    return ACCEPTED


def _sanitized_visual_page_summary(page: SourceAccuracyPageResult) -> dict[str, Any]:
    visual_metric = next(
        (
            metric
            for metric in reversed(page.metrics)
            if metric.name == "owner_visual_review"
        ),
        None,
    )
    checklist_statuses = {
        field: "not_recorded" for field in REQUIRED_VISUAL_CHECK_FIELDS
    }
    if visual_metric is not None:
        detail = dict(visual_metric.details)
        for field_name in _string_items(detail.get("pending_checks")):
            checklist_statuses[field_name] = PENDING
        for field_name in _string_items(detail.get("review_checks")):
            checklist_statuses[field_name] = STATUS_REVIEW
        for field_name in _string_items(detail.get("failed_checks")):
            checklist_statuses[field_name] = STATUS_FAIL
    return {
        "document_key": page.document_key,
        "pdf_page_index": page.pdf_page_index,
        "page_number": page.page_number,
        "reviewer_role": "owner_reviewer",
        "review_status": page.visual_review_status,
        "automated_outcome": page.automated_outcome,
        "visual_review_outcome": page.visual_review_outcome,
        "final_outcome": page.final_page_outcome,
        "checklist_statuses": checklist_statuses,
        "generalized_finding_codes": [
            finding.code
            for finding in page.findings
            if finding.code.startswith("VISUAL_")
        ],
        "accepted_limitation_codes": [
            finding.code
            for finding in page.findings
            if page.visual_review_status in {COMPLETED, NEEDS_SECOND_REVIEW}
            and page.final_page_outcome == REVIEW
            and not _is_blocking_finding(finding)
        ],
    }


def _visual_finding_policy(field_name: str, value: str) -> tuple[str, str, str, str]:
    if value == PENDING:
        return (
            "VISUAL_CHECK_PENDING",
            "informational",
            "MANUAL_REVIEW_REQUIRED",
            "A required visual checklist item remains pending.",
        )
    if value == STATUS_REVIEW:
        return (
            "VISUAL_LAYOUT_LIMITATION",
            "minor",
            "DOCUMENT_LAYOUT_LIMITATION",
            "Owner visual review accepted a generalized review limitation.",
        )
    return (
        _fail_code(field_name),
        _fail_severity(field_name),
        CONFIRMED_PARSER_DEFECT,
        ("Owner visual review confirmed a generalized parser or evidence defect."),
    )


def _fail_code(field_name: str) -> str:
    return {
        "text_complete": "VISUAL_TEXT_OMISSION",
        "text_exact_enough": "VISUAL_TEXT_DUPLICATION",
        "reading_order_correct": "VISUAL_READING_ORDER_ERROR",
        "headings_correct": "VISUAL_HEADING_ERROR",
        "section_assignment_correct": "VISUAL_SECTION_ASSIGNMENT_ERROR",
        "page_provenance_correct": "VISUAL_PAGE_PROVENANCE_ERROR",
        "table_evidence_usable": "VISUAL_TABLE_UNUSABLE",
        "figure_caption_correct": "VISUAL_CAPTION_MISMATCH",
        "equation_preserved": "VISUAL_EQUATION_CORRUPTION",
        "admonition_exact": "VISUAL_ADMONITION_MISMATCH",
        "cross_references_preserved": "VISUAL_REFERENCE_MISMATCH",
        "chunks_coherent": "VISUAL_CHUNK_INCOHERENCE",
        "fabricated_content_absent": "VISUAL_FABRICATION_DETECTED",
    }[field_name]


def _fail_severity(field_name: str) -> str:
    if field_name in {
        "text_complete",
        "page_provenance_correct",
        "admonition_exact",
        "equation_preserved",
        "fabricated_content_absent",
    }:
        return "critical"
    if field_name in {
        "text_exact_enough",
        "reading_order_correct",
        "section_assignment_correct",
        "table_evidence_usable",
        "chunks_coherent",
    }:
        return "major"
    return "minor"


def _affected_stage(field_name: str) -> str:
    return {
        "text_complete": "pdf_extraction",
        "text_exact_enough": "normalization",
        "reading_order_correct": "reading_order",
        "headings_correct": "heading_detection",
        "section_assignment_correct": "section_hierarchy",
        "page_provenance_correct": "source_provenance",
        "table_evidence_usable": "table_mapping",
        "figure_caption_correct": "figure_mapping",
        "equation_preserved": "equation_mapping",
        "admonition_exact": "admonition_mapping",
        "cross_references_preserved": "cross_reference_mapping",
        "chunks_coherent": "chunk_generation",
        "fabricated_content_absent": "content_integrity",
    }[field_name]


def _recommended_phase(field_name: str) -> str:
    if field_name in {"table_evidence_usable", "figure_caption_correct"}:
        return "targeted_entity_mapping_correction"
    if field_name == "chunks_coherent":
        return "targeted_chunking_correction"
    return "targeted_parser_correction"


def _visual_finding_id(decision: VisualReviewDecision, sequence: int) -> str:
    return f"{decision.document_key}:p{decision.pdf_page_index}:visual:{sequence:03d}"


def _completion_percentage(pages: Sequence[SourceAccuracyPageResult]) -> float:
    if not pages:
        return 0.0
    completed = sum(1 for page in pages if page.visual_review_status == COMPLETED)
    return round((completed / len(pages)) * 100.0, 2)


def _page_has_visual_metric_detail(
    page: SourceAccuracyPageResult,
    detail_key: str,
) -> bool:
    for metric in page.metrics:
        if metric.name != "owner_visual_review":
            continue
        value = metric.details.get(detail_key)
        return bool(value)
    return False


def _checks_with_value(decision: VisualReviewDecision, value: str) -> list[str]:
    return [
        field_name
        for field_name, field_value in sorted(decision.checklist.items())
        if field_value == value
    ]


def _is_blocking_finding(finding: SourceAccuracyFinding) -> bool:
    return finding.category == CONFIRMED_PARSER_DEFECT and finding.severity in {
        "critical",
        "major",
    }


def _corrective_recommendations(
    outcome: str,
    blocking_codes: Sequence[str],
) -> tuple[str, ...]:
    if outcome == INCOMPLETE:
        return ("complete_remaining_owner_visual_reviews",)
    if outcome == REJECTED:
        phases = ["targeted_parser_correction"]
        if blocking_codes:
            phases.append("rerun_p0_visual_review_after_correction")
        return tuple(phases)
    if outcome == ACCEPTED_WITH_LIMITATIONS:
        return ("second_review_or_formal_limitation_acceptance",)
    return ("phase_13i_b3_final_p0_acceptance",)


def _reject_protected_payload(value: Any, *, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in PROTECTED_DATA_FIELDS:
                raise ValueError(f"Protected data field is not allowed: {key_text}")
            _reject_protected_payload(item, path=f"{path}.{key_text}")
    elif isinstance(value, Sequence) and not isinstance(value, str):
        for index, item in enumerate(value):
            _reject_protected_payload(item, path=f"{path}[{index}]")
    elif isinstance(value, str):
        if _looks_like_absolute_path(value):
            raise ValueError(
                f"Absolute paths are not allowed in visual review data: {path}"
            )
        lowered = value.lower()
        if "source text:" in lowered or "table contents:" in lowered:
            raise ValueError(f"Protected source-derived note is not allowed: {path}")


def _looks_like_absolute_path(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if stripped.startswith(("/", "\\", "file:")):
        return True
    if PureWindowsPath(stripped).drive:
        return True
    return bool(re.match(r"^[A-Za-z]:[\\/]", stripped))


def _required_string(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Visual review requires non-empty string {key}.")
    return value.strip()


def _required_int(data: Mapping[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Visual review requires integer {key}.")
    return value


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_short_string(
    value: Any,
    field_name: str,
    *,
    max_length: int = 80,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or null.")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValueError(f"{field_name} is too long.")
    return normalized


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError(f"{field_name} must be a sequence of strings.")
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} must contain non-empty strings.")
        result.append(item.strip())
    return tuple(result)


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("Expected mapping.")
    return value


def _int_mapping(value: Any) -> Mapping[str, int]:
    mapping = _mapping_or_empty(value)
    return {
        str(key): int(item) for key, item in mapping.items() if isinstance(item, int)
    }


def _sequence_of_mappings(value: Any) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError("Expected sequence of mappings.")
    return tuple(item for item in value if isinstance(item, Mapping))


def _string_items(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(str(item) for item in value)


__all__ = [
    "ACCEPTED",
    "ACCEPTED_WITH_LIMITATIONS",
    "BLOCKED",
    "COMPLETED",
    "CONFIRMED_PARSER_DEFECT",
    "INCOMPLETE",
    "NEEDS_SECOND_REVIEW",
    "PENDING",
    "REJECTED",
    "REQUIRED_VISUAL_CHECK_FIELDS",
    "VISUAL_CHECK_VALUES",
    "VISUAL_FINDING_CODES",
    "VISUAL_REVIEW_SCOPE",
    "VISUAL_REVIEW_STATUSES",
    "P0PilotAcceptanceResult",
    "VisualReviewDecision",
    "assess_p0_pilot_acceptance",
    "default_visual_review_decision",
    "load_source_accuracy_page_results_from_report",
    "merge_visual_review_decision",
    "p0_pilot_acceptance_result_to_dict",
    "p0_pilot_acceptance_result_to_json",
    "source_accuracy_page_result_to_dict",
    "validate_visual_review_checklist",
    "visual_review_decision_to_dict",
]
