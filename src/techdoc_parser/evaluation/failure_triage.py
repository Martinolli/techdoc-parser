"""Diagnosis-only root-cause triage for P0 source-accuracy findings.

This module is evaluation-only. It does not change parser behavior, run OCR,
modify source PDFs, call external services, or write files.
"""

from __future__ import annotations

import json
import unicodedata
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any

from techdoc_parser.chunking import create_semantic_chunks
from techdoc_parser.contracts import build_structured_document_artifact
from techdoc_parser.contracts.structured_document import structured_document_to_dict
from techdoc_parser.core import Block, Chunk, Document, Page
from techdoc_parser.evaluation.source_accuracy import (
    SourceAccuracyPageResult,
    SourceAccuracyPlanPage,
    collect_source_page_proxy,
    evaluate_representative_page,
    load_p0_source_accuracy_plan,
    source_accuracy_page_result_to_dict,
)
from techdoc_parser.evaluation.source_block_eligibility import (
    SourceBlockEligibilityPolicy,
    classify_source_block_chunk_eligibility,
    missing_required_source_block_ids,
    summarize_source_block_eligibility,
)
from techdoc_parser.ingestion import PDFLoader
from techdoc_parser.structure import get_semantic_blocks_for_page

COMPLETE = "COMPLETE"
REVIEW = "REVIEW"
BLOCKED = "BLOCKED"

CONFIRMED_PARSER_DEFECT = "CONFIRMED_PARSER_DEFECT"
EVALUATION_FRAMEWORK_DEFECT = "EVALUATION_FRAMEWORK_DEFECT"
SOURCE_PROXY_LIMITATION = "SOURCE_PROXY_LIMITATION"
EXPECTED_MULTI_REPRESENTATION = "EXPECTED_MULTI_REPRESENTATION"
DOCUMENT_LAYOUT_LIMITATION = "DOCUMENT_LAYOUT_LIMITATION"
NEEDS_VISUAL_CONFIRMATION = "NEEDS_VISUAL_CONFIRMATION"

ROOT_CAUSE_CLASSIFICATIONS = (
    CONFIRMED_PARSER_DEFECT,
    EVALUATION_FRAMEWORK_DEFECT,
    SOURCE_PROXY_LIMITATION,
    EXPECTED_MULTI_REPRESENTATION,
    DOCUMENT_LAYOUT_LIMITATION,
    NEEDS_VISUAL_CONFIRMATION,
)
DIAGNOSTIC_CERTAINTIES = ("confirmed", "probable", "uncertain")
VISUAL_CHECK_VALUES = ("pass", "fail", "uncertain", "pending", "not_applicable")
VISUAL_CHECK_FIELDS = (
    "source_proxy_matches_visible_page",
    "raw_parser_text_matches_visible_page",
    "parser_order_matches_visible_reading_order",
    "duplicate_is_visible_in_source",
    "duplicate_is_parser_introduced",
    "missing_text_is_visible",
    "table_or_box_explains_order",
    "header_footer_explains_duplicate",
    "finding_root_cause_confirmed",
)
TRIAGE_SCOPE = "selected_p0_failure_root_cause_isolation"
DEFAULT_APPROVED_P0_PLAN = Path(
    "tests/fixtures/pilot_corpus/p0_source_accuracy_plan.json"
)


@dataclass(frozen=True)
class FailureTriageCase:
    """One approved P0 case selected for diagnosis."""

    case_id: str
    document_key: str
    filename: str
    pdf_page_index: int
    page_number: int
    original_finding_codes: tuple[str, ...]
    failure_dimensions: tuple[str, ...]
    selection_reason: tuple[str, ...]
    priority: str
    visual_review_required: bool


@dataclass(frozen=True)
class PipelineStageObservation:
    """Sanitized observation for one pipeline stage."""

    stage: str
    entity_count: int
    text_line_count: int
    source_block_ids: tuple[str, ...]
    ordering_keys: tuple[str, ...]
    duplicate_keys: tuple[str, ...]
    coverage_summary: Mapping[str, object]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class FailureTriageFinding:
    """Root-cause classification for one investigated failure."""

    finding_id: str
    case_id: str
    original_finding_code: str
    failure_dimension: str
    root_cause_classification: str
    diagnostic_certainty: str
    introduced_at_stage: str
    evidence_codes: tuple[str, ...]
    requires_visual_confirmation: bool
    recommended_owner: str
    recommended_corrective_phase: str
    message: str
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FailureTriageCaseResult:
    """Diagnosis result for one selected P0 case."""

    case_id: str
    document_key: str
    filename: str
    pdf_page_index: int
    page_number: int
    original_outcome: str
    original_finding_codes: tuple[str, ...]
    failure_dimensions: tuple[str, ...]
    stage_observations: tuple[PipelineStageObservation, ...]
    triage_findings: tuple[FailureTriageFinding, ...]
    root_cause_counts: Mapping[str, int]
    visual_review_status: str
    recommended_action: str
    final_triage_status: str
    local_artifact_labels: tuple[str, ...]


@dataclass(frozen=True)
class FailureTriageResult:
    """Aggregate diagnosis result for the selected P0 subset."""

    outcome: str
    triage_scope: str
    case_count: int
    cases: tuple[FailureTriageCaseResult, ...]
    finding_counts: Mapping[str, int]
    root_cause_counts: Mapping[str, int]
    pipeline_stage_counts: Mapping[str, int]
    confirmed_defect_counts: Mapping[str, int]
    evaluator_defect_counts: Mapping[str, int]
    proxy_limitation_counts: Mapping[str, int]
    layout_limitation_counts: Mapping[str, int]
    visual_confirmation_counts: Mapping[str, int]
    corrective_recommendations: Mapping[str, tuple[str, ...]]
    summary: str
    parser_behavior_changed: bool = False
    evaluator_policy_changed: bool = False
    original_p0_outcomes_changed: bool = False
    ocr_run: bool = False
    aviationrag_modified: bool = False
    full_document_accuracy_evaluated: bool = False


@dataclass(frozen=True)
class FailureTriageLocalEvidence:
    """Local-only evidence that may contain extracted source text."""

    case_result: FailureTriageCaseResult
    source_proxy: Mapping[str, object]
    parser_blocks_raw: tuple[Mapping[str, object], ...]
    parser_blocks_ordered: tuple[Mapping[str, object], ...]
    normalized_blocks: tuple[Mapping[str, object], ...]
    structured_entities: Mapping[str, object]
    semantic_chunks: tuple[Mapping[str, object], ...]
    evaluator_input: Mapping[str, object]
    evaluator_findings: tuple[Mapping[str, object], ...]
    comparison_report: Mapping[str, object]
    root_cause_checklist: Mapping[str, object]


