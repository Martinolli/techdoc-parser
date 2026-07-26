"""Controlled P0 source-accuracy proxy evaluation.

This module is evaluation-only. It does not change parser behavior, run OCR,
modify source PDFs, call external services, or write files.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path, PureWindowsPath
from typing import Any

import fitz  # type: ignore[import-untyped]

from techdoc_parser.chunking import create_semantic_chunks
from techdoc_parser.contracts import build_structured_document_artifact
from techdoc_parser.contracts.structured_document import structured_document_to_dict
from techdoc_parser.core import Block, Chunk, Document, Page
from techdoc_parser.evaluation.source_block_eligibility import (
    SourceBlockEligibilityPolicy,
    classify_source_block_chunk_eligibility,
    covered_source_block_ids,
    eligible_source_block_ids,
    missing_required_source_block_ids,
    summarize_source_block_eligibility,
)
from techdoc_parser.ingestion import PDFLoader
from techdoc_parser.structure import get_semantic_blocks_for_page

PASS = "PASS"
REVIEW = "REVIEW"
FAIL = "FAIL"

STATUS_PASS = "pass"
STATUS_REVIEW = "review"
STATUS_FAIL = "fail"
STATUS_NOT_MEASURABLE = "not_measurable"
STATUS_NOT_APPLICABLE = "not_applicable"

EVALUATION_SCOPE = "approved_p0_representative_pages"
SOURCE_ACCURACY_SCOPE = "representative_p0_pages"
AUTOMATED_SOURCE_PROXY = "automated_source_proxy"
HUMAN_VISUAL_REVIEW = "human_visual_review"
SOURCE_ACCURACY_POLICY_NAME = "p0-source-accuracy"
SOURCE_ACCURACY_POLICY_VERSION = "2.0"
SOURCE_ACCURACY_PREVIOUS_POLICY_VERSION = "1.0"
SOURCE_ACCURACY_RUN_TYPE = "corrected_evaluator_rerun"
SOURCE_ACCURACY_SUPERSEDES_POLICY_INTERPRETATION = "1"

FINDING_CATEGORIES = (
    "PARSER_DEFECT",
    "SOURCE_PROXY_LIMITATION",
    "CONTRACT_LIMITATION",
    "DOCUMENT_LAYOUT_LIMITATION",
    "OCR_OR_EXTRACTION_LIMITATION",
    "ACCEPTABLE_DEGRADATION",
    "MANUAL_REVIEW_REQUIRED",
    "EVALUATION_FRAMEWORK_ISSUE",
)
SEVERITIES = ("critical", "major", "minor", "informational")
METRIC_STATUSES = (
    STATUS_PASS,
    STATUS_REVIEW,
    STATUS_FAIL,
    STATUS_NOT_MEASURABLE,
    STATUS_NOT_APPLICABLE,
)
VISUAL_CHECK_VALUES = (
    STATUS_PASS,
    STATUS_REVIEW,
    STATUS_FAIL,
    STATUS_NOT_APPLICABLE,
    "pending",
)
VISUAL_CHECK_FIELDS = (
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
SR22_DOCUMENT_KEY = "cirrus_sr22_maintenance_manual"


@dataclass(frozen=True)
class SourceAccuracyPlanPage:
    """One approved P0 page from the committed execution plan."""

    document_key: str
    filename: str
    pdf_page_index: int
    page_number: int
    printed_page_label: str | None
    evaluation_roles: tuple[str, ...]
    priority: str
    selection_reason: tuple[str, ...]
    review_status: str = "approved_for_execution"


@dataclass(frozen=True)
class SourceAccuracyFinding:
    """One controlled source-accuracy finding."""

    finding_id: str
    document_key: str
    pdf_page_index: int
    page_number: int
    category: str
    severity: str
    code: str
    message: str
    source_entity_ids: tuple[str, ...] = ()
    parser_entity_ids: tuple[str, ...] = ()
    metric_name: str | None = None
    requires_manual_review: bool = False
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceAccuracyMetricResult:
    """One deterministic metric result."""

    name: str
    status: str
    value: object
    threshold: object | None = None
    unit: str | None = None
    message: str = ""
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationPolicyCorrection:
    """One additive correction record for a v1 evaluator-policy disposition."""

    original_finding_code: str
    corrected_policy_disposition: str
    corrected_metric_status: str
    correction_reason_code: str
    message: str
    metric_name: str | None = None


@dataclass(frozen=True)
class SourceAccuracyPageResult:
    """Evaluation result for one approved P0 page."""

    document_key: str
    filename: str
    pdf_page_index: int
    page_number: int
    printed_page_label: str | None
    evaluation_roles: tuple[str, ...]
    automated_outcome: str
    visual_review_status: str
    visual_review_outcome: str
    final_page_outcome: str
    metrics: tuple[SourceAccuracyMetricResult, ...]
    findings: tuple[SourceAccuracyFinding, ...]
    parser_counts: Mapping[str, int]
    source_proxy_counts: Mapping[str, int | str | bool]
    review_artifact_labels: tuple[str, ...]
    source_accuracy_scope: str = SOURCE_ACCURACY_SCOPE
    evidence_modes: tuple[str, str] = (AUTOMATED_SOURCE_PROXY, HUMAN_VISUAL_REVIEW)
    full_document_accuracy_evaluated: bool = False
    ocr_accuracy_evaluated: bool = False
    visual_layout_accuracy_evaluated: str = "true_only_where_review_completed"
    context_pages: tuple[int, ...] = ()
    operational_full_document_parse: bool = False
    sr22_text_classification: str | None = None
    evaluation_policy_name: str = SOURCE_ACCURACY_POLICY_NAME
    evaluation_policy_version: str = SOURCE_ACCURACY_POLICY_VERSION
    previous_evaluation_policy_version: str = SOURCE_ACCURACY_PREVIOUS_POLICY_VERSION
    run_type: str = SOURCE_ACCURACY_RUN_TYPE
    supersedes_policy_interpretation: str = (
        SOURCE_ACCURACY_SUPERSEDES_POLICY_INTERPRETATION
    )
    original_automated_outcome: str | None = None
    policy_corrections: tuple[EvaluationPolicyCorrection, ...] = ()
    source_block_eligibility_summary: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceAccuracyPilotResult:
    """Aggregate P0 pilot result."""

    outcome: str
    evaluation_scope: str
    document_count: int
    page_count: int
    page_results: tuple[SourceAccuracyPageResult, ...]
    finding_counts: Mapping[str, int]
    category_counts: Mapping[str, int]
    severity_counts: Mapping[str, int]
    page_outcome_counts: Mapping[str, int]
    metric_summaries: Mapping[str, Mapping[str, int]]
    visual_review_completion_counts: Mapping[str, int]
    document_summaries: Mapping[str, Mapping[str, object]]
    limitations: tuple[str, ...]
    summary: str
    source_accuracy_scope: str = SOURCE_ACCURACY_SCOPE
    full_document_accuracy_evaluated: bool = False
    ocr_accuracy_evaluated: bool = False
    visual_layout_accuracy_evaluated: str = "true_only_where_review_completed"
    evaluation_policy_name: str = SOURCE_ACCURACY_POLICY_NAME
    evaluation_policy_version: str = SOURCE_ACCURACY_POLICY_VERSION
    previous_evaluation_policy_version: str = SOURCE_ACCURACY_PREVIOUS_POLICY_VERSION
    run_type: str = SOURCE_ACCURACY_RUN_TYPE
    supersedes_policy_interpretation: str = (
        SOURCE_ACCURACY_SUPERSEDES_POLICY_INTERPRETATION
    )
    automated_outcome_counts: Mapping[str, int] = field(default_factory=dict)
    policy_correction_counts: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class LocalPageEvidence:
    """Local-only evidence that may include source text."""

    page_result: SourceAccuracyPageResult
    source_proxy: Mapping[str, object]
    parser_blocks: tuple[Mapping[str, object], ...]
    parser_sections: tuple[Mapping[str, object], ...]
    parser_entities: Mapping[str, object]
    parser_chunks: tuple[Mapping[str, object], ...]
    review_checklist: Mapping[str, object]


def load_p0_source_accuracy_plan(
    path: str | Path,
    *,
    strict_p0: bool = True,
) -> tuple[SourceAccuracyPlanPage, ...]:
    """Load and validate the committed P0 source-accuracy plan."""
    plan_path = Path(path)
    data = _load_json_object(plan_path)
    pages_data = data.get("pages")
    if not isinstance(pages_data, list):
        raise ValueError("P0 plan must contain a pages list.")
    pages: list[SourceAccuracyPlanPage] = []
    seen: set[tuple[str, int]] = set()
    for index, item in enumerate(pages_data):
        if not isinstance(item, Mapping):
            raise ValueError(f"Plan entry {index} must be an object.")
        page = SourceAccuracyPlanPage(
            document_key=_required_string(item, "document_key", index),
            filename=_required_filename(item, index),
            pdf_page_index=_required_int(item, "pdf_page_index", index),
            page_number=_required_int(item, "page_number", index),
            printed_page_label=_optional_string(item.get("printed_page_label")),
            evaluation_roles=_string_tuple(item.get("evaluation_roles")),
            priority=_required_string(item, "priority", index),
            selection_reason=_string_tuple(item.get("selection_reason")),
            review_status=_required_string(item, "review_status", index),
        )
        if strict_p0 and page.priority != "P0":
            raise ValueError(f"Plan entry {index} is not priority P0.")
        if page.pdf_page_index + 1 != page.page_number:
            raise ValueError(f"Plan entry {index} has inconsistent page numbering.")
        key = (page.document_key, page.pdf_page_index)
        if key in seen:
            raise ValueError(
                f"Duplicate plan page: {page.document_key} p{page.page_number}."
            )
        seen.add(key)
        if page.review_status != "approved_for_execution":
            raise ValueError(f"Plan entry {index} is not approved for execution.")
        pages.append(page)
    return tuple(
        sorted(pages, key=lambda page: (page.document_key, page.pdf_page_index))
    )


def run_source_accuracy_pilot(
    *,
    input_dir: str | Path,
    plan: Sequence[SourceAccuracyPlanPage],
    document_keys: Collection[str] | None = None,
    context_radius: int = 1,
    checklist_paths: Sequence[str | Path] = (),
) -> SourceAccuracyPilotResult:
    """Run source-accuracy proxy checks for approved P0 pages only."""
    selected_plan = _filter_plan(plan, document_keys)
    checklists = _load_checklists_by_page_id(checklist_paths)
    input_root = Path(input_dir)
    by_document: dict[str, list[SourceAccuracyPlanPage]] = {}
    for plan_page in selected_plan:
        by_document.setdefault(plan_page.document_key, []).append(plan_page)

    page_results: list[SourceAccuracyPageResult] = []
    for document_key in sorted(by_document):
        pages = sorted(by_document[document_key], key=lambda item: item.pdf_page_index)
        source_path = input_root / pages[0].filename
        if not source_path.exists():
            page_results.extend(
                _missing_source_results(source_path, pages, context_radius)
            )
            continue
        parser_document = PDFLoader(str(source_path)).load()
        for plan_page in pages:
            result = evaluate_representative_page(
                source_path=source_path,
                document_key=plan_page.document_key,
                pdf_page_index=plan_page.pdf_page_index,
                page_number=plan_page.page_number,
                printed_page_label=plan_page.printed_page_label,
                evaluation_roles=plan_page.evaluation_roles,
                selection_reason=plan_page.selection_reason,
                context_radius=context_radius,
                parser_document=parser_document,
                checklist=checklists.get(_page_review_id(plan_page)),
            )
            page_results.append(result)

    return _pilot_result(tuple(page_results))


def evaluate_representative_page(
    *,
    source_path: str | Path,
    document_key: str,
    pdf_page_index: int,
    evaluation_roles: Collection[str],
    context_radius: int = 1,
    page_number: int | None = None,
    printed_page_label: str | None = None,
    selection_reason: Sequence[str] = (),
    parser_document: Document | None = None,
    checklist: Mapping[str, object] | None = None,
) -> SourceAccuracyPageResult:
    """Evaluate one representative P0 page without writing files."""
    source = Path(source_path)
    expected_page_number = (
        page_number if page_number is not None else pdf_page_index + 1
    )
    base_plan = SourceAccuracyPlanPage(
        document_key=document_key,
        filename=source.name,
        pdf_page_index=pdf_page_index,
        page_number=expected_page_number,
        printed_page_label=printed_page_label,
        evaluation_roles=tuple(sorted(evaluation_roles)),
        priority="P0",
        selection_reason=tuple(selection_reason),
    )
    if not source.exists():
        return _blocking_page_result(
            base_plan,
            code="SOURCE_FILE_MISSING",
            message="Approved source PDF is missing.",
            context_radius=context_radius,
        )
    try:
        source_proxy = collect_source_page_proxy(source, pdf_page_index)
    except (IndexError, ValueError) as exc:
        return _blocking_page_result(
            base_plan,
            code="SOURCE_PAGE_UNAVAILABLE",
            message=str(exc),
            context_radius=context_radius,
        )
    document = (
        parser_document
        if parser_document is not None
        else PDFLoader(str(source)).load()
    )
    if expected_page_number < 1 or expected_page_number > len(document.pages):
        return _blocking_page_result(
            base_plan,
            code="PARSER_PAGE_UNAVAILABLE",
            message="Parser document does not contain the approved page.",
            context_radius=context_radius,
        )
    parser_page = document.pages[expected_page_number - 1]
    structured = build_structured_document_artifact(
        document,
        document_id=document_key,
        source_checksum=_sha256_file(source),
    )
    structured_data = structured_document_to_dict(structured)
    chunks = create_semantic_chunks(document)
    selected_chunks = _chunks_for_page(chunks, expected_page_number)
    parser_text = _page_parser_text(parser_page)
    (
        metrics,
        finding_specs,
        policy_corrections,
        source_block_eligibility_summary,
    ) = _evaluate_page_metrics(
        plan_page=base_plan,
        source_proxy=source_proxy,
        parser_page=parser_page,
        parser_text=parser_text,
        structured_data=structured_data,
        selected_chunks=selected_chunks,
    )
    findings = _build_findings(base_plan, finding_specs)
    visual_status, visual_outcome, visual_findings = _visual_review_state(
        base_plan,
        checklist,
        start_sequence=len(findings) + 1,
    )
    all_findings = tuple((*findings, *visual_findings))
    automated_outcome = _outcome_from_metrics_and_findings(metrics, findings)
    final_outcome = _final_page_outcome(
        automated_outcome=automated_outcome,
        visual_status=visual_status,
        visual_outcome=visual_outcome,
        findings=all_findings,
    )
    source_counts = _source_proxy_counts(source_proxy)
    parser_counts = _parser_counts(
        parser_page=parser_page,
        structured_data=structured_data,
        chunks=selected_chunks,
        page_number=expected_page_number,
    )
    labels = _artifact_labels(base_plan)
    source_label = source_proxy.get("printed_page_label")
    effective_label = (
        source_label if isinstance(source_label, str) else printed_page_label
    )
    return SourceAccuracyPageResult(
        document_key=document_key,
        filename=source.name,
        pdf_page_index=pdf_page_index,
        page_number=expected_page_number,
        printed_page_label=effective_label,
        evaluation_roles=tuple(sorted(evaluation_roles)),
        automated_outcome=automated_outcome,
        visual_review_status=visual_status,
        visual_review_outcome=visual_outcome,
        final_page_outcome=final_outcome,
        metrics=metrics,
        findings=all_findings,
        parser_counts=parser_counts,
        source_proxy_counts=source_counts,
        review_artifact_labels=labels,
        context_pages=_context_pages(
            expected_page_number,
            len(document.pages),
            context_radius,
        ),
        operational_full_document_parse=True,
        sr22_text_classification=(
            _sr22_text_classification(source_counts)
            if document_key == SR22_DOCUMENT_KEY
            else None
        ),
        original_automated_outcome=FAIL if policy_corrections else None,
        policy_corrections=policy_corrections,
        source_block_eligibility_summary=source_block_eligibility_summary,
    )


def collect_source_page_proxy(
    source_path: str | Path,
    pdf_page_index: int,
) -> dict[str, object]:
    """Collect local automated source-proxy evidence from one PDF page."""
    path = Path(source_path)
    with fitz.open(path) as document:
        if pdf_page_index < 0 or pdf_page_index >= document.page_count:
            raise IndexError(
                f"PDF page index {pdf_page_index} is outside the source document."
            )
        page = document.load_page(pdf_page_index)
        text = page.get_text("text") or ""
        blocks = _source_text_blocks(page)
        words = _word_count(text)
        label = _page_label(page)
        links = page.get_links() or []
        return {
            "source_filename": path.name,
            "source_sha256": _sha256_file(path),
            "pdf_page_index": pdf_page_index,
            "page_number": pdf_page_index + 1,
            "printed_page_label": label,
            "text": text,
            "normalized_lines": _normalized_lines(text),
            "text_blocks": blocks,
            "line_count": len(_normalized_lines(text)),
            "character_count": len(text.strip()),
            "word_count": words,
            "image_count": len(page.get_images(full=False)),
            "width": round(float(page.rect.width), 3),
            "height": round(float(page.rect.height), 3),
            "rotation": int(page.rotation or 0),
            "link_count": len(links),
            "annotation_count": len(list(page.annots() or [])),
            "text_mode": classify_native_text_use(
                character_count=len(text.strip()),
                word_count=words,
                image_count=len(page.get_images(full=False)),
            ),
        }


def classify_native_text_use(
    *,
    character_count: int,
    word_count: int,
    image_count: int,
) -> str:
    """Classify selected page native-text usability without OCR."""
    if character_count >= 100 or word_count >= 20:
        return "native_text_usable"
    if image_count > 0 and character_count < 50:
        return "image_dominant"
    if 0 < character_count < 100:
        return "native_text_sparse"
    return "uncertain"


def default_visual_review_checklist(page_id: str) -> dict[str, object]:
    """Return a local visual checklist with visually dependent fields pending."""
    return {
        "page_id": page_id,
        "checks": {field: "pending" for field in VISUAL_CHECK_FIELDS},
        "reviewer_notes": "",
    }


def source_accuracy_page_result_to_dict(
    result: SourceAccuracyPageResult,
    *,
    sanitized: bool = True,
) -> dict[str, Any]:
    """Convert a page result to JSON-safe data."""
    return {
        "document_key": result.document_key,
        "filename": result.filename,
        "pdf_page_index": result.pdf_page_index,
        "page_number": result.page_number,
        "printed_page_label": result.printed_page_label,
        "evaluation_roles": list(result.evaluation_roles),
        "automated_outcome": result.automated_outcome,
        "visual_review_status": result.visual_review_status,
        "visual_review_outcome": result.visual_review_outcome,
        "final_page_outcome": result.final_page_outcome,
        "metrics": [_metric_to_dict(metric) for metric in result.metrics],
        "findings": [_finding_to_dict(finding) for finding in result.findings],
        "parser_counts": dict(result.parser_counts),
        "source_proxy_counts": dict(result.source_proxy_counts),
        "review_artifact_labels": list(result.review_artifact_labels),
        "source_accuracy_scope": result.source_accuracy_scope,
        "evidence_modes": list(result.evidence_modes),
        "full_document_accuracy_evaluated": result.full_document_accuracy_evaluated,
        "ocr_accuracy_evaluated": result.ocr_accuracy_evaluated,
        "visual_layout_accuracy_evaluated": result.visual_layout_accuracy_evaluated,
        "context_pages": list(result.context_pages),
        "operational_full_document_parse": result.operational_full_document_parse,
        "sr22_text_classification": result.sr22_text_classification,
        "evaluation_policy_name": result.evaluation_policy_name,
        "evaluation_policy_version": result.evaluation_policy_version,
        "previous_evaluation_policy_version": (
            result.previous_evaluation_policy_version
        ),
        "run_type": result.run_type,
        "supersedes_policy_interpretation": result.supersedes_policy_interpretation,
        "original_automated_outcome": result.original_automated_outcome,
        "policy_corrections": [
            _policy_correction_to_dict(correction)
            for correction in result.policy_corrections
        ],
        "source_block_eligibility_summary": dict(
            result.source_block_eligibility_summary
        ),
        "sanitized": sanitized,
    }


def source_accuracy_pilot_result_to_dict(
    result: SourceAccuracyPilotResult,
) -> dict[str, Any]:
    """Convert an aggregate pilot result to JSON-safe sanitized data."""
    return {
        "outcome": result.outcome,
        "evaluation_scope": result.evaluation_scope,
        "source_accuracy_scope": result.source_accuracy_scope,
        "evaluation_policy_name": result.evaluation_policy_name,
        "evaluation_policy_version": result.evaluation_policy_version,
        "previous_evaluation_policy_version": (
            result.previous_evaluation_policy_version
        ),
        "run_type": result.run_type,
        "supersedes_policy_interpretation": result.supersedes_policy_interpretation,
        "full_document_accuracy_evaluated": result.full_document_accuracy_evaluated,
        "ocr_accuracy_evaluated": result.ocr_accuracy_evaluated,
        "visual_layout_accuracy_evaluated": result.visual_layout_accuracy_evaluated,
        "document_count": result.document_count,
        "page_count": result.page_count,
        "finding_counts": dict(result.finding_counts),
        "category_counts": dict(result.category_counts),
        "severity_counts": dict(result.severity_counts),
        "page_outcome_counts": dict(result.page_outcome_counts),
        "automated_outcome_counts": dict(result.automated_outcome_counts),
        "policy_correction_counts": dict(result.policy_correction_counts),
        "metric_summaries": {
            key: dict(value) for key, value in sorted(result.metric_summaries.items())
        },
        "visual_review_completion_counts": dict(result.visual_review_completion_counts),
        "document_summaries": {
            key: dict(value) for key, value in sorted(result.document_summaries.items())
        },
        "limitations": list(result.limitations),
        "summary": result.summary,
        "page_results": [
            source_accuracy_page_result_to_dict(page) for page in result.page_results
        ],
    }


def source_accuracy_pilot_result_to_json(
    result: SourceAccuracyPilotResult,
) -> str:
    """Serialize aggregate source-accuracy pilot result as sanitized JSON."""
    return (
        json.dumps(
            source_accuracy_pilot_result_to_dict(result),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def source_accuracy_pilot_result_to_markdown(
    result: SourceAccuracyPilotResult,
) -> str:
    """Serialize aggregate source-accuracy pilot result as sanitized Markdown."""
    lines = [
        "# P0 Source Accuracy Pilot",
        "",
        "source_accuracy_scope: representative_p0_pages",
        f"evaluation_policy_name: {result.evaluation_policy_name}",
        f"evaluation_policy_version: {result.evaluation_policy_version}",
        f"run_type: {result.run_type}",
        (
            "supersedes_policy_interpretation: "
            f"{result.supersedes_policy_interpretation}"
        ),
        "visual_review_status: pending_or_completed_per_page",
        "full_document_accuracy_evaluated: false",
        "ocr_accuracy_evaluated: false",
        "",
        "## Summary",
        "",
        f"- Outcome: `{result.outcome}`",
        f"- Evaluation scope: `{result.evaluation_scope}`",
        f"- Evaluation policy: `{result.evaluation_policy_name}` "
        f"`{result.evaluation_policy_version}`",
        f"- Run type: `{result.run_type}`",
        f"- Documents: `{result.document_count}`",
        f"- P0 pages: `{result.page_count}`",
        (
            "- Full-document accuracy evaluated: "
            f"`{result.full_document_accuracy_evaluated}`"
        ),
        f"- OCR accuracy evaluated: `{result.ocr_accuracy_evaluated}`",
        "",
        "## Page Outcomes",
        "",
        (
            "| Document | Page | Automated outcome | Visual review | "
            "Final outcome | Main findings |"
        ),
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for page in result.page_results:
        finding_codes = ", ".join(_top_finding_codes(page.findings)) or "none"
        lines.append(
            f"| `{page.document_key}` | {page.page_number} | "
            f"`{page.automated_outcome}` | `{page.visual_review_status}` | "
            f"`{page.final_page_outcome}` | {finding_codes} |"
        )
    lines.extend(
        [
            "",
            "## Finding Counts",
            "",
            _mapping_line(result.category_counts),
            "",
            "## Severity Counts",
            "",
            _mapping_line(result.severity_counts),
            "",
            "## Policy Corrections",
            "",
            _mapping_line(result.policy_correction_counts),
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in result.limitations)
    lines.extend(
        [
            "",
            "## Privacy",
            "",
            "This report is sanitized. It contains no extracted source text, "
            "rendered images, equations, table contents, or source hashes.",
        ]
    )
    return "\n".join(lines) + "\n"


def local_page_evidence_to_dict(evidence: LocalPageEvidence) -> dict[str, object]:
    """Return local evidence data. This may include extracted source text."""
    return {
        "page_result": source_accuracy_page_result_to_dict(evidence.page_result),
        "source_proxy": dict(evidence.source_proxy),
        "parser_blocks": list(evidence.parser_blocks),
        "parser_sections": list(evidence.parser_sections),
        "parser_entities": dict(evidence.parser_entities),
        "parser_chunks": list(evidence.parser_chunks),
        "review_checklist": dict(evidence.review_checklist),
    }


def build_local_page_evidence(
    *,
    source_path: str | Path,
    result: SourceAccuracyPageResult,
    parser_document: Document | None = None,
) -> LocalPageEvidence:
    """Build local-only detailed evidence for one page without writing it."""
    source = Path(source_path)
    document = (
        parser_document
        if parser_document is not None
        else PDFLoader(str(source)).load()
    )
    source_proxy = collect_source_page_proxy(source, result.pdf_page_index)
    parser_page = document.pages[result.page_number - 1]
    structured = build_structured_document_artifact(
        document,
        document_id=result.document_key,
        source_checksum=_sha256_file(source),
    )
    structured_data = structured_document_to_dict(structured)
    chunks = _chunks_for_page(create_semantic_chunks(document), result.page_number)
    return LocalPageEvidence(
        page_result=result,
        source_proxy=source_proxy,
        parser_blocks=tuple(block.to_dict() for block in parser_page.blocks),
        parser_sections=tuple(
            section
            for section in _sequence_from_mapping(structured_data, "sections")
            if _section_touches_page(section, result.page_number)
        ),
        parser_entities=_entities_for_page(structured_data, result.page_number),
        parser_chunks=tuple(chunk.to_dict() for chunk in chunks),
        review_checklist=default_visual_review_checklist(
            _page_review_id_from_result(result)
        ),
    )


def _evaluate_page_metrics(
    *,
    plan_page: SourceAccuracyPlanPage,
    source_proxy: Mapping[str, object],
    parser_page: Page,
    parser_text: str,
    structured_data: Mapping[str, object],
    selected_chunks: Sequence[Chunk],
) -> tuple[
    tuple[SourceAccuracyMetricResult, ...],
    list[dict[str, object]],
    tuple[EvaluationPolicyCorrection, ...],
    Mapping[str, int],
]:
    findings: list[dict[str, object]] = []
    corrections: list[EvaluationPolicyCorrection] = []
    metrics: list[SourceAccuracyMetricResult] = []
    source_text = str(source_proxy.get("text", ""))
    metrics.extend(
        _text_fidelity_metrics(
            plan_page,
            source_text,
            parser_text,
            findings,
            corrections,
        )
    )
    metrics.extend(
        _reading_order_metrics(plan_page, parser_page, findings, corrections)
    )
    metrics.extend(
        _provenance_metrics(
            plan_page,
            parser_page,
            structured_data,
            selected_chunks,
            findings,
        )
    )
    metrics.extend(_hierarchy_metrics(plan_page, structured_data, findings))
    metrics.extend(_entity_metrics(plan_page, structured_data, findings))
    chunk_metrics, eligibility_summary = _chunk_metrics(
        plan_page,
        parser_page,
        structured_data,
        selected_chunks,
        findings,
        corrections,
    )
    metrics.extend(chunk_metrics)
    metrics.extend(_sr22_metrics(plan_page, source_proxy, findings))
    return tuple(metrics), findings, tuple(corrections), eligibility_summary


def _text_fidelity_metrics(
    plan_page: SourceAccuracyPlanPage,
    source_text: str,
    parser_text: str,
    findings: list[dict[str, object]],
    corrections: list[EvaluationPolicyCorrection],
) -> tuple[SourceAccuracyMetricResult, ...]:
    source_chars = len(source_text.strip())
    parser_chars = len(parser_text.strip())
    source_lines = _normalized_lines(source_text)
    parser_lines = _normalized_lines(parser_text)
    coverage = 1.0 if source_chars == 0 else min(parser_chars / source_chars, 1.0)
    missing_lines = [line for line in source_lines if line not in parser_lines]
    source_duplicate_lines = _duplicate_lines(source_lines)
    parser_duplicate_lines = _duplicate_lines(parser_lines)
    source_duplicate_set = set(source_duplicate_lines)
    parser_only_duplicates = tuple(
        line for line in parser_duplicate_lines if line not in source_duplicate_set
    )
    source_symbols = _unicode_symbols(source_text)
    parser_symbols = _unicode_symbols(parser_text)
    symbol_loss = sorted(source_symbols - parser_symbols)
    coverage_status = STATUS_PASS
    if source_chars > 0 and coverage < 0.95:
        coverage_status = STATUS_FAIL
        findings.append(
            _finding_spec(
                category="PARSER_DEFECT",
                severity="major",
                code="TEXT_COVERAGE_LOW",
                message="Parser text coverage is below the automated threshold.",
                metric_name="raw_character_coverage",
            )
        )
    if missing_lines:
        coverage_status = STATUS_FAIL
        findings.append(
            _finding_spec(
                category="PARSER_DEFECT",
                severity="major",
                code="SOURCE_LINES_MISSING",
                message="One or more source-proxy lines are not represented.",
                metric_name="missing_line_count",
                details={"missing_line_count": len(missing_lines)},
            )
        )
    duplicate_status = STATUS_PASS
    if parser_only_duplicates:
        duplicate_status = STATUS_FAIL
        findings.append(
            _finding_spec(
                category="PARSER_DEFECT",
                severity="major",
                code="DUPLICATE_TEXT_LINES",
                message=(
                    "Parser text includes duplicate normalized lines not present "
                    "in the source proxy."
                ),
                metric_name="duplicate_line_count",
                details={
                    "duplicate_line_count": len(parser_duplicate_lines),
                    "parser_only_duplicate_count": len(parser_only_duplicates),
                    "corrected_policy_disposition": "parser_defect",
                    "corrected_metric_status": STATUS_FAIL,
                    "correction_reason_code": "PARSER_ONLY_DUPLICATION_REMAINS_FAIL",
                },
            )
        )
    elif parser_duplicate_lines:
        duplicate_status = STATUS_REVIEW
        findings.append(
            _finding_spec(
                category="SOURCE_PROXY_LIMITATION",
                severity="minor",
                code="DUPLICATE_TEXT_LINES",
                message=(
                    "Duplicate normalized lines are present in the source proxy; "
                    "visual review is required before treating them as parser defects."
                ),
                metric_name="duplicate_line_count",
                requires_manual_review=True,
                details={
                    "duplicate_line_count": len(parser_duplicate_lines),
                    "source_proxy_duplicate_count": len(source_duplicate_lines),
                    "corrected_policy_disposition": "source_proxy_review",
                    "corrected_metric_status": STATUS_REVIEW,
                    "correction_reason_code": "SOURCE_PROXY_DUPLICATION_RECLASSIFIED",
                },
            )
        )
        corrections.append(
            EvaluationPolicyCorrection(
                original_finding_code="DUPLICATE_TEXT_LINES",
                corrected_policy_disposition="source_proxy_review",
                corrected_metric_status=STATUS_REVIEW,
                correction_reason_code="SOURCE_PROXY_DUPLICATION_RECLASSIFIED",
                message=(
                    "Duplicate-line findings no longer change raw text "
                    "coverage status when the source proxy also contains duplicates."
                ),
                metric_name="duplicate_line_count",
            )
        )
        corrections.append(
            EvaluationPolicyCorrection(
                original_finding_code="RAW_CHARACTER_COVERAGE_STATUS_FAIL",
                corrected_policy_disposition="coverage_metric_independent",
                corrected_metric_status=coverage_status,
                correction_reason_code="DUPLICATION_DECOUPLED_FROM_COVERAGE",
                message=(
                    "Raw character coverage status is based on coverage, "
                    "missing lines, native-text availability, and symbol loss only."
                ),
                metric_name="raw_character_coverage",
            )
        )
    if symbol_loss:
        coverage_status = STATUS_FAIL
        findings.append(
            _finding_spec(
                category="PARSER_DEFECT",
                severity="major",
                code="UNICODE_SYMBOL_LOSS",
                message="Unicode or mathematical symbols are missing from parser text.",
                metric_name="unicode_symbol_loss_count",
                details={"unicode_symbol_loss_count": len(symbol_loss)},
            )
        )
    if source_chars == 0:
        coverage_status = STATUS_REVIEW
        findings.append(
            _finding_spec(
                category="OCR_OR_EXTRACTION_LIMITATION",
                severity="major",
                code="NO_NATIVE_TEXT_PROXY",
                message=(
                    "Source page has no direct native text proxy; OCR is out of scope."
                ),
                metric_name="raw_character_coverage",
                requires_manual_review=True,
            )
        )
    line_coverage = (
        1.0
        if not source_lines
        else (len(source_lines) - len(missing_lines)) / len(source_lines)
    )
    return (
        SourceAccuracyMetricResult(
            name="raw_character_coverage",
            status=coverage_status,
            value=round(coverage, 6),
            threshold=0.95,
            unit="ratio",
            message="Parser text compared with automated source text proxy.",
            details={
                "source_characters": source_chars,
                "parser_characters": parser_chars,
                "metric_independent_of_duplicate_line_count": True,
            },
        ),
        SourceAccuracyMetricResult(
            name="normalized_line_coverage",
            status=STATUS_PASS if line_coverage >= 1.0 else STATUS_FAIL,
            value=round(line_coverage, 6),
            threshold=1.0,
            unit="ratio",
        ),
        SourceAccuracyMetricResult(
            name="missing_line_count",
            status=STATUS_PASS if not missing_lines else STATUS_FAIL,
            value=len(missing_lines),
            threshold=0,
            unit="lines",
        ),
        SourceAccuracyMetricResult(
            name="duplicate_line_count",
            status=duplicate_status,
            value=len(parser_duplicate_lines),
            threshold=0,
            unit="lines",
            details={
                "source_proxy_duplicate_count": len(source_duplicate_lines),
                "parser_only_duplicate_count": len(parser_only_duplicates),
            },
        ),
        SourceAccuracyMetricResult(
            name="unicode_symbol_loss_count",
            status=STATUS_PASS if not symbol_loss else STATUS_FAIL,
            value=len(symbol_loss),
            threshold=0,
            unit="symbols",
        ),
        SourceAccuracyMetricResult(
            name="table_cell_accuracy",
            status=STATUS_NOT_MEASURABLE
            if "table" in plan_page.evaluation_roles
            else STATUS_NOT_APPLICABLE,
            value="not_measurable",
            message="Current parser does not reconstruct table cells.",
        ),
        SourceAccuracyMetricResult(
            name="source_page_visual_accuracy",
            status=STATUS_NOT_MEASURABLE,
            value="pending_human_visual_review",
            message="Visual source accuracy requires human review.",
        ),
    )


def _reading_order_metrics(
    plan_page: SourceAccuracyPlanPage,
    parser_page: Page,
    findings: list[dict[str, object]],
    corrections: list[EvaluationPolicyCorrection],
) -> tuple[SourceAccuracyMetricResult, ...]:
    text_blocks = [
        block for block in parser_page.text_blocks if block.source and block.source.bbox
    ]
    inversions = 0
    previous_y = None
    for block in text_blocks:
        assert block.source is not None
        assert block.source.bbox is not None
        y0 = block.source.bbox.y0
        if previous_y is not None and y0 + 2.0 < previous_y:
            inversions += 1
        previous_y = y0
    status = STATUS_PASS if inversions == 0 else STATUS_REVIEW
    if inversions:
        findings.append(
            _finding_spec(
                category="MANUAL_REVIEW_REQUIRED",
                severity="minor",
                code="READING_ORDER_INVERSION",
                message=(
                    "Parser text-block order has coordinate inversions; visual "
                    "review is required before treating this as a parser defect."
                ),
                metric_name="order_inversion_count",
                requires_manual_review=True,
                details={
                    "inversions": inversions,
                    "corrected_policy_disposition": "visual_review_required",
                    "corrected_metric_status": STATUS_REVIEW,
                    "correction_reason_code": "READING_ORDER_VISUAL_REVIEW_REQUIRED",
                },
            )
        )
        corrections.append(
            EvaluationPolicyCorrection(
                original_finding_code="READING_ORDER_INVERSION",
                corrected_policy_disposition="visual_review_required",
                corrected_metric_status=STATUS_REVIEW,
                correction_reason_code="READING_ORDER_VISUAL_REVIEW_REQUIRED",
                message=(
                    "Coordinate-order inversions are not automatic parser "
                    "failures under policy v2."
                ),
                metric_name="order_inversion_count",
            )
        )
    if _needs_visual_order_review(plan_page):
        findings.append(
            _finding_spec(
                category="MANUAL_REVIEW_REQUIRED",
                severity="informational",
                code="READING_ORDER_VISUAL_REVIEW_REQUIRED",
                message="Complex or multi-column reading order requires visual review.",
                metric_name="order_consistency_ratio",
                requires_manual_review=True,
            )
        )
    return (
        SourceAccuracyMetricResult(
            name="order_consistency_ratio",
            status=status,
            value=1.0 if inversions == 0 else 0.0,
            threshold=1.0,
            unit="ratio",
            details={"visual_confirmation_required": inversions > 0},
        ),
        SourceAccuracyMetricResult(
            name="order_inversion_count",
            status=status,
            value=inversions,
            threshold=0,
            unit="inversions",
            details={"visual_confirmation_required": inversions > 0},
        ),
        SourceAccuracyMetricResult(
            name="multi_column_visual_review",
            status=(
                STATUS_REVIEW
                if _needs_visual_order_review(plan_page)
                else STATUS_NOT_APPLICABLE
            ),
            value=_needs_visual_order_review(plan_page),
            message="Two-column and complex pages are not auto-approved.",
        ),
    )


def _provenance_metrics(
    plan_page: SourceAccuracyPlanPage,
    parser_page: Page,
    structured_data: Mapping[str, object],
    selected_chunks: Sequence[Chunk],
    findings: list[dict[str, object]],
) -> tuple[SourceAccuracyMetricResult, ...]:
    wrong_block_pages = [
        block.id
        for block in parser_page.blocks
        if block.source is not None
        and block.source.page_number is not None
        and block.source.page_number != plan_page.page_number
    ]
    wrong_chunk_pages = [
        chunk.id
        for chunk in selected_chunks
        if plan_page.page_number not in chunk.source_page_numbers
    ]
    wrong_section_spans = _wrong_section_spans(
        structured_data,
        plan_page.page_number,
    )
    failure_count = (
        len(wrong_block_pages) + len(wrong_chunk_pages) + len(wrong_section_spans)
    )
    if failure_count:
        findings.append(
            _finding_spec(
                category="PARSER_DEFECT",
                severity="critical",
                code="PAGE_PROVENANCE_CONTRADICTION",
                message="Parser evidence contains contradictory page provenance.",
                metric_name="page_provenance_consistency",
                details={"failure_count": failure_count},
            )
        )
    return (
        SourceAccuracyMetricResult(
            name="page_provenance_consistency",
            status=STATUS_PASS if failure_count == 0 else STATUS_FAIL,
            value=1.0 if failure_count == 0 else 0.0,
            threshold=1.0,
            unit="ratio",
        ),
        SourceAccuracyMetricResult(
            name="printed_page_label_match",
            status=STATUS_PASS
            if plan_page.printed_page_label is not None
            else STATUS_NOT_APPLICABLE,
            value=plan_page.printed_page_label is not None,
            message="Missing optional printed page labels are not failures.",
        ),
    )


def _hierarchy_metrics(
    plan_page: SourceAccuracyPlanPage,
    structured_data: Mapping[str, object],
    findings: list[dict[str, object]],
) -> tuple[SourceAccuracyMetricResult, ...]:
    sections = _sequence_from_mapping(structured_data, "sections")
    section_ids = {str(section.get("section_id")) for section in sections}
    unknown_parent_count = sum(
        1
        for section in sections
        if section.get("parent_section_id") is not None
        and str(section.get("parent_section_id")) not in section_ids
    )
    if unknown_parent_count:
        findings.append(
            _finding_spec(
                category="PARSER_DEFECT",
                severity="major",
                code="UNKNOWN_SECTION_PARENT",
                message="Structured section hierarchy references an unknown parent.",
                metric_name="section_parent_integrity",
            )
        )
    if "section_hierarchy" in plan_page.evaluation_roles:
        findings.append(
            _finding_spec(
                category="MANUAL_REVIEW_REQUIRED",
                severity="informational",
                code="HIERARCHY_VISUAL_REVIEW_REQUIRED",
                message="Heading hierarchy correctness requires visual review.",
                metric_name="section_hierarchy_visual_review",
                requires_manual_review=True,
            )
        )
    return (
        SourceAccuracyMetricResult(
            name="section_parent_integrity",
            status=STATUS_PASS if unknown_parent_count == 0 else STATUS_FAIL,
            value=unknown_parent_count,
            threshold=0,
            unit="bad_parent_refs",
        ),
        SourceAccuracyMetricResult(
            name="section_hierarchy_visual_review",
            status=STATUS_REVIEW
            if "section_hierarchy" in plan_page.evaluation_roles
            else STATUS_NOT_APPLICABLE,
            value=(
                "pending"
                if "section_hierarchy" in plan_page.evaluation_roles
                else "not_applicable"
            ),
        ),
    )


def _entity_metrics(
    plan_page: SourceAccuracyPlanPage,
    structured_data: Mapping[str, object],
    findings: list[dict[str, object]],
) -> tuple[SourceAccuracyMetricResult, ...]:
    page_number = plan_page.page_number
    tables = _entities_on_page(structured_data, "tables", page_number)
    figures = _entities_on_page(structured_data, "figures", page_number)
    equations = _entities_on_page(structured_data, "equations", page_number)
    admonitions = _entities_on_page(structured_data, "admonitions", page_number)
    references = _entities_on_page(structured_data, "cross_references", page_number)
    metrics = [
        _entity_metric("table_evidence_count", tables, "table", plan_page, findings),
        _entity_metric(
            "figure_caption_evidence_count",
            figures,
            "figure_caption",
            plan_page,
            findings,
        ),
        _entity_metric(
            "equation_evidence_count",
            equations,
            "equation",
            plan_page,
            findings,
        ),
        _entity_metric(
            "admonition_evidence_count",
            admonitions,
            "admonition",
            plan_page,
            findings,
        ),
        _entity_metric(
            "cross_reference_evidence_count",
            references,
            "cross_reference",
            plan_page,
            findings,
        ),
        SourceAccuracyMetricResult(
            name="figure_content_accuracy",
            status=STATUS_NOT_MEASURABLE
            if "figure_caption" in plan_page.evaluation_roles
            else STATUS_NOT_APPLICABLE,
            value="not_measurable",
            message="Figure visual content is not interpreted.",
        ),
    ]
    if tables and "table" in plan_page.evaluation_roles:
        findings.append(
            _finding_spec(
                category="CONTRACT_LIMITATION",
                severity="minor",
                code="TABLE_CANDIDATE_ONLY",
                message=(
                    "Table evidence is candidate-level; cells are not reconstructed."
                ),
                metric_name="table_cell_accuracy",
                requires_manual_review=True,
            )
        )
    if equations:
        findings.append(
            _finding_spec(
                category="MANUAL_REVIEW_REQUIRED",
                severity="informational",
                code="EQUATION_VISUAL_REVIEW_REQUIRED",
                message="Equation visual layout requires human review.",
                metric_name="equation_evidence_count",
                requires_manual_review=True,
            )
        )
    if figures:
        findings.append(
            _finding_spec(
                category="MANUAL_REVIEW_REQUIRED",
                severity="informational",
                code="FIGURE_CAPTION_VISUAL_REVIEW_REQUIRED",
                message="Figure-caption association requires human review.",
                metric_name="figure_caption_evidence_count",
                requires_manual_review=True,
            )
        )
    return tuple(metrics)


def _entity_metric(
    name: str,
    entities: Sequence[Mapping[str, object]],
    role: str,
    plan_page: SourceAccuracyPlanPage,
    findings: list[dict[str, object]],
) -> SourceAccuracyMetricResult:
    expected = role in plan_page.evaluation_roles
    if expected and not entities:
        findings.append(
            _finding_spec(
                category="MANUAL_REVIEW_REQUIRED",
                severity="minor",
                code=f"{role.upper()}_EVIDENCE_NOT_AUTOMATED",
                message="Expected entity role has no automated root entity evidence.",
                metric_name=name,
                requires_manual_review=True,
            )
        )
        return SourceAccuracyMetricResult(
            name=name,
            status=STATUS_REVIEW,
            value=0,
            threshold=1,
            unit="entities",
        )
    return SourceAccuracyMetricResult(
        name=name,
        status=STATUS_PASS if entities else STATUS_NOT_APPLICABLE,
        value=len(entities),
        threshold=1 if expected else None,
        unit="entities",
    )


def _chunk_metrics(
    plan_page: SourceAccuracyPlanPage,
    parser_page: Page,
    structured_data: Mapping[str, object],
    selected_chunks: Sequence[Chunk],
    findings: list[dict[str, object]],
    corrections: list[EvaluationPolicyCorrection],
) -> tuple[tuple[SourceAccuracyMetricResult, ...], Mapping[str, int]]:
    semantic_blocks = list(get_semantic_blocks_for_page(parser_page))
    entities = _entities_for_page(structured_data, plan_page.page_number)
    eligibilities = tuple(
        classify_source_block_chunk_eligibility(
            block,
            selected_chunks,
            entities=entities,
            policy=SourceBlockEligibilityPolicy(require_heading_chunks=False),
        )
        for block in semantic_blocks
    )
    eligible_ids = eligible_source_block_ids(eligibilities)
    covered_ids = covered_source_block_ids(eligibilities)
    missing = missing_required_source_block_ids(eligibilities)
    eligibility_summary = summarize_source_block_eligibility(eligibilities)
    v1_semantic_ids = {
        block.id for block in semantic_blocks if block.id and _block_text(block)
    }
    v1_chunk_ids = {
        block_id for chunk in selected_chunks for block_id in chunk.source_block_ids
    }
    v1_missing = sorted(v1_semantic_ids - v1_chunk_ids)
    if missing:
        findings.append(
            _finding_spec(
                category="PARSER_DEFECT",
                severity="major",
                code="CHUNK_SOURCE_COVERAGE_GAP",
                message="Selected-page semantic blocks are missing from chunks.",
                metric_name="chunk_source_block_coverage",
                details={
                    "missing_count": len(missing),
                    "eligible_source_block_count": len(eligible_ids),
                    "covered_source_block_count": len(covered_ids),
                    "eligibility_summary": eligibility_summary,
                    "corrected_policy_disposition": "parser_or_chunk_gap",
                    "corrected_metric_status": STATUS_FAIL,
                    "correction_reason_code": "REQUIRED_DIRECT_CHUNK_MISSING",
                },
            )
        )
    elif v1_missing:
        corrections.append(
            EvaluationPolicyCorrection(
                original_finding_code="CHUNK_SOURCE_COVERAGE_GAP",
                corrected_policy_disposition="not_a_required_direct_chunk_gap",
                corrected_metric_status=STATUS_PASS,
                correction_reason_code="SOURCE_BLOCK_ELIGIBILITY_RECLASSIFIED",
                message=(
                    "Policy v2 excludes heading/blank/non-emitting blocks and "
                    "accepts entity-derived chunk replacements."
                ),
                metric_name="chunk_source_block_coverage",
            )
        )
    coverage = 1.0 if not eligible_ids else len(covered_ids) / len(eligible_ids)
    section_paths = {
        chunk.metadata.get("section_path")
        for chunk in selected_chunks
        if chunk.metadata.get("section_path")
    }
    section_crossing = len(section_paths) > 1
    if section_crossing:
        findings.append(
            _finding_spec(
                category="MANUAL_REVIEW_REQUIRED",
                severity="minor",
                code="CHUNK_SECTION_CROSSING_REVIEW",
                message="Selected-page chunks include multiple section contexts.",
                metric_name="chunk_section_coherence",
                requires_manual_review=True,
            )
        )
    return (
        (
            SourceAccuracyMetricResult(
                name="chunk_source_block_coverage",
                status=STATUS_PASS if coverage >= 1.0 else STATUS_FAIL,
                value=round(coverage, 6),
                threshold=1.0,
                unit="ratio",
                details={
                    "eligible_source_block_count": len(eligible_ids),
                    "covered_source_block_count": len(covered_ids),
                    "missing_source_block_count": len(missing),
                    "eligibility_summary": eligibility_summary,
                },
            ),
            SourceAccuracyMetricResult(
                name="chunk_count",
                status=STATUS_PASS if selected_chunks else STATUS_REVIEW,
                value=len(selected_chunks),
                threshold=1,
                unit="chunks",
            ),
            SourceAccuracyMetricResult(
                name="chunk_section_coherence",
                status=STATUS_REVIEW if section_crossing else STATUS_PASS,
                value=not section_crossing,
            ),
            SourceAccuracyMetricResult(
                name="deterministic_ids",
                status=STATUS_PASS,
                value=all(chunk.id.startswith("chunk-") for chunk in selected_chunks),
            ),
        ),
        eligibility_summary,
    )


def _sr22_metrics(
    plan_page: SourceAccuracyPlanPage,
    source_proxy: Mapping[str, object],
    findings: list[dict[str, object]],
) -> tuple[SourceAccuracyMetricResult, ...]:
    if plan_page.document_key != SR22_DOCUMENT_KEY:
        return ()
    classification = str(source_proxy.get("text_mode", "uncertain"))
    status = STATUS_PASS if classification == "native_text_usable" else STATUS_REVIEW
    if classification != "native_text_usable":
        findings.append(
            _finding_spec(
                category="OCR_OR_EXTRACTION_LIMITATION",
                severity="major" if classification == "image_dominant" else "minor",
                code="SR22_NATIVE_TEXT_LIMITATION",
                message="SR22 selected page has limited native-text proxy evidence.",
                metric_name="sr22_native_text_classification",
                requires_manual_review=True,
                details={"classification": classification},
            )
        )
    return (
        SourceAccuracyMetricResult(
            name="sr22_native_text_classification",
            status=status,
            value=classification,
        ),
    )


def _build_findings(
    plan_page: SourceAccuracyPlanPage,
    specs: Sequence[Mapping[str, object]],
) -> tuple[SourceAccuracyFinding, ...]:
    findings: list[SourceAccuracyFinding] = []
    for index, spec in enumerate(specs, start=1):
        category = str(spec["category"])
        severity = str(spec["severity"])
        if category not in FINDING_CATEGORIES:
            raise ValueError(f"Unsupported finding category: {category}")
        if severity not in SEVERITIES:
            raise ValueError(f"Unsupported finding severity: {severity}")
        findings.append(
            SourceAccuracyFinding(
                finding_id=(
                    f"{plan_page.document_key}:p{plan_page.pdf_page_index}:"
                    f"finding:{index:03d}"
                ),
                document_key=plan_page.document_key,
                pdf_page_index=plan_page.pdf_page_index,
                page_number=plan_page.page_number,
                category=category,
                severity=severity,
                code=str(spec["code"]),
                message=str(spec["message"]),
                source_entity_ids=_string_tuple(spec.get("source_entity_ids")),
                parser_entity_ids=_string_tuple(spec.get("parser_entity_ids")),
                metric_name=_optional_string(spec.get("metric_name")),
                requires_manual_review=bool(spec.get("requires_manual_review", False)),
                details=_details_mapping(spec.get("details")),
            )
        )
    return tuple(findings)


def _visual_review_state(
    plan_page: SourceAccuracyPlanPage,
    checklist: Mapping[str, object] | None,
    *,
    start_sequence: int,
) -> tuple[str, str, tuple[SourceAccuracyFinding, ...]]:
    checklist_data = (
        validate_visual_review_checklist(checklist)
        if checklist is not None
        else default_visual_review_checklist(_page_review_id(plan_page))
    )
    checks = _mapping(checklist_data["checks"])
    values = [str(value) for value in checks.values()]
    pending = any(value == "pending" for value in values)
    failed = any(value == STATUS_FAIL for value in values)
    reviewed = not pending
    status = "completed" if reviewed else "pending"
    if failed:
        outcome = FAIL
    elif pending or any(value == STATUS_REVIEW for value in values):
        outcome = REVIEW
    else:
        outcome = PASS
    if status == "completed":
        return status, outcome, ()
    finding = SourceAccuracyFinding(
        finding_id=(
            f"{plan_page.document_key}:p{plan_page.pdf_page_index}:"
            f"finding:{start_sequence:03d}"
        ),
        document_key=plan_page.document_key,
        pdf_page_index=plan_page.pdf_page_index,
        page_number=plan_page.page_number,
        category="MANUAL_REVIEW_REQUIRED",
        severity="informational",
        code="VISUAL_REVIEW_PENDING",
        message="Human visual review is pending; final PASS is not allowed.",
        metric_name="source_page_visual_accuracy",
        requires_manual_review=True,
    )
    return status, outcome, (finding,)


def validate_visual_review_checklist(
    checklist: Mapping[str, object],
) -> dict[str, object]:
    """Validate one explicit local visual-review checklist object."""
    allowed_top = {"page_id", "checks", "reviewer_notes"}
    unknown_top = set(checklist) - allowed_top
    if unknown_top:
        raise ValueError(f"Unknown checklist fields: {sorted(unknown_top)}")
    page_id = _required_string(checklist, "page_id", 0)
    checks = _mapping(checklist.get("checks"))
    unknown_checks = set(checks) - set(VISUAL_CHECK_FIELDS)
    if unknown_checks:
        raise ValueError(f"Unknown visual checks: {sorted(unknown_checks)}")
    normalized_checks: dict[str, str] = {}
    for field_name in VISUAL_CHECK_FIELDS:
        value = str(checks.get(field_name, "pending"))
        if value not in VISUAL_CHECK_VALUES:
            raise ValueError(f"Invalid checklist value for {field_name}: {value}")
        normalized_checks[field_name] = value
    notes = _optional_string(checklist.get("reviewer_notes")) or ""
    return {"page_id": page_id, "checks": normalized_checks, "reviewer_notes": notes}


def _pilot_result(
    page_results: tuple[SourceAccuracyPageResult, ...],
) -> SourceAccuracyPilotResult:
    final_counts = Counter(page.final_page_outcome for page in page_results)
    automated_counts = Counter(page.automated_outcome for page in page_results)
    if final_counts.get(FAIL, 0):
        outcome = FAIL
    elif final_counts.get(REVIEW, 0):
        outcome = REVIEW
    else:
        outcome = PASS
    findings = [finding for page in page_results for finding in page.findings]
    correction_counts = Counter(
        correction.correction_reason_code
        for page in page_results
        for correction in page.policy_corrections
    )
    metric_summary: dict[str, Counter[str]] = {}
    for page in page_results:
        for metric in page.metrics:
            metric_summary.setdefault(metric.name, Counter())[metric.status] += 1
    by_document: dict[str, dict[str, object]] = {}
    for page in page_results:
        summary = by_document.setdefault(
            page.document_key,
            {
                "filename": page.filename,
                "p0_pages": [],
                "final_outcomes": Counter(),
                "automated_outcomes": Counter(),
                "visual_reviews": Counter(),
                "finding_count": 0,
            },
        )
        p0_pages = summary["p0_pages"]
        assert isinstance(p0_pages, list)
        p0_pages.append(page.page_number)
        final_outcomes = summary["final_outcomes"]
        automated_outcomes = summary["automated_outcomes"]
        visual_reviews = summary["visual_reviews"]
        assert isinstance(final_outcomes, Counter)
        assert isinstance(automated_outcomes, Counter)
        assert isinstance(visual_reviews, Counter)
        final_outcomes[page.final_page_outcome] += 1
        automated_outcomes[page.automated_outcome] += 1
        visual_reviews[page.visual_review_status] += 1
        finding_count = summary["finding_count"]
        assert isinstance(finding_count, int)
        summary["finding_count"] = finding_count + len(page.findings)
    document_summaries = {
        key: {
            "filename": value["filename"],
            "p0_pages": value["p0_pages"],
            "final_outcomes": _counter_dict(value["final_outcomes"]),
            "automated_outcomes": _counter_dict(value["automated_outcomes"]),
            "visual_reviews": _counter_dict(value["visual_reviews"]),
            "finding_count": value["finding_count"],
        }
        for key, value in sorted(by_document.items())
    }
    limitations = (
        (
            "Automated source proxies use PDF text extraction and are not "
            "independent visual ground truth."
        ),
        "Human visual review is required before any page can receive final PASS.",
        "Only approved P0 representative pages were scored.",
        "Full-document accuracy was not evaluated.",
        "OCR was not run and OCR accuracy was not evaluated.",
        "Current table cell accuracy and figure content accuracy are not measurable.",
        (
            "Existing parser behavior, chunking, and StructuredDocument output "
            "were not changed."
        ),
    )
    return SourceAccuracyPilotResult(
        outcome=outcome,
        evaluation_scope=EVALUATION_SCOPE,
        document_count=len({page.document_key for page in page_results}),
        page_count=len(page_results),
        page_results=tuple(
            sorted(
                page_results,
                key=lambda page: (page.document_key, page.pdf_page_index),
            )
        ),
        finding_counts=dict(Counter(finding.code for finding in findings)),
        category_counts=dict(Counter(finding.category for finding in findings)),
        severity_counts=dict(Counter(finding.severity for finding in findings)),
        page_outcome_counts=dict(final_counts),
        automated_outcome_counts=dict(automated_counts),
        policy_correction_counts=dict(correction_counts),
        metric_summaries={
            key: dict(value) for key, value in sorted(metric_summary.items())
        },
        visual_review_completion_counts=dict(
            Counter(page.visual_review_status for page in page_results)
        ),
        document_summaries=document_summaries,
        limitations=limitations,
        summary=(
            f"Evaluated {len(page_results)} approved P0 pages; aggregate "
            f"outcome is {outcome}."
        ),
    )


def _missing_source_results(
    source_path: Path,
    pages: Sequence[SourceAccuracyPlanPage],
    context_radius: int,
) -> list[SourceAccuracyPageResult]:
    return [
        _blocking_page_result(
            page,
            code="SOURCE_FILE_MISSING",
            message=f"Approved source PDF is missing: {source_path.name}",
            context_radius=context_radius,
        )
        for page in pages
    ]


def _blocking_page_result(
    plan_page: SourceAccuracyPlanPage,
    *,
    code: str,
    message: str,
    context_radius: int,
) -> SourceAccuracyPageResult:
    finding = SourceAccuracyFinding(
        finding_id=f"{plan_page.document_key}:p{plan_page.pdf_page_index}:finding:001",
        document_key=plan_page.document_key,
        pdf_page_index=plan_page.pdf_page_index,
        page_number=plan_page.page_number,
        category="EVALUATION_FRAMEWORK_ISSUE",
        severity="critical",
        code=code,
        message=message,
        requires_manual_review=True,
    )
    metric = SourceAccuracyMetricResult(
        name="page_execution",
        status=STATUS_FAIL,
        value=False,
        message=message,
    )
    return SourceAccuracyPageResult(
        document_key=plan_page.document_key,
        filename=plan_page.filename,
        pdf_page_index=plan_page.pdf_page_index,
        page_number=plan_page.page_number,
        printed_page_label=plan_page.printed_page_label,
        evaluation_roles=plan_page.evaluation_roles,
        automated_outcome=FAIL,
        visual_review_status="pending",
        visual_review_outcome=REVIEW,
        final_page_outcome=FAIL,
        metrics=(metric,),
        findings=(finding,),
        parser_counts={},
        source_proxy_counts={},
        review_artifact_labels=_artifact_labels(plan_page),
        context_pages=(plan_page.page_number,),
        operational_full_document_parse=False,
    )


def _outcome_from_metrics_and_findings(
    metrics: Sequence[SourceAccuracyMetricResult],
    findings: Sequence[SourceAccuracyFinding],
) -> str:
    if any(metric.status == STATUS_FAIL for metric in metrics):
        return FAIL
    if any(
        finding.severity in {"critical", "major"}
        and finding.category == "PARSER_DEFECT"
        for finding in findings
    ):
        return FAIL
    if any(
        metric.status in {STATUS_REVIEW, STATUS_NOT_MEASURABLE}
        and metric.name != "source_page_visual_accuracy"
        for metric in metrics
    ):
        return REVIEW
    if any(finding.requires_manual_review for finding in findings):
        return REVIEW
    return PASS


def _final_page_outcome(
    *,
    automated_outcome: str,
    visual_status: str,
    visual_outcome: str,
    findings: Sequence[SourceAccuracyFinding],
) -> str:
    if automated_outcome == FAIL or visual_outcome == FAIL:
        return FAIL
    if any(
        finding.severity in {"critical", "major"}
        and finding.category == "PARSER_DEFECT"
        for finding in findings
    ):
        return FAIL
    if visual_status != "completed":
        return REVIEW
    if automated_outcome == PASS and visual_outcome == PASS:
        return PASS
    return REVIEW


def _filter_plan(
    plan: Sequence[SourceAccuracyPlanPage],
    document_keys: Collection[str] | None,
) -> tuple[SourceAccuracyPlanPage, ...]:
    if document_keys is None:
        return tuple(plan)
    requested = set(document_keys)
    return tuple(page for page in plan if page.document_key in requested)


def _load_checklists_by_page_id(
    checklist_paths: Sequence[str | Path],
) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for path in checklist_paths:
        checklist = validate_visual_review_checklist(_load_json_object(path))
        result[str(checklist["page_id"])] = checklist
    return result


def _source_proxy_counts(
    source_proxy: Mapping[str, object],
) -> dict[str, int | str | bool]:
    return {
        "character_count": _int_value(source_proxy.get("character_count")),
        "word_count": _int_value(source_proxy.get("word_count")),
        "line_count": _int_value(source_proxy.get("line_count")),
        "text_block_count": len(_sequence_from_mapping(source_proxy, "text_blocks")),
        "image_count": _int_value(source_proxy.get("image_count")),
        "link_count": _int_value(source_proxy.get("link_count")),
        "annotation_count": _int_value(source_proxy.get("annotation_count")),
        "rotation": _int_value(source_proxy.get("rotation")),
        "text_mode": str(source_proxy.get("text_mode", "uncertain")),
        "source_hash_verified_locally": bool(source_proxy.get("source_sha256")),
    }


def _parser_counts(
    *,
    parser_page: Page,
    structured_data: Mapping[str, object],
    chunks: Sequence[Chunk],
    page_number: int,
) -> dict[str, int]:
    return {
        "text_blocks": len(parser_page.text_blocks),
        "blocks": len(parser_page.blocks),
        "semantic_blocks": len(get_semantic_blocks_for_page(parser_page)),
        "heading_blocks": _count_blocks(parser_page, "heading"),
        "table_blocks": _count_blocks(parser_page, "table")
        + _count_blocks(parser_page, "table_region"),
        "figure_blocks": _count_blocks(parser_page, "figure"),
        "formula_blocks": _count_blocks(parser_page, "formula"),
        "chunks": len(chunks),
        "structured_sections_on_page": len(
            [
                section
                for section in _sequence_from_mapping(structured_data, "sections")
                if _section_touches_page(section, page_number)
            ]
        ),
        "structured_tables_on_page": len(
            _entities_on_page(structured_data, "tables", page_number)
        ),
        "structured_figures_on_page": len(
            _entities_on_page(structured_data, "figures", page_number)
        ),
        "structured_equations_on_page": len(
            _entities_on_page(structured_data, "equations", page_number)
        ),
        "structured_admonitions_on_page": len(
            _entities_on_page(structured_data, "admonitions", page_number)
        ),
        "structured_cross_references_on_page": len(
            _entities_on_page(structured_data, "cross_references", page_number)
        ),
    }


def _count_blocks(page: Page, block_type: str) -> int:
    return sum(1 for block in page.blocks if block.block_type == block_type)


def _entities_for_page(
    structured_data: Mapping[str, object],
    page_number: int,
) -> dict[str, object]:
    return {
        "tables": _entities_on_page(structured_data, "tables", page_number),
        "figures": _entities_on_page(structured_data, "figures", page_number),
        "equations": _entities_on_page(structured_data, "equations", page_number),
        "admonitions": _entities_on_page(
            structured_data,
            "admonitions",
            page_number,
        ),
        "cross_references": _entities_on_page(
            structured_data,
            "cross_references",
            page_number,
        ),
    }


def _entities_on_page(
    structured_data: Mapping[str, object],
    field_name: str,
    page_number: int,
) -> tuple[Mapping[str, object], ...]:
    return tuple(
        item
        for item in _sequence_from_mapping(structured_data, field_name)
        if _entity_touches_page(item, page_number)
    )


def _entity_touches_page(entity: Mapping[str, object], page_number: int) -> bool:
    page_refs = entity.get("page_refs")
    if isinstance(page_refs, Sequence) and not isinstance(page_refs, str):
        refs = [int(value) for value in page_refs if isinstance(value, int)]
        return page_number in refs
    source_span = entity.get("source_span")
    if isinstance(source_span, Mapping):
        return _span_touches_page(source_span, page_number)
    return False


def _section_touches_page(section: Mapping[str, object], page_number: int) -> bool:
    source_span = section.get("source_span")
    return isinstance(source_span, Mapping) and _span_touches_page(
        source_span,
        page_number,
    )


def _span_touches_page(span: Mapping[str, object], page_number: int) -> bool:
    start = span.get("page_start")
    end = span.get("page_end")
    if not isinstance(start, int) or not isinstance(end, int):
        return False
    return start <= page_number <= end


def _wrong_section_spans(
    structured_data: Mapping[str, object],
    page_number: int,
) -> tuple[str, ...]:
    wrong: list[str] = []
    for block in _sequence_from_mapping(structured_data, "blocks"):
        if block.get("page_number") != page_number:
            continue
        section_id = block.get("section_id")
        if section_id is None:
            continue
        matching = [
            section
            for section in _sequence_from_mapping(structured_data, "sections")
            if section.get("section_id") == section_id
        ]
        if matching and not _section_touches_page(matching[0], page_number):
            wrong.append(str(block.get("block_id")))
    return tuple(wrong)


def _chunks_for_page(chunks: Sequence[Chunk], page_number: int) -> tuple[Chunk, ...]:
    return tuple(chunk for chunk in chunks if page_number in chunk.source_page_numbers)


def _page_parser_text(page: Page) -> str:
    return "\n".join(block.text or "" for block in page.text_blocks if block.text)


def _source_text_blocks(page: fitz.Page) -> tuple[dict[str, object], ...]:
    raw_blocks = page.get_text("blocks") or []
    blocks: list[dict[str, object]] = []
    for index, block in enumerate(raw_blocks):
        if not isinstance(block, Sequence) or len(block) < 5:
            continue
        text = str(block[4] or "")
        if not text.strip():
            continue
        blocks.append(
            {
                "source_block_id": f"source-block-{index + 1:04d}",
                "bbox": [
                    float(block[0]),
                    float(block[1]),
                    float(block[2]),
                    float(block[3]),
                ],
                "text": text,
            }
        )
    return tuple(blocks)


def _page_label(page: fitz.Page) -> str | None:
    try:
        label = page.get_label()
    except Exception:
        return None
    return _optional_string(label)


def _context_pages(
    page_number: int,
    page_count: int,
    context_radius: int,
) -> tuple[int, ...]:
    start = max(1, page_number - max(context_radius, 0))
    end = min(page_count, page_number + max(context_radius, 0))
    return tuple(range(start, end + 1))


def _artifact_labels(plan_page: SourceAccuracyPlanPage) -> tuple[str, ...]:
    base = f"{plan_page.document_key}/page_{plan_page.page_number}"
    return (
        f"{base}/page.png",
        f"{base}/source_proxy.json",
        f"{base}/parser_blocks.json",
        f"{base}/parser_sections.json",
        f"{base}/parser_entities.json",
        f"{base}/parser_chunks.json",
        f"{base}/review.html",
        f"{base}/review_checklist.json",
    )


def _page_review_id(plan_page: SourceAccuracyPlanPage) -> str:
    return f"{plan_page.document_key}:p{plan_page.pdf_page_index}"


def _page_review_id_from_result(result: SourceAccuracyPageResult) -> str:
    return f"{result.document_key}:p{result.pdf_page_index}"


def _sr22_text_classification(source_counts: Mapping[str, int | str | bool]) -> str:
    return str(source_counts.get("text_mode", "uncertain"))


def _needs_visual_order_review(plan_page: SourceAccuracyPlanPage) -> bool:
    return bool(
        {"reading_order", "multi_column", "mixed_layout", "rotated_page", "landscape"}
        & set(plan_page.evaluation_roles)
    )


def _normalized_lines(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFC", text).replace("\r\n", "\n")
    return tuple(
        " ".join(line.split())
        for line in normalized.splitlines()
        if " ".join(line.split())
    )


def _duplicate_lines(lines: Sequence[str]) -> tuple[str, ...]:
    counts = Counter(lines)
    return tuple(sorted(line for line, count in counts.items() if count > 1))


def _unicode_symbols(text: str) -> set[str]:
    return {
        char
        for char in text
        if ord(char) > 127 or unicodedata.category(char).startswith("S")
    }


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _block_text(block: Block) -> str:
    return block.normalized_text or block.text or ""


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_object(path: str | Path) -> dict[str, object]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _required_string(
    data: Mapping[str, object],
    key: str,
    index: int,
) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Plan entry {index} requires non-empty string {key}.")
    return value.strip()


def _required_filename(data: Mapping[str, object], index: int) -> str:
    value = _required_string(data, "filename", index)
    if PureWindowsPath(value).drive or "/" in value or "\\" in value:
        raise ValueError(f"Plan entry {index} filename must be a basename.")
    return value


def _required_int(data: Mapping[str, object], key: str, index: int) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Plan entry {index} requires integer {key}.")
    return value


def _optional_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError("Expected a sequence of strings.")
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Expected non-empty string values.")
        result.append(item.strip())
    return tuple(result)


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("Expected object mapping.")
    return value


def _details_mapping(value: object) -> Mapping[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("Finding details must be an object.")
    return dict(value)


def _sequence_from_mapping(
    data: Mapping[str, object],
    key: str,
) -> tuple[Mapping[str, object], ...]:
    value = data.get(key)
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _finding_spec(
    *,
    category: str,
    severity: str,
    code: str,
    message: str,
    metric_name: str | None = None,
    requires_manual_review: bool = False,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "category": category,
        "severity": severity,
        "code": code,
        "message": message,
        "metric_name": metric_name,
        "requires_manual_review": requires_manual_review,
        "details": dict(details or {}),
    }


def _metric_to_dict(metric: SourceAccuracyMetricResult) -> dict[str, object]:
    return {
        "name": metric.name,
        "status": metric.status,
        "value": metric.value,
        "threshold": metric.threshold,
        "unit": metric.unit,
        "message": metric.message,
        "details": dict(metric.details),
    }


def _finding_to_dict(finding: SourceAccuracyFinding) -> dict[str, object]:
    return {
        "finding_id": finding.finding_id,
        "document_key": finding.document_key,
        "pdf_page_index": finding.pdf_page_index,
        "page_number": finding.page_number,
        "category": finding.category,
        "severity": finding.severity,
        "code": finding.code,
        "message": finding.message,
        "source_entity_ids": list(finding.source_entity_ids),
        "parser_entity_ids": list(finding.parser_entity_ids),
        "metric_name": finding.metric_name,
        "requires_manual_review": finding.requires_manual_review,
        "details": dict(finding.details),
    }


def _policy_correction_to_dict(
    correction: EvaluationPolicyCorrection,
) -> dict[str, object]:
    return {
        "original_finding_code": correction.original_finding_code,
        "corrected_policy_disposition": correction.corrected_policy_disposition,
        "corrected_metric_status": correction.corrected_metric_status,
        "correction_reason_code": correction.correction_reason_code,
        "message": correction.message,
        "metric_name": correction.metric_name,
    }


def _mapping_line(mapping: Mapping[str, object]) -> str:
    if not mapping:
        return "`none`"
    items = ", ".join(f"{key}: {value}" for key, value in sorted(mapping.items()))
    return f"`{items}`"


def _int_value(value: object) -> int:
    return value if isinstance(value, int) else 0


def _counter_dict(value: object) -> dict[str, int]:
    if not isinstance(value, Counter):
        raise TypeError("Expected Counter summary.")
    return dict(value)


def _top_finding_codes(findings: Sequence[SourceAccuracyFinding]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(finding.code for finding in findings[:5]))


__all__ = [
    "AUTOMATED_SOURCE_PROXY",
    "EVALUATION_SCOPE",
    "FAIL",
    "FINDING_CATEGORIES",
    "HUMAN_VISUAL_REVIEW",
    "PASS",
    "REVIEW",
    "SEVERITIES",
    "SOURCE_ACCURACY_POLICY_NAME",
    "SOURCE_ACCURACY_POLICY_VERSION",
    "SOURCE_ACCURACY_PREVIOUS_POLICY_VERSION",
    "SOURCE_ACCURACY_RUN_TYPE",
    "SOURCE_ACCURACY_SCOPE",
    "SOURCE_ACCURACY_SUPERSEDES_POLICY_INTERPRETATION",
    "EvaluationPolicyCorrection",
    "LocalPageEvidence",
    "SourceAccuracyFinding",
    "SourceAccuracyMetricResult",
    "SourceAccuracyPageResult",
    "SourceAccuracyPilotResult",
    "SourceAccuracyPlanPage",
    "build_local_page_evidence",
    "classify_native_text_use",
    "collect_source_page_proxy",
    "default_visual_review_checklist",
    "evaluate_representative_page",
    "load_p0_source_accuracy_plan",
    "local_page_evidence_to_dict",
    "run_source_accuracy_pilot",
    "source_accuracy_page_result_to_dict",
    "source_accuracy_pilot_result_to_dict",
    "source_accuracy_pilot_result_to_json",
    "source_accuracy_pilot_result_to_markdown",
    "validate_visual_review_checklist",
]