def load_p0_failure_triage_plan(
    path: str | Path,
    *,
    approved_plan: Sequence[SourceAccuracyPlanPage] | None = None,
) -> tuple[FailureTriageCase, ...]:
    """Load and validate a sanitized selected-P0 failure triage plan."""
    data = _load_json_object(path)
    cases_data = data.get("cases")
    if not isinstance(cases_data, list):
        raise ValueError("Failure triage plan must contain a cases list.")
    approved_index = _approved_index(approved_plan)
    cases: list[FailureTriageCase] = []
    case_ids: set[str] = set()
    page_keys: set[tuple[str, int]] = set()
    for index, item in enumerate(cases_data):
        if not isinstance(item, Mapping):
            raise ValueError(f"Triage case {index} must be an object.")
        case = FailureTriageCase(
            case_id=_required_string(item, "case_id", index),
            document_key=_required_string(item, "document_key", index),
            filename=_required_filename(item, index),
            pdf_page_index=_required_int(item, "pdf_page_index", index),
            page_number=_required_int(item, "page_number", index),
            original_finding_codes=_string_tuple(item.get("original_finding_codes")),
            failure_dimensions=_string_tuple(item.get("failure_dimensions")),
            selection_reason=_string_tuple(item.get("selection_reason")),
            priority=_required_string(item, "priority", index),
            visual_review_required=_required_bool(
                item,
                "visual_review_required",
                index,
            ),
        )
        if case.case_id in case_ids:
            raise ValueError(f"Duplicate triage case_id: {case.case_id}.")
        if case.priority != "P0":
            raise ValueError(f"Triage case {case.case_id} is not priority P0.")
        if case.pdf_page_index + 1 != case.page_number:
            raise ValueError(
                f"Triage case {case.case_id} has inconsistent page numbering."
            )
        if not case.original_finding_codes:
            raise ValueError(f"Triage case {case.case_id} requires finding codes.")
        if not case.failure_dimensions:
            raise ValueError(f"Triage case {case.case_id} requires dimensions.")
        page_key = (case.document_key, case.pdf_page_index)
        if page_key in page_keys:
            raise ValueError(
                f"Duplicate selected P0 page: {case.document_key} p{case.page_number}."
            )
        if approved_index and page_key not in approved_index:
            raise ValueError(
                f"Triage case {case.case_id} is not in the approved P0 plan."
            )
        if approved_index:
            approved_page = approved_index[page_key]
            if approved_page.filename != case.filename:
                raise ValueError(
                    f"Triage case {case.case_id} filename does not match P0 plan."
                )
        case_ids.add(case.case_id)
        page_keys.add(page_key)
        cases.append(case)
    return tuple(sorted(cases, key=lambda item: item.case_id))


def load_default_p0_failure_triage_plan(
    path: str | Path,
) -> tuple[FailureTriageCase, ...]:
    """Load a triage plan using the committed P0 source-accuracy plan."""
    approved_plan = (
        load_p0_source_accuracy_plan(DEFAULT_APPROVED_P0_PLAN)
        if DEFAULT_APPROVED_P0_PLAN.is_file()
        else None
    )
    return load_p0_failure_triage_plan(path, approved_plan=approved_plan)


def run_p0_failure_triage(
    *,
    input_dir: str | Path,
    plan: Sequence[FailureTriageCase],
    case_ids: Collection[str] | None = None,
    context_radius: int = 1,
    checklist_paths: Sequence[str | Path] = (),
) -> FailureTriageResult:
    """Run diagnosis-only root-cause triage for selected P0 cases."""
    selected_cases = _filter_cases(plan, case_ids)
    checklists = _load_checklists_by_case_id(checklist_paths)
    input_root = Path(input_dir)
    by_document: dict[str, list[FailureTriageCase]] = {}
    for case in selected_cases:
        by_document.setdefault(case.document_key, []).append(case)

    results: list[FailureTriageCaseResult] = []
    for document_key in sorted(by_document):
        cases = sorted(by_document[document_key], key=lambda item: item.pdf_page_index)
        source_path = input_root / cases[0].filename
        if not source_path.exists():
            results.extend(_missing_source_results(source_path, cases))
            continue
        parser_document = PDFLoader(str(source_path)).load()
        for case in cases:
            page_result = evaluate_representative_page(
                source_path=source_path,
                document_key=case.document_key,
                pdf_page_index=case.pdf_page_index,
                page_number=case.page_number,
                evaluation_roles=_evaluation_roles_from_case(case),
                context_radius=context_radius,
                parser_document=parser_document,
            )
            results.append(
                triage_p0_failure_case(
                    source_path=source_path,
                    case=case,
                    page_result=page_result,
                    parser_document=parser_document,
                    checklist=checklists.get(case.case_id),
                )
            )
    return _aggregate_result(tuple(results))


def triage_p0_failure_case(
    *,
    source_path: str | Path,
    case: FailureTriageCase,
    page_result: SourceAccuracyPageResult | None = None,
    parser_document: Document | None = None,
    checklist: Mapping[str, object] | None = None,
) -> FailureTriageCaseResult:
    """Diagnose one selected P0 case without writing files or changing output."""
    source = Path(source_path)
    if not source.exists():
        return _blocking_case_result(case, "SOURCE_FILE_MISSING")
    document = (
        parser_document
        if parser_document is not None
        else PDFLoader(str(source)).load()
    )
    if case.page_number < 1 or case.page_number > len(document.pages):
        return _blocking_case_result(case, "PARSER_PAGE_UNAVAILABLE")
    result = (
        page_result
        if page_result is not None
        else evaluate_representative_page(
            source_path=source,
            document_key=case.document_key,
            pdf_page_index=case.pdf_page_index,
            page_number=case.page_number,
            evaluation_roles=_evaluation_roles_from_case(case),
            parser_document=document,
        )
    )
    source_proxy = collect_source_page_proxy(source, case.pdf_page_index)
    parser_page = document.pages[case.page_number - 1]
    chunks = _chunks_for_page(create_semantic_chunks(document), case.page_number)
    structured = build_structured_document_artifact(
        document,
        document_id=case.document_key,
    )
    structured_data = structured_document_to_dict(structured)
    stage_data = _stage_data(
        source_proxy=source_proxy,
        parser_page=parser_page,
        structured_data=structured_data,
        chunks=chunks,
        page_number=case.page_number,
    )
    findings = _triage_findings_for_case(
        case=case,
        page_result=result,
        stage_data=stage_data,
    )
    visual_status = _visual_review_status(
        case=case,
        checklist=checklist,
        findings=findings,
    )
    status = _case_status(findings)
    return FailureTriageCaseResult(
        case_id=case.case_id,
        document_key=case.document_key,
        filename=case.filename,
        pdf_page_index=case.pdf_page_index,
        page_number=case.page_number,
        original_outcome=result.final_page_outcome,
        original_finding_codes=case.original_finding_codes,
        failure_dimensions=case.failure_dimensions,
        stage_observations=_observations_from_stage_data(stage_data),
        triage_findings=findings,
        root_cause_counts=dict(
            Counter(finding.root_cause_classification for finding in findings)
        ),
        visual_review_status=visual_status,
        recommended_action=_recommended_action(findings),
        final_triage_status=status,
        local_artifact_labels=_artifact_labels(case),
    )


def build_failure_triage_local_evidence(
    *,
    source_path: str | Path,
    case_result: FailureTriageCaseResult,
    parser_document: Document | None = None,
) -> FailureTriageLocalEvidence:
    """Build local-only triage evidence. This may include extracted text."""
    source = Path(source_path)
    document = (
        parser_document
        if parser_document is not None
        else PDFLoader(str(source)).load()
    )
    source_proxy = collect_source_page_proxy(source, case_result.pdf_page_index)
    parser_page = document.pages[case_result.page_number - 1]
    structured = build_structured_document_artifact(
        document,
        document_id=case_result.document_key,
    )
    structured_data = structured_document_to_dict(structured)
    chunks = _chunks_for_page(create_semantic_chunks(document), case_result.page_number)
    ordered_blocks = get_semantic_blocks_for_page(parser_page)
    normalized_blocks = tuple(
        {
            "block_id": block.id,
            "block_type": block.block_type,
            "normalized_text": _block_text(block),
            "source_text_block_ids": list(_source_text_block_ids(block)),
        }
        for block in parser_page.blocks
    )
    evaluator_input = {
        "page_result": source_accuracy_page_result_to_dict(
            case_result_to_page_proxy(case_result)
        ),
        "stage_observation_count": len(case_result.stage_observations),
    }
    return FailureTriageLocalEvidence(
        case_result=case_result,
        source_proxy=source_proxy,
        parser_blocks_raw=tuple(block.to_dict() for block in parser_page.text_blocks),
        parser_blocks_ordered=tuple(block.to_dict() for block in ordered_blocks),
        normalized_blocks=normalized_blocks,
        structured_entities=_entities_for_page(
            structured_data, case_result.page_number
        ),
        semantic_chunks=tuple(chunk.to_dict() for chunk in chunks),
        evaluator_input=evaluator_input,
        evaluator_findings=tuple(
            failure_triage_finding_to_dict(finding)
            for finding in case_result.triage_findings
        ),
        comparison_report=failure_triage_case_result_to_dict(case_result),
        root_cause_checklist=default_root_cause_checklist(case_result.case_id),
    )


def default_root_cause_checklist(case_id: str) -> dict[str, object]:
    """Return a local root-cause checklist with visual fields pending."""
    return {
        "case_id": case_id,
        "checks": {field: "pending" for field in VISUAL_CHECK_FIELDS},
        "reviewer_notes": "",
    }


def validate_root_cause_checklist(
    checklist: Mapping[str, object],
) -> dict[str, object]:
    """Validate one explicit local root-cause checklist object."""
    allowed_top = {"case_id", "checks", "reviewer_notes"}
    unknown_top = set(checklist) - allowed_top
    if unknown_top:
        raise ValueError(f"Unknown checklist fields: {sorted(unknown_top)}")
    case_id = _required_string(checklist, "case_id", 0)
    checks = _mapping(checklist.get("checks"))
    unknown_checks = set(checks) - set(VISUAL_CHECK_FIELDS)
    if unknown_checks:
        raise ValueError(f"Unknown root-cause checks: {sorted(unknown_checks)}")
    normalized_checks: dict[str, str] = {}
    for field_name in VISUAL_CHECK_FIELDS:
        value = str(checks.get(field_name, "pending"))
        if value not in VISUAL_CHECK_VALUES:
            raise ValueError(f"Invalid checklist value for {field_name}: {value}")
        normalized_checks[field_name] = value
    notes = checklist.get("reviewer_notes", "")
    if not isinstance(notes, str):
        raise ValueError("reviewer_notes must be a string.")
    return {
        "case_id": case_id,
        "checks": normalized_checks,
        "reviewer_notes": notes,
    }


def failure_triage_result_to_dict(result: FailureTriageResult) -> dict[str, Any]:
    """Convert an aggregate triage result to sanitized JSON-safe data."""
    return {
        "outcome": result.outcome,
        "triage_scope": result.triage_scope,
        "case_count": result.case_count,
        "finding_counts": dict(result.finding_counts),
        "root_cause_counts": dict(result.root_cause_counts),
        "pipeline_stage_counts": dict(result.pipeline_stage_counts),
        "confirmed_defect_counts": dict(result.confirmed_defect_counts),
        "evaluator_defect_counts": dict(result.evaluator_defect_counts),
        "proxy_limitation_counts": dict(result.proxy_limitation_counts),
        "layout_limitation_counts": dict(result.layout_limitation_counts),
        "visual_confirmation_counts": dict(result.visual_confirmation_counts),
        "corrective_recommendations": {
            key: list(value)
            for key, value in sorted(result.corrective_recommendations.items())
        },
        "parser_behavior_changed": result.parser_behavior_changed,
        "evaluator_policy_changed": result.evaluator_policy_changed,
        "original_p0_outcomes_changed": result.original_p0_outcomes_changed,
        "ocr_run": result.ocr_run,
        "aviationrag_modified": result.aviationrag_modified,
        "full_document_accuracy_evaluated": result.full_document_accuracy_evaluated,
        "summary": result.summary,
        "cases": [failure_triage_case_result_to_dict(case) for case in result.cases],
    }


def failure_triage_result_to_json(result: FailureTriageResult) -> str:
    """Serialize an aggregate triage result as sanitized JSON."""
    return (
        json.dumps(failure_triage_result_to_dict(result), indent=2, sort_keys=True)
        + "\n"
    )


def failure_triage_result_to_markdown(result: FailureTriageResult) -> str:
    """Serialize an aggregate triage result as sanitized Markdown."""
    lines = [
        "# P0 Failure Root-Cause Triage",
        "",
        f"- Outcome: `{result.outcome}`",
        f"- Triage scope: `{result.triage_scope}`",
        f"- Cases: `{result.case_count}`",
        "- Parser behavior changed: `False`",
        "- Evaluator policy changed: `False`",
        "- OCR run: `False`",
        "- AviationRAG modified: `False`",
        "- Full-document accuracy evaluated: `False`",
        "",
        "## Root-Cause Counts",
        "",
        _mapping_line(result.root_cause_counts),
        "",
        "## Pipeline Stage Counts",
        "",
        _mapping_line(result.pipeline_stage_counts),
        "",
        "## Cases",
        "",
        ("| Case | Document | Page | Original outcome | Root causes | Triage status |"),
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for case in result.cases:
        lines.append(
            f"| `{case.case_id}` | `{case.document_key}` | {case.page_number} | "
            f"`{case.original_outcome}` | {_mapping_line(case.root_cause_counts)} | "
            f"`{case.final_triage_status}` |"
        )
    lines.extend(
        [
            "",
            "## Corrective Recommendations",
            "",
        ]
    )
    if result.corrective_recommendations:
        for phase, cases in sorted(result.corrective_recommendations.items()):
            lines.append(f"- `{phase}`: {', '.join(f'`{case}`' for case in cases)}")
    else:
        lines.append("- `none`")
    lines.extend(
        [
            "",
            "## Privacy",
            "",
            "This report is sanitized. It contains no extracted source text, "
            "rendered pages, source hashes, proprietary procedures, tables, "
            "or equations.",
        ]
    )
    return "\n".join(lines) + "\n"


def failure_triage_case_result_to_dict(
    result: FailureTriageCaseResult,
) -> dict[str, Any]:
    """Convert a case triage result to sanitized JSON-safe data."""
    return {
        "case_id": result.case_id,
        "document_key": result.document_key,
        "filename": result.filename,
        "pdf_page_index": result.pdf_page_index,
        "page_number": result.page_number,
        "original_outcome": result.original_outcome,
        "original_finding_codes": list(result.original_finding_codes),
        "failure_dimensions": list(result.failure_dimensions),
        "stage_observations": [
            pipeline_stage_observation_to_dict(observation)
            for observation in result.stage_observations
        ],
        "triage_findings": [
            failure_triage_finding_to_dict(finding)
            for finding in result.triage_findings
        ],
        "root_cause_counts": dict(result.root_cause_counts),
        "visual_review_status": result.visual_review_status,
        "recommended_action": result.recommended_action,
        "final_triage_status": result.final_triage_status,
        "local_artifact_labels": list(result.local_artifact_labels),
    }


def pipeline_stage_observation_to_dict(
    observation: PipelineStageObservation,
) -> dict[str, object]:
    """Convert a stage observation to sanitized JSON-safe data."""
    return {
        "stage": observation.stage,
        "entity_count": observation.entity_count,
        "text_line_count": observation.text_line_count,
        "source_block_ids": list(observation.source_block_ids),
        "ordering_keys": list(observation.ordering_keys),
        "duplicate_keys": list(observation.duplicate_keys),
        "coverage_summary": dict(observation.coverage_summary),
        "notes": list(observation.notes),
    }


def failure_triage_finding_to_dict(
    finding: FailureTriageFinding,
) -> dict[str, object]:
    """Convert a triage finding to sanitized JSON-safe data."""
    return {
        "finding_id": finding.finding_id,
        "case_id": finding.case_id,
        "original_finding_code": finding.original_finding_code,
        "failure_dimension": finding.failure_dimension,
        "root_cause_classification": finding.root_cause_classification,
        "diagnostic_certainty": finding.diagnostic_certainty,
        "introduced_at_stage": finding.introduced_at_stage,
        "evidence_codes": list(finding.evidence_codes),
        "requires_visual_confirmation": finding.requires_visual_confirmation,
        "recommended_owner": finding.recommended_owner,
        "recommended_corrective_phase": finding.recommended_corrective_phase,
        "message": finding.message,
        "details": dict(finding.details),
    }


def local_failure_triage_evidence_to_dict(
    evidence: FailureTriageLocalEvidence,
) -> dict[str, object]:
    """Return local evidence data. This may include extracted source text."""
    return {
        "case_result": failure_triage_case_result_to_dict(evidence.case_result),
        "source_proxy": dict(evidence.source_proxy),
        "parser_blocks_raw": list(evidence.parser_blocks_raw),
        "parser_blocks_ordered": list(evidence.parser_blocks_ordered),
        "normalized_blocks": list(evidence.normalized_blocks),
        "structured_entities": dict(evidence.structured_entities),
        "semantic_chunks": list(evidence.semantic_chunks),
        "evaluator_input": dict(evidence.evaluator_input),
        "evaluator_findings": list(evidence.evaluator_findings),
        "comparison_report": dict(evidence.comparison_report),
        "root_cause_checklist": dict(evidence.root_cause_checklist),
    }


def case_result_to_page_proxy(
    result: FailureTriageCaseResult,
) -> SourceAccuracyPageResult:
    """Create a source-accuracy-shaped proxy for local evidence metadata only."""
    return SourceAccuracyPageResult(
        document_key=result.document_key,
        filename=result.filename,
        pdf_page_index=result.pdf_page_index,
        page_number=result.page_number,
        printed_page_label=None,
        evaluation_roles=result.failure_dimensions,
        automated_outcome=result.original_outcome,
        visual_review_status=result.visual_review_status,
        visual_review_outcome="REVIEW",
        final_page_outcome=result.original_outcome,
        metrics=(),
        findings=(),
        parser_counts={},
        source_proxy_counts={},
        review_artifact_labels=result.local_artifact_labels,
    )


def _stage_data(
    *,
    source_proxy: Mapping[str, object],
    parser_page: Page,
    structured_data: Mapping[str, object],
    chunks: Sequence[Chunk],
    page_number: int,
) -> dict[str, object]:
    source_blocks = _source_blocks(source_proxy)
    raw_blocks = tuple(parser_page.text_blocks)
    ordered_blocks = tuple(get_semantic_blocks_for_page(parser_page))
    normalized_blocks = tuple(
        block for block in parser_page.blocks if _block_text(block)
    )
    structured_entities = _entities_for_page(structured_data, page_number)
    semantic_blocks = [block for block in ordered_blocks if _block_text(block)]
    chunk_ids = {block_id for chunk in chunks for block_id in chunk.source_block_ids}
    eligibilities = tuple(
        classify_source_block_chunk_eligibility(
            block,
            chunks,
            entities=structured_entities,
            policy=SourceBlockEligibilityPolicy(require_heading_chunks=False),
        )
        for block in ordered_blocks
    )
    corrected_missing = missing_required_source_block_ids(eligibilities)
    evaluator_missing = [
        block.id for block in semantic_blocks if block.id and block.id not in chunk_ids
    ]
    return {
        "source_lines": _normalized_lines(str(source_proxy.get("text", ""))),
        "source_block_lines": _lines_from_source_blocks(source_blocks),
        "parser_lines": _lines_from_blocks(raw_blocks),
        "ordered_lines": _lines_from_blocks(ordered_blocks),
        "normalized_lines": _lines_from_blocks(normalized_blocks),
        "chunk_lines": _lines_from_chunks(chunks),
        "source_blocks": source_blocks,
        "raw_blocks": raw_blocks,
        "ordered_blocks": ordered_blocks,
        "normalized_blocks": normalized_blocks,
        "structured_entities": structured_entities,
        "chunks": tuple(chunks),
        "source_inversions": _source_block_inversions(source_blocks),
        "parser_inversions": _block_inversions(raw_blocks),
        "ordered_inversions": _block_inversions(ordered_blocks),
        "chunk_inversions": _chunk_order_inversions(chunks),
        "semantic_ids": tuple(block.id for block in semantic_blocks if block.id),
        "chunk_ids": tuple(sorted(chunk_ids)),
        "evaluator_missing_ids": tuple(evaluator_missing),
        "rendered_chunk_missing_ids": corrected_missing,
        "policy_v2_missing_ids": corrected_missing,
        "policy_v2_eligibility_summary": summarize_source_block_eligibility(
            eligibilities
        ),
    }


def _triage_findings_for_case(
    *,
    case: FailureTriageCase,
    page_result: SourceAccuracyPageResult,
    stage_data: Mapping[str, object],
) -> tuple[FailureTriageFinding, ...]:
    findings: list[FailureTriageFinding] = []
    for sequence, code in enumerate(case.original_finding_codes, start=1):
        dimension = _dimension_for_code(code, case.failure_dimensions)
        classification = _classification_for_code(
            code=code,
            case=case,
            page_result=page_result,
            stage_data=stage_data,
        )
        findings.append(
            FailureTriageFinding(
                finding_id=f"{case.case_id}:finding:{sequence:03d}",
                case_id=case.case_id,
                original_finding_code=code,
                failure_dimension=dimension,
                root_cause_classification=classification["root_cause"],
                diagnostic_certainty=classification["certainty"],
                introduced_at_stage=classification["stage"],
                evidence_codes=classification["evidence_codes"],
                requires_visual_confirmation=classification["requires_visual"],
                recommended_owner=classification["owner"],
                recommended_corrective_phase=classification["phase"],
                message=classification["message"],
                details=classification["details"],
            )
        )
    return tuple(findings)


def _classification_for_code(
    *,
    code: str,
    case: FailureTriageCase,
    page_result: SourceAccuracyPageResult,
    stage_data: Mapping[str, object],
) -> dict[str, Any]:
    if code == "DUPLICATE_TEXT_LINES":
        return _classify_duplicate(case, stage_data)
    if code == "RAW_CHARACTER_COVERAGE_STATUS_FAIL":
        return _classify_coverage_metric(page_result)
    if code == "READING_ORDER_INVERSION":
        return _classify_reading_order(case, stage_data)
    if code == "CHUNK_SOURCE_COVERAGE_GAP":
        return _classify_chunk_gap(stage_data)
    if code == "TABLE_CANDIDATE_ONLY":
        return _classification(
            root_cause=EXPECTED_MULTI_REPRESENTATION,
            certainty="confirmed",
            stage="structure/entity_mapping",
            evidence_codes=("TABLE_CANDIDATE_ENTITY_REPRESENTATION",),
            requires_visual=True,
            owner="evaluation_policy",
            phase="13I-c2E",
            message=(
                "Candidate-level table representation is expected multi-"
                "representation, not a standalone parser defect."
            ),
        )
    if code.endswith("_EVIDENCE_NOT_AUTOMATED") or code.endswith(
        "_VISUAL_REVIEW_REQUIRED"
    ):
        return _classification(
            root_cause=NEEDS_VISUAL_CONFIRMATION,
            certainty="uncertain",
            stage="human_visual_review",
            evidence_codes=("VISUAL_ENTITY_CONFIRMATION_REQUIRED",),
            requires_visual=True,
            owner="owner_review",
            phase="owner_visual_checklists",
            message=(
                "Automated evidence cannot determine the visual source "
                "association for this finding."
            ),
        )
    if code == "CHUNK_SECTION_CROSSING_REVIEW":
        return _classification(
            root_cause=DOCUMENT_LAYOUT_LIMITATION,
            certainty="probable",
            stage="chunk_construction",
            evidence_codes=("MULTI_SECTION_CONTEXT_REQUIRES_REVIEW",),
            requires_visual=True,
            owner="owner_review",
            phase="owner_visual_checklists",
            message=(
                "Multiple section contexts on the selected page require "
                "review before treating this as a chunking defect."
            ),
        )
    if code == "VISUAL_REVIEW_PENDING":
        return _classification(
            root_cause=NEEDS_VISUAL_CONFIRMATION,
            certainty="confirmed",
            stage="human_visual_review",
            evidence_codes=("VISUAL_CHECKLIST_PENDING",),
            requires_visual=True,
            owner="owner_review",
            phase="owner_visual_checklists",
            message="Final source-accuracy approval requires visual review.",
        )
    return _classification(
        root_cause=NEEDS_VISUAL_CONFIRMATION,
        certainty="uncertain",
        stage="human_visual_review",
        evidence_codes=("UNMAPPED_FINDING_REQUIRES_REVIEW",),
        requires_visual=True,
        owner="owner_review",
        phase="owner_visual_checklists",
        message="The finding requires visual confirmation before correction.",
    )


def _classify_duplicate(
    case: FailureTriageCase,
    stage_data: Mapping[str, object],
) -> dict[str, Any]:
    source_duplicates = len(
        _duplicate_lines(_stage_lines(stage_data, "source_block_lines"))
    )
    parser_duplicates = len(_duplicate_lines(_stage_lines(stage_data, "parser_lines")))
    chunk_duplicates = len(_duplicate_lines(_stage_lines(stage_data, "chunk_lines")))
    if source_duplicates and parser_duplicates <= source_duplicates:
        return _classification(
            root_cause=SOURCE_PROXY_LIMITATION,
            certainty="probable",
            stage="source_proxy",
            evidence_codes=("SOURCE_PROXY_DUPLICATE_LINES",),
            requires_visual=True,
            owner="owner_review",
            phase="owner_visual_checklists",
            message=(
                "Duplicate lines are already visible in direct source-block "
                "proxy extraction; visual confirmation is needed before parser "
                "correction."
            ),
            details={
                "source_duplicate_count": source_duplicates,
                "parser_duplicate_count": parser_duplicates,
                "chunk_duplicate_count": chunk_duplicates,
            },
        )
    if parser_duplicates > source_duplicates:
        return _classification(
            root_cause=CONFIRMED_PARSER_DEFECT,
            certainty="probable",
            stage="parser_text_block_extraction",
            evidence_codes=("PARSER_DUPLICATE_EXCEEDS_SOURCE_PROXY",),
            requires_visual=True,
            owner="ingestion",
            phase="13I-c2A",
            message=(
                "Parser raw text blocks contain more duplicate lines than the "
                "source proxy."
            ),
            details={
                "source_duplicate_count": source_duplicates,
                "parser_duplicate_count": parser_duplicates,
                "chunk_duplicate_count": chunk_duplicates,
            },
        )
    return _classification(
        root_cause=NEEDS_VISUAL_CONFIRMATION,
        certainty="uncertain",
        stage="human_visual_review",
        evidence_codes=("DUPLICATE_ORIGIN_UNPROVEN",),
        requires_visual=True,
        owner="owner_review",
        phase="owner_visual_checklists",
        message=f"Duplicate origin for {case.case_id} is not proven automatically.",
    )


def _classify_coverage_metric(
    page_result: SourceAccuracyPageResult,
) -> dict[str, Any]:
    coverage = _metric_value(page_result, "raw_character_coverage")
    missing_lines = _metric_value(page_result, "missing_line_count")
    threshold = _metric_threshold(page_result, "raw_character_coverage")
    if (
        isinstance(coverage, int | float)
        and isinstance(threshold, int | float)
        and coverage >= threshold
        and missing_lines == 0
    ):
        return _classification(
            root_cause=EVALUATION_FRAMEWORK_DEFECT,
            certainty="confirmed",
            stage="source_accuracy_evaluator",
            evidence_codes=("COVERAGE_VALUE_PASS_STATUS_FAILS",),
            requires_visual=False,
            owner="evaluation",
            phase="13I-c2E",
            message=(
                "The raw coverage metric was marked failed even though its "
                "numeric coverage met threshold and missing-line count was zero."
            ),
            details={"coverage": coverage, "threshold": threshold},
        )
    return _classification(
        root_cause=NEEDS_VISUAL_CONFIRMATION,
        certainty="uncertain",
        stage="human_visual_review",
        evidence_codes=("TEXT_COVERAGE_NEEDS_SOURCE_REVIEW",),
        requires_visual=True,
        owner="owner_review",
        phase="owner_visual_checklists",
        message="Automated evidence is insufficient to confirm text loss.",
    )


def _classify_reading_order(
    case: FailureTriageCase,
    stage_data: Mapping[str, object],
) -> dict[str, Any]:
    source_inversions = len(_stage_tuple(stage_data, "source_inversions"))
    parser_inversions = len(_stage_tuple(stage_data, "parser_inversions"))
    ordered_inversions = len(_stage_tuple(stage_data, "ordered_inversions"))
    if parser_inversions > source_inversions:
        return _classification(
            root_cause=CONFIRMED_PARSER_DEFECT,
            certainty="probable",
            stage="parser_text_block_extraction",
            evidence_codes=("PARSER_ORDER_DIFFERS_FROM_SOURCE_PROXY",),
            requires_visual=True,
            owner="ingestion",
            phase="13I-c2B",
            message=(
                "Parser block order shows more coordinate inversions than the "
                "direct source proxy."
            ),
            details={
                "source_inversions": source_inversions,
                "parser_inversions": parser_inversions,
                "ordered_inversions": ordered_inversions,
            },
        )
    if _has_complex_layout(case):
        return _classification(
            root_cause=NEEDS_VISUAL_CONFIRMATION,
            certainty="uncertain",
            stage="human_visual_review",
            evidence_codes=("COMPLEX_LAYOUT_LINEAR_ORDER_UNPROVEN",),
            requires_visual=True,
            owner="owner_review",
            phase="owner_visual_checklists",
            message=(
                "The direct source proxy and parser order require visual "
                "confirmation on this complex-layout page."
            ),
            details={
                "source_inversions": source_inversions,
                "parser_inversions": parser_inversions,
                "ordered_inversions": ordered_inversions,
            },
        )
    return _classification(
        root_cause=SOURCE_PROXY_LIMITATION,
        certainty="probable",
        stage="source_proxy",
        evidence_codes=("SOURCE_PROXY_ORDER_HAS_GEOMETRIC_INVERSION",),
        requires_visual=True,
        owner="owner_review",
        phase="owner_visual_checklists",
        message=(
            "The automated source proxy itself has coordinate inversions; this "
            "is not sufficient to prove parser ordering failure."
        ),
        details={
            "source_inversions": source_inversions,
            "parser_inversions": parser_inversions,
            "ordered_inversions": ordered_inversions,
        },
    )


def _classify_chunk_gap(stage_data: Mapping[str, object]) -> dict[str, Any]:
    evaluator_missing = _stage_tuple(stage_data, "evaluator_missing_ids")
    corrected_missing = _stage_tuple(stage_data, "policy_v2_missing_ids")
    if evaluator_missing and not corrected_missing:
        return _classification(
            root_cause=EVALUATION_FRAMEWORK_DEFECT,
            certainty="confirmed",
            stage="source_accuracy_evaluator",
            evidence_codes=("CHUNK_ELIGIBILITY_RECLASSIFIED_BY_POLICY_V2",),
            requires_visual=False,
            owner="evaluation",
            phase="13I-c2E",
            message=(
                "The b2 evaluator counted a semantic block as missing, but "
                "policy v2 does not reproduce a required direct chunk gap."
            ),
            details={
                "evaluator_missing_count": len(evaluator_missing),
                "corrected_policy_reproduced": False,
                "policy_v2_missing_count": 0,
            },
        )
    if corrected_missing:
        return _classification(
            root_cause=CONFIRMED_PARSER_DEFECT,
            certainty="probable",
            stage="semantic_chunks",
            evidence_codes=("RENDERED_SEMANTIC_BLOCK_NOT_IN_CHUNK_SOURCE_IDS",),
            requires_visual=False,
            owner="chunking",
            phase="13I-c2D",
            message="A rendered semantic block is absent from selected page chunks.",
            details={
                "rendered_missing_count": len(corrected_missing),
                "corrected_policy_reproduced": True,
            },
        )
    return _classification(
        root_cause=EVALUATION_FRAMEWORK_DEFECT,
        certainty="confirmed",
        stage="source_accuracy_evaluator",
        evidence_codes=("CHUNK_GAP_NOT_REPRODUCED",),
        requires_visual=False,
        owner="evaluation",
        phase="13I-c2E",
        message="The chunk source-coverage gap was not reproduced by diagnostics.",
        details={"corrected_policy_reproduced": False},
    )


def _observations_from_stage_data(
    stage_data: Mapping[str, object],
) -> tuple[PipelineStageObservation, ...]:
    source_blocks = _stage_mappings(stage_data, "source_blocks")
    raw_blocks = _stage_blocks(stage_data, "raw_blocks")
    ordered_blocks = _stage_blocks(stage_data, "ordered_blocks")
    normalized_blocks = _stage_blocks(stage_data, "normalized_blocks")
    chunks = _stage_chunks(stage_data, "chunks")
    entities = _mapping(stage_data.get("structured_entities"))
    return (
        _source_observation(source_blocks, stage_data),
        _block_observation("parser_blocks_raw", raw_blocks),
        _block_observation("parser_blocks_ordered", ordered_blocks),
        _block_observation("normalized_blocks", normalized_blocks),
        _entity_observation(entities),
        _chunk_observation(chunks, stage_data),
        _evaluator_observation(stage_data),
    )


def _source_observation(
    source_blocks: Sequence[Mapping[str, object]],
    stage_data: Mapping[str, object],
) -> PipelineStageObservation:
    lines = _stage_lines(stage_data, "source_block_lines")
    return PipelineStageObservation(
        stage="source_proxy",
        entity_count=len(source_blocks),
        text_line_count=len(lines),
        source_block_ids=tuple(
            str(block.get("source_block_id")) for block in source_blocks
        ),
        ordering_keys=_source_order_keys(source_blocks),
        duplicate_keys=_duplicate_keys(lines),
        coverage_summary={
            "duplicate_line_count": len(_duplicate_lines(lines)),
            "inversion_count": len(_stage_tuple(stage_data, "source_inversions")),
        },
        notes=("automated_source_proxy_not_visual_ground_truth",),
    )


def _block_observation(
    stage: str,
    blocks: Sequence[Block],
) -> PipelineStageObservation:
    lines = _lines_from_blocks(blocks)
    return PipelineStageObservation(
        stage=stage,
        entity_count=len(blocks),
        text_line_count=len(lines),
        source_block_ids=tuple(block.id for block in blocks if block.id),
        ordering_keys=_block_order_keys(blocks),
        duplicate_keys=_duplicate_keys(lines),
        coverage_summary={
            "duplicate_line_count": len(_duplicate_lines(lines)),
            "inversion_count": len(_block_inversions(blocks)),
        },
    )


def _entity_observation(
    entities: Mapping[str, object],
) -> PipelineStageObservation:
    entity_counts = {
        key: len(value)
        for key, value in entities.items()
        if isinstance(value, Sequence) and not isinstance(value, str)
    }
    total = sum(entity_counts.values())
    return PipelineStageObservation(
        stage="structured_entities",
        entity_count=total,
        text_line_count=0,
        source_block_ids=(),
        ordering_keys=tuple(sorted(entity_counts)),
        duplicate_keys=(),
        coverage_summary=entity_counts,
        notes=("root_entities_preserve_structured_representations",),
    )


def _chunk_observation(
    chunks: Sequence[Chunk],
    stage_data: Mapping[str, object],
) -> PipelineStageObservation:
    lines = _lines_from_chunks(chunks)
    return PipelineStageObservation(
        stage="semantic_chunks",
        entity_count=len(chunks),
        text_line_count=len(lines),
        source_block_ids=tuple(
            dict.fromkeys(
                block_id for chunk in chunks for block_id in chunk.source_block_ids
            )
        ),
        ordering_keys=tuple(chunk.id for chunk in chunks),
        duplicate_keys=_duplicate_keys(lines),
        coverage_summary={
            "semantic_id_count": len(_stage_tuple(stage_data, "semantic_ids")),
            "chunk_source_id_count": len(_stage_tuple(stage_data, "chunk_ids")),
            "evaluator_missing_count": len(
                _stage_tuple(stage_data, "evaluator_missing_ids")
            ),
            "rendered_missing_count": len(
                _stage_tuple(stage_data, "rendered_chunk_missing_ids")
            ),
        },
    )


def _evaluator_observation(
    stage_data: Mapping[str, object],
) -> PipelineStageObservation:
    return PipelineStageObservation(
        stage="source_accuracy_evaluator",
        entity_count=0,
        text_line_count=0,
        source_block_ids=(),
        ordering_keys=(),
        duplicate_keys=(),
        coverage_summary={
            "evaluator_missing_ids": len(
                _stage_tuple(stage_data, "evaluator_missing_ids")
            ),
            "rendered_missing_ids": len(
                _stage_tuple(stage_data, "rendered_chunk_missing_ids")
            ),
        },
        notes=("diagnosis_only_no_policy_change",),
    )


def _aggregate_result(
    case_results: tuple[FailureTriageCaseResult, ...],
) -> FailureTriageResult:
    findings = [finding for case in case_results for finding in case.triage_findings]
    root_counts = Counter(finding.root_cause_classification for finding in findings)
    stage_counts = Counter(finding.introduced_at_stage for finding in findings)
    finding_counts = Counter(finding.original_finding_code for finding in findings)
    outcome = COMPLETE
    if any(case.final_triage_status == BLOCKED for case in case_results):
        outcome = BLOCKED
    elif any(case.final_triage_status == REVIEW for case in case_results):
        outcome = REVIEW
    recommendations: dict[str, list[str]] = {}
    for finding in findings:
        if finding.recommended_corrective_phase in {
            "none",
            "owner_visual_checklists",
        }:
            continue
        recommendations.setdefault(finding.recommended_corrective_phase, [])
        if finding.case_id not in recommendations[finding.recommended_corrective_phase]:
            recommendations[finding.recommended_corrective_phase].append(
                finding.case_id
            )
    return FailureTriageResult(
        outcome=outcome,
        triage_scope=TRIAGE_SCOPE,
        case_count=len(case_results),
        cases=tuple(sorted(case_results, key=lambda item: item.case_id)),
        finding_counts=dict(finding_counts),
        root_cause_counts=dict(root_counts),
        pipeline_stage_counts=dict(stage_counts),
        confirmed_defect_counts=_counts_for_root(findings, CONFIRMED_PARSER_DEFECT),
        evaluator_defect_counts=_counts_for_root(findings, EVALUATION_FRAMEWORK_DEFECT),
        proxy_limitation_counts=_counts_for_root(findings, SOURCE_PROXY_LIMITATION),
        layout_limitation_counts=_counts_for_root(findings, DOCUMENT_LAYOUT_LIMITATION),
        visual_confirmation_counts=_counts_for_root(
            findings, NEEDS_VISUAL_CONFIRMATION
        ),
        corrective_recommendations={
            phase: tuple(sorted(cases))
            for phase, cases in sorted(recommendations.items())
        },
        summary=(
            f"Diagnosed {len(case_results)} selected P0 cases; triage outcome "
            f"is {outcome}."
        ),
    )


def _counts_for_root(
    findings: Sequence[FailureTriageFinding],
    root_cause: str,
) -> dict[str, int]:
    return dict(
        Counter(
            finding.failure_dimension
            for finding in findings
            if finding.root_cause_classification == root_cause
        )
    )


def _missing_source_results(
    source_path: Path,
    cases: Sequence[FailureTriageCase],
) -> list[FailureTriageCaseResult]:
    return [
        _blocking_case_result(case, f"SOURCE_FILE_MISSING:{source_path.name}")
        for case in cases
    ]


def _blocking_case_result(
    case: FailureTriageCase,
    reason: str,
) -> FailureTriageCaseResult:
    finding = FailureTriageFinding(
        finding_id=f"{case.case_id}:finding:001",
        case_id=case.case_id,
        original_finding_code=reason,
        failure_dimension="blocking_evidence",
        root_cause_classification=NEEDS_VISUAL_CONFIRMATION,
        diagnostic_certainty="uncertain",
        introduced_at_stage="diagnostic_pipeline",
        evidence_codes=("DIAGNOSTIC_EVIDENCE_BLOCKED",),
        requires_visual_confirmation=True,
        recommended_owner="evaluation",
        recommended_corrective_phase="13I-c2E",
        message="Diagnostic evidence could not be produced.",
    )
    return FailureTriageCaseResult(
        case_id=case.case_id,
        document_key=case.document_key,
        filename=case.filename,
        pdf_page_index=case.pdf_page_index,
        page_number=case.page_number,
        original_outcome=BLOCKED,
        original_finding_codes=case.original_finding_codes,
        failure_dimensions=case.failure_dimensions,
        stage_observations=(),
        triage_findings=(finding,),
        root_cause_counts={NEEDS_VISUAL_CONFIRMATION: 1},
        visual_review_status="blocked",
        recommended_action="produce_missing_diagnostic_evidence",
        final_triage_status=BLOCKED,
        local_artifact_labels=_artifact_labels(case),
    )


def _classification(
    *,
    root_cause: str,
    certainty: str,
    stage: str,
    evidence_codes: Sequence[str],
    requires_visual: bool,
    owner: str,
    phase: str,
    message: str,
    details: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "root_cause": root_cause,
        "certainty": certainty,
        "stage": stage,
        "evidence_codes": tuple(evidence_codes),
        "requires_visual": requires_visual,
        "owner": owner,
        "phase": phase,
        "message": message,
        "details": dict(details or {}),
    }


def _case_status(findings: Sequence[FailureTriageFinding]) -> str:
    if not findings:
        return BLOCKED
    if any(
        finding.introduced_at_stage == "diagnostic_pipeline" for finding in findings
    ):
        return BLOCKED
    if any(
        finding.requires_visual_confirmation
        or finding.diagnostic_certainty == "uncertain"
        or finding.root_cause_classification == NEEDS_VISUAL_CONFIRMATION
        for finding in findings
    ):
        return REVIEW
    return COMPLETE


def _recommended_action(findings: Sequence[FailureTriageFinding]) -> str:
    if any(
        finding.root_cause_classification == CONFIRMED_PARSER_DEFECT
        for finding in findings
    ):
        return "prepare_targeted_parser_or_chunking_phase_after_visual_confirmation"
    if any(
        finding.root_cause_classification == EVALUATION_FRAMEWORK_DEFECT
        for finding in findings
    ):
        return "prepare_evaluation_policy_correction_without_changing_b2_results"
    return "complete_owner_visual_confirmation_before_parser_correction"


def _visual_review_status(
    *,
    case: FailureTriageCase,
    checklist: Mapping[str, object] | None,
    findings: Sequence[FailureTriageFinding],
) -> str:
    if checklist is None:
        return "pending" if case.visual_review_required else "not_required"
    checklist_data = validate_root_cause_checklist(checklist)
    checks = _mapping(checklist_data["checks"])
    if any(value == "pending" for value in checks.values()):
        return "pending"
    if any(value == "uncertain" for value in checks.values()):
        return "uncertain"
    if any(finding.requires_visual_confirmation for finding in findings):
        return "completed_requires_reconciliation"
    return "completed"


def _filter_cases(
    plan: Sequence[FailureTriageCase],
    case_ids: Collection[str] | None,
) -> tuple[FailureTriageCase, ...]:
    if case_ids is None:
        return tuple(plan)
    requested = set(case_ids)
    return tuple(case for case in plan if case.case_id in requested)


def _load_checklists_by_case_id(
    checklist_paths: Sequence[str | Path],
) -> dict[str, Mapping[str, object]]:
    result: dict[str, Mapping[str, object]] = {}
    for path in checklist_paths:
        checklist = validate_root_cause_checklist(_load_json_object(path))
        result[str(checklist["case_id"])] = checklist
    return result


def _approved_index(
    approved_plan: Sequence[SourceAccuracyPlanPage] | None,
) -> dict[tuple[str, int], SourceAccuracyPlanPage]:
    if approved_plan is None:
        return {}
    return {(page.document_key, page.pdf_page_index): page for page in approved_plan}


def _evaluation_roles_from_case(case: FailureTriageCase) -> tuple[str, ...]:
    roles: set[str] = set()
    for dimension in case.failure_dimensions:
        roles.update(_roles_for_dimension(dimension))
    if not roles:
        roles.add("ordinary_text")
    return tuple(sorted(roles))


def _roles_for_dimension(dimension: str) -> tuple[str, ...]:
    mapping = {
        "control_page": ("ordinary_text",),
        "duplicate_text": ("ordinary_text",),
        "text_coverage": ("ordinary_text",),
        "reading_order": ("reading_order", "multi_column"),
        "chunk_source_coverage": ("ordinary_text",),
        "table_entity": ("table",),
        "figure_caption": ("figure_caption",),
        "equation_or_text_box": ("equation", "mixed_layout"),
        "admonition_or_procedure": ("admonition", "procedure"),
        "cross_reference": ("cross_reference",),
    }
    return mapping.get(dimension, ("ordinary_text",))


def _dimension_for_code(
    code: str,
    fallback_dimensions: Sequence[str],
) -> str:
    if code == "DUPLICATE_TEXT_LINES":
        return "duplicate_text"
    if code == "RAW_CHARACTER_COVERAGE_STATUS_FAIL":
        return "text_coverage"
    if code == "READING_ORDER_INVERSION":
        return "reading_order"
    if code == "CHUNK_SOURCE_COVERAGE_GAP":
        return "chunk_source_coverage"
    if code.startswith("TABLE_"):
        return "table_entity"
    if code.startswith("FIGURE_"):
        return "figure_caption"
    if code.startswith("EQUATION_"):
        return "equation_or_text_box"
    if code.startswith("ADMONITION_"):
        return "admonition_or_procedure"
    if code.startswith("CROSS_REFERENCE_"):
        return "cross_reference"
    if code == "CHUNK_SECTION_CROSSING_REVIEW":
        return "chunk_section_context"
    if code == "VISUAL_REVIEW_PENDING":
        return "visual_review_pending"
    return fallback_dimensions[0] if fallback_dimensions else "unknown"


def _has_complex_layout(case: FailureTriageCase) -> bool:
    complex_dimensions = {
        "reading_order",
        "table_entity",
        "figure_caption",
        "equation_or_text_box",
        "admonition_or_procedure",
    }
    return bool(complex_dimensions & set(case.failure_dimensions))


def _metric_value(result: SourceAccuracyPageResult, metric_name: str) -> object:
    for metric in result.metrics:
        if metric.name == metric_name:
            return metric.value
    return None


def _metric_threshold(result: SourceAccuracyPageResult, metric_name: str) -> object:
    for metric in result.metrics:
        if metric.name == metric_name:
            return metric.threshold
    return None


def _artifact_labels(case: FailureTriageCase) -> tuple[str, ...]:
    base = f"{case.case_id}"
    return (
        f"{base}/source_proxy.json",
        f"{base}/parser_blocks_raw.json",
        f"{base}/parser_blocks_ordered.json",
        f"{base}/normalized_blocks.json",
        f"{base}/entities.json",
        f"{base}/chunks.json",
        f"{base}/evaluator_input.json",
        f"{base}/evaluator_findings.json",
        f"{base}/comparison_report.json",
        f"{base}/review.html",
        f"{base}/root_cause_checklist.json",
    )


def _chunks_for_page(chunks: Sequence[Chunk], page_number: int) -> tuple[Chunk, ...]:
    return tuple(chunk for chunk in chunks if page_number in chunk.source_page_numbers)


def _source_blocks(
    source_proxy: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    value = source_proxy.get("text_blocks")
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _lines_from_source_blocks(
    source_blocks: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    lines: list[str] = []
    for block in source_blocks:
        lines.extend(_normalized_lines(str(block.get("text", ""))))
    return tuple(lines)


def _lines_from_blocks(blocks: Sequence[Block]) -> tuple[str, ...]:
    lines: list[str] = []
    for block in blocks:
        lines.extend(_normalized_lines(_block_text(block)))
    return tuple(lines)


def _lines_from_chunks(chunks: Sequence[Chunk]) -> tuple[str, ...]:
    lines: list[str] = []
    for chunk in chunks:
        lines.extend(_normalized_lines(chunk.text))
    return tuple(lines)


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


def _duplicate_keys(lines: Sequence[str]) -> tuple[str, ...]:
    duplicates = _duplicate_lines(lines)
    return tuple(
        f"duplicate_line_{index:03d}" for index, _line in enumerate(duplicates, start=1)
    )


def _source_block_inversions(
    source_blocks: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    inversions: list[str] = []
    previous_y: float | None = None
    previous_id = ""
    for block in source_blocks:
        bbox = block.get("bbox")
        if not isinstance(bbox, Sequence) or isinstance(bbox, str) or len(bbox) < 2:
            continue
        y0 = float(bbox[1])
        block_id = str(block.get("source_block_id", "source-block"))
        if previous_y is not None and y0 + 2.0 < previous_y:
            inversions.append(f"{previous_id}->{block_id}")
        previous_y = y0
        previous_id = block_id
    return tuple(inversions)


def _block_inversions(blocks: Sequence[Block]) -> tuple[str, ...]:
    inversions: list[str] = []
    previous_y: float | None = None
    previous_id = ""
    for block in blocks:
        bbox = block.source.bbox if block.source is not None else None
        if bbox is None:
            continue
        if previous_y is not None and bbox.y0 + 2.0 < previous_y:
            inversions.append(f"{previous_id}->{block.id}")
        previous_y = bbox.y0
        previous_id = block.id
    return tuple(inversions)


def _chunk_order_inversions(chunks: Sequence[Chunk]) -> tuple[str, ...]:
    inversions: list[str] = []
    previous_index: int | None = None
    previous_id = ""
    for chunk in chunks:
        index = _first_block_page_index(chunk)
        if previous_index is not None and index < previous_index:
            inversions.append(f"{previous_id}->{chunk.id}")
        previous_index = index
        previous_id = chunk.id
    return tuple(inversions)


def _first_block_page_index(chunk: Chunk) -> int:
    if not chunk.source_block_ids:
        return 0
    first = chunk.source_block_ids[0]
    parts = first.split("-")
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 0


def _source_order_keys(
    source_blocks: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    keys: list[str] = []
    for block in source_blocks:
        bbox = block.get("bbox")
        if isinstance(bbox, Sequence) and not isinstance(bbox, str) and len(bbox) >= 2:
            keys.append(f"{block.get('source_block_id')}@{float(bbox[1]):.2f}")
    return tuple(keys)


def _block_order_keys(blocks: Sequence[Block]) -> tuple[str, ...]:
    keys: list[str] = []
    for block in blocks:
        bbox = block.source.bbox if block.source is not None else None
        if bbox is not None:
            keys.append(f"{block.id}@{bbox.y0:.2f}")
        else:
            keys.append(f"{block.id}@none")
    return tuple(keys)


def _entities_for_page(
    structured_data: Mapping[str, object],
    page_number: int,
) -> dict[str, object]:
    return {
        "tables": _entities_on_page(structured_data, "tables", page_number),
        "figures": _entities_on_page(structured_data, "figures", page_number),
        "equations": _entities_on_page(structured_data, "equations", page_number),
        "admonitions": _entities_on_page(structured_data, "admonitions", page_number),
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
    value = structured_data.get(field_name)
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(
        item
        for item in value
        if isinstance(item, Mapping) and _entity_touches_page(item, page_number)
    )


def _entity_touches_page(entity: Mapping[str, object], page_number: int) -> bool:
    page_refs = entity.get("page_refs")
    if isinstance(page_refs, Sequence) and not isinstance(page_refs, str):
        return page_number in [value for value in page_refs if isinstance(value, int)]
    source_span = entity.get("source_span")
    if not isinstance(source_span, Mapping):
        return False
    start = source_span.get("page_start")
    end = source_span.get("page_end")
    return (
        isinstance(start, int) and isinstance(end, int) and start <= page_number <= end
    )


def _source_text_block_ids(block: Block) -> tuple[str, ...]:
    ids = getattr(block, "source_text_block_ids", ())
    if not isinstance(ids, Sequence) or isinstance(ids, str):
        return ()
    return tuple(str(value) for value in ids)


def _block_text(block: Block) -> str:
    return block.normalized_text or block.text or getattr(block, "caption", None) or ""


def _stage_lines(data: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(str(item) for item in value)


def _stage_tuple(data: Mapping[str, object], key: str) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(str(item) for item in value)


def _stage_blocks(data: Mapping[str, object], key: str) -> tuple[Block, ...]:
    value = data.get(key)
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(item for item in value if isinstance(item, Block))


def _stage_chunks(data: Mapping[str, object], key: str) -> tuple[Chunk, ...]:
    value = data.get(key)
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(item for item in value if isinstance(item, Chunk))


def _stage_mappings(
    data: Mapping[str, object],
    key: str,
) -> tuple[Mapping[str, object], ...]:
    value = data.get(key)
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("Expected object mapping.")
    return value


def _load_json_object(path: str | Path) -> dict[str, object]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _required_string(data: Mapping[str, object], key: str, index: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Triage case {index} requires non-empty string {key}.")
    return value.strip()


def _required_filename(data: Mapping[str, object], index: int) -> str:
    value = _required_string(data, "filename", index)
    if PureWindowsPath(value).drive or "/" in value or "\\" in value:
        raise ValueError(f"Triage case {index} filename must be a basename.")
    return value


def _required_int(data: Mapping[str, object], key: str, index: int) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Triage case {index} requires integer {key}.")
    return value


def _required_bool(data: Mapping[str, object], key: str, index: int) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"Triage case {index} requires boolean {key}.")
    return value


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


def _mapping_line(mapping: Mapping[str, object]) -> str:
    if not mapping:
        return "`none`"
    items = ", ".join(f"{key}: {value}" for key, value in sorted(mapping.items()))
    return f"`{items}`"


__all__ = [
    "BLOCKED",
    "COMPLETE",
    "CONFIRMED_PARSER_DEFECT",
    "DOCUMENT_LAYOUT_LIMITATION",
    "EVALUATION_FRAMEWORK_DEFECT",
    "EXPECTED_MULTI_REPRESENTATION",
    "FailureTriageCase",
    "FailureTriageCaseResult",
    "FailureTriageFinding",
    "FailureTriageLocalEvidence",
    "FailureTriageResult",
    "NEEDS_VISUAL_CONFIRMATION",
    "PipelineStageObservation",
    "REVIEW",
    "ROOT_CAUSE_CLASSIFICATIONS",
    "SOURCE_PROXY_LIMITATION",
    "TRIAGE_SCOPE",
    "build_failure_triage_local_evidence",
    "default_root_cause_checklist",
    "failure_triage_case_result_to_dict",
    "failure_triage_finding_to_dict",
    "failure_triage_result_to_dict",
    "failure_triage_result_to_json",
    "failure_triage_result_to_markdown",
    "load_default_p0_failure_triage_plan",
    "load_p0_failure_triage_plan",
    "local_failure_triage_evidence_to_dict",
    "pipeline_stage_observation_to_dict",
    "run_p0_failure_triage",
    "triage_p0_failure_case",
    "validate_root_cause_checklist",
]
