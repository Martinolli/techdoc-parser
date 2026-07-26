"""Controlled engineering OCR-fidelity evaluation helpers.

This module is evaluation-only. It does not run OCR, modify source PDFs,
change parser behavior, call external services, write files, or approve OCR
fidelity without explicit owner review.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from hashlib import sha256
from pathlib import Path, PureWindowsPath
from typing import Any, cast

import fitz  # type: ignore[import-untyped]

PASS = "PASS"
REVIEW = "REVIEW"
FAIL = "FAIL"
BLOCKED = "BLOCKED"
OWNER_REVIEW_REQUIRED = "OWNER_REVIEW_REQUIRED"
NEEDS_SECOND_REVIEW = "NEEDS_SECOND_REVIEW"
ACCEPTED_WITH_LIMITATIONS = "ACCEPTED_WITH_LIMITATIONS"

PENDING = "pending"
COMPLETED = "completed"
BLOCKED_REVIEW = "blocked"

ENGINEERING_OCR_SCOPE = "controlled_engineering_ocr_fidelity"
ENGINEERING_OCR_POLICY_NAME = "engineering-ocr-fidelity"
ENGINEERING_OCR_POLICY_VERSION = "0.1"
EXPECTED_SOURCE_PAGES = 43

NO_SUPPORTED_OCR_EXECUTION_PATH = "NO_SUPPORTED_OCR_EXECUTION_PATH"
OCR_ARTIFACT_SUPPLIED = "OCR_ARTIFACT_SUPPLIED"

FINDING_CATEGORIES = (
    "CAPABILITY_GAP",
    "TEXT_FIDELITY",
    "READING_ORDER",
    "SYMBOL_FIDELITY",
    "FORMULA_FIDELITY",
    "TABLE_FIGURE_FIDELITY",
    "PROVENANCE",
    "OWNER_REVIEW_REQUIRED",
)
SEVERITIES = ("critical", "major", "minor", "informational")

REQUIRED_OWNER_CHECK_FIELDS = (
    "text_complete",
    "reading_order_correct",
    "greek_symbols_preserved",
    "math_symbols_preserved",
    "formulas_preserved",
    "tables_usable",
    "figures_captions_preserved",
    "page_provenance_correct",
    "fabricated_content_absent",
)
OWNER_CHECK_VALUES = ("pass", "review", "fail", "not_applicable", PENDING)

GREEK_SYMBOLS = tuple("αβγδεζηθικλμνξοπρστυφχψω")
GREEK_SYMBOLS += tuple(symbol.upper() for symbol in GREEK_SYMBOLS)
MATH_SYMBOLS = ("±", "≤", "≥", "≈", "∞", "∑", "√", "∫", "°", "×", "÷", "−", "μ")
SYMBOL_SUBSTITUTIONS = {
    "α": ("a", "alpha"),
    "β": ("b", "beta"),
    "γ": ("y", "gamma"),
    "δ": ("d", "delta"),
    "θ": ("0", "theta"),
    "λ": ("lambda",),
    "μ": ("u", "micro", "mu"),
    "Ω": ("ohm", "omega", "O"),
    "≤": ("<=", "<"),
    "≥": (">=", ">"),
    "±": ("+-", "+/-"),
    "−": ("-",),
    "×": ("x", "*"),
    "÷": ("/",),
}


@dataclass(frozen=True)
class EngineeringOcrCapability:
    """Current OCR execution capability for the parser-side evaluation."""

    status: str
    supported: bool
    reason: str
    parser_ocr_runner_present: bool = False
    dependency_probe: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineeringOcrFinding:
    """One automated engineering OCR-fidelity finding."""

    code: str
    category: str
    severity: str
    message: str
    page_number: int | None = None
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineeringOcrMetric:
    """One deterministic OCR-fidelity metric."""

    name: str
    status: str
    value: object
    threshold: object | None = None
    message: str = ""
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class EngineeringOcrPageEvidence:
    """One page-level OCR-fidelity evidence record.

    Text/image references are local artifact references only. Sanitized reports
    must not include full extracted text, rendered pages, formulas, table
    contents, absolute paths, or proprietary procedure wording.
    """

    document_key: str
    filename: str
    pdf_page_index: int
    page_number: int
    source_page_image_reference: str | None
    native_text_baseline_reference: str | None
    ocr_text_candidate_reference: str | None
    source_profiles: tuple[str, ...]
    native_text_character_count: int
    ocr_text_character_count: int
    native_line_count: int
    ocr_line_count: int
    native_symbol_counts: Mapping[str, int]
    ocr_symbol_counts: Mapping[str, int]
    extracted_formula_count: int
    extracted_table_signal_count: int
    extracted_figure_signal_count: int
    reading_order_warnings: tuple[str, ...]
    symbol_normalization_warnings: tuple[str, ...]
    symbol_substitution_warnings: tuple[str, ...]
    page_provenance: Mapping[str, object]
    owner_checklist_status: str
    automated_outcome: str
    final_page_outcome: str
    needs_second_review: bool
    findings: tuple[EngineeringOcrFinding, ...]
    metrics: tuple[EngineeringOcrMetric, ...]


@dataclass(frozen=True)
class EngineeringOcrEvaluationResult:
    """Aggregate D.7a engineering OCR-fidelity result."""

    outcome: str
    source_filename: str | None
    source_sha256: str | None
    source_size_bytes: int | None
    expected_page_count: int
    observed_page_count: int
    capability: EngineeringOcrCapability
    page_results: tuple[EngineeringOcrPageEvidence, ...]
    finding_counts: Mapping[str, int]
    severity_counts: Mapping[str, int]
    page_outcome_counts: Mapping[str, int]
    source_profile_counts: Mapping[str, int]
    limitations: tuple[str, ...]
    summary: str
    evaluation_scope: str = ENGINEERING_OCR_SCOPE
    policy_name: str = ENGINEERING_OCR_POLICY_NAME
    policy_version: str = ENGINEERING_OCR_POLICY_VERSION
    parser_behavior_modified: bool = False
    source_pdf_modified: bool = False
    aviationrag_modified: bool = False
    embeddings_or_vector_store_used: bool = False
    ocr_run_by_evaluator: bool = False
    owner_review_required: bool = True


@dataclass(frozen=True)
class EngineeringOcrOwnerReviewDecision:
    """One explicit owner checklist for D.7a page disposition."""

    document_key: str
    pdf_page_index: int
    page_number: int
    review_status: str
    checklist: Mapping[str, str]
    finding_codes: tuple[str, ...] = ()
    accepted_limitation_codes: tuple[str, ...] = ()
    sanitized_notes: str | None = None


def detect_supported_ocr_capability() -> EngineeringOcrCapability:
    """Return the current parser-side OCR capability without running OCR."""
    pymupdf_has_ocr = hasattr(fitz.Page, "get_textpage_ocr")
    return EngineeringOcrCapability(
        status=NO_SUPPORTED_OCR_EXECUTION_PATH,
        supported=False,
        reason=(
            "techdoc-parser exposes native PDF text extraction and OCR-required "
            "detection, but no documented parser OCR runner or CLI path."
        ),
        parser_ocr_runner_present=False,
        dependency_probe={"pymupdf_page_get_textpage_ocr_present": pymupdf_has_ocr},
    )


def default_owner_review_decision(
    *,
    document_key: str,
    pdf_page_index: int,
    page_number: int,
) -> EngineeringOcrOwnerReviewDecision:
    """Return an explicit all-pending owner checklist template."""
    return EngineeringOcrOwnerReviewDecision(
        document_key=document_key,
        pdf_page_index=pdf_page_index,
        page_number=page_number,
        review_status=PENDING,
        checklist={field: PENDING for field in REQUIRED_OWNER_CHECK_FIELDS},
    )


def validate_owner_review_decision(
    data: Mapping[str, object],
    *,
    expected_document_key: str,
    expected_pdf_page_index: int,
) -> EngineeringOcrOwnerReviewDecision:
    """Validate one owner checklist and reject unsafe or ambiguous payloads."""
    allowed = {
        "document_key",
        "pdf_page_index",
        "page_number",
        "review_status",
        "checklist",
        "finding_codes",
        "accepted_limitation_codes",
        "sanitized_notes",
    }
    _reject_protected_payload(data)
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Unknown owner review fields: {sorted(unknown)}")

    document_key = _required_string(data, "document_key")
    if document_key != expected_document_key:
        raise ValueError("Owner review document_key does not match expected page.")
    pdf_page_index = _required_int(data, "pdf_page_index")
    if pdf_page_index != expected_pdf_page_index:
        raise ValueError("Owner review pdf_page_index does not match expected page.")
    page_number = _required_int(data, "page_number")
    if page_number != pdf_page_index + 1:
        raise ValueError("Owner review page_number must equal pdf_page_index + 1.")
    review_status = _required_string(data, "review_status")
    if review_status not in {PENDING, COMPLETED, NEEDS_SECOND_REVIEW, BLOCKED_REVIEW}:
        raise ValueError(f"Invalid owner review status: {review_status}")

    raw_checklist = data.get("checklist")
    if not isinstance(raw_checklist, Mapping):
        raise ValueError("Owner review checklist must include checklist object.")
    missing = set(REQUIRED_OWNER_CHECK_FIELDS) - set(raw_checklist)
    unknown_checks = set(raw_checklist) - set(REQUIRED_OWNER_CHECK_FIELDS)
    if missing:
        raise ValueError(f"Missing owner checklist fields: {sorted(missing)}")
    if unknown_checks:
        raise ValueError(f"Unknown owner checklist fields: {sorted(unknown_checks)}")
    checklist: dict[str, str] = {}
    for field_name in REQUIRED_OWNER_CHECK_FIELDS:
        value = raw_checklist.get(field_name)
        if not isinstance(value, str) or value not in OWNER_CHECK_VALUES:
            raise ValueError(f"Invalid owner checklist value for {field_name}: {value}")
        checklist[field_name] = value

    return EngineeringOcrOwnerReviewDecision(
        document_key=document_key,
        pdf_page_index=pdf_page_index,
        page_number=page_number,
        review_status=review_status,
        checklist=checklist,
        finding_codes=_string_tuple(data.get("finding_codes"), "finding_codes"),
        accepted_limitation_codes=_string_tuple(
            data.get("accepted_limitation_codes"),
            "accepted_limitation_codes",
        ),
        sanitized_notes=_optional_string(
            data.get("sanitized_notes"),
            "sanitized_notes",
        ),
    )


def evaluate_engineering_ocr_fidelity(
    *,
    source_path: str | Path,
    native_text_artifact: str | Path | None = None,
    ocr_text_artifact: str | Path | None = None,
    document_key: str = "wing_design_chapter_7",
    expected_page_count: int = EXPECTED_SOURCE_PAGES,
    owner_reviews: Mapping[int, EngineeringOcrOwnerReviewDecision] | None = None,
) -> EngineeringOcrEvaluationResult:
    """Evaluate supplied OCR artifacts, or return a controlled blocked result."""
    source = Path(source_path)
    source_profile = _load_source_profile(source)
    capability = detect_supported_ocr_capability()
    source_native_pages = cast(
        dict[int, str],
        source_profile.get("native_text_by_page", {}),
    )
    native_pages = (
        _load_page_text_artifact(native_text_artifact)
        if native_text_artifact is not None
        else source_native_pages
    )
    ocr_pages = (
        _load_page_text_artifact(ocr_text_artifact)
        if ocr_text_artifact is not None
        else {}
    )
    observed_page_count = _observed_page_count(source_profile, native_pages, ocr_pages)

    if not ocr_pages:
        page_results = _blocked_page_results(
            source_profile=source_profile,
            document_key=document_key,
            source_filename=source.name if source.exists() else None,
            expected_page_count=expected_page_count,
        )
        findings = (
            EngineeringOcrFinding(
                code=NO_SUPPORTED_OCR_EXECUTION_PATH,
                category="CAPABILITY_GAP",
                severity="critical",
                message=(
                    "No supported parser-side OCR execution path or supplied OCR "
                    "artifact is available for controlled D.7a comparison."
                ),
                details={
                    "parser_ocr_runner_present": capability.parser_ocr_runner_present,
                    "ocr_artifact_supplied": False,
                },
            ),
        )
        return _aggregate_result(
            outcome=BLOCKED,
            source_profile=source_profile,
            source=source,
            expected_page_count=expected_page_count,
            observed_page_count=observed_page_count,
            capability=capability,
            page_results=page_results,
            extra_findings=findings,
            limitations=(
                "OCR was not run by the evaluator.",
                "No parser OCR implementation or documented OCR CLI path exists.",
                "OCR fidelity cannot be accepted until an owner review is completed.",
            ),
            summary=(
                "D.7a is blocked: techdoc-parser can characterize the source PDF "
                "and detect OCR-required pages, but it cannot produce a supported "
                "OCR candidate for fidelity comparison."
            ),
        )

    page_numbers = sorted(set(native_pages) | set(ocr_pages))
    page_results = tuple(
        evaluate_engineering_ocr_page(
            document_key=document_key,
            filename=source.name,
            pdf_page_index=page_number - 1,
            page_number=page_number,
            native_text=native_pages.get(page_number, ""),
            ocr_text=ocr_pages.get(page_number, ""),
            source_image_reference=f"{document_key}/page_{page_number}/page.png",
            native_text_reference=(
                f"{document_key}/page_{page_number}/native_text_baseline.txt"
            ),
            ocr_text_reference=f"{document_key}/page_{page_number}/ocr_candidate.txt",
            owner_review=owner_reviews.get(page_number) if owner_reviews else None,
        )
        for page_number in page_numbers
    )
    outcome = _corpus_outcome(page_results)
    return _aggregate_result(
        outcome=outcome,
        source_profile=source_profile,
        source=source,
        expected_page_count=expected_page_count,
        observed_page_count=observed_page_count,
        capability=replace(
            capability,
            status=OCR_ARTIFACT_SUPPLIED,
            supported=True,
            reason=(
                "OCR candidate artifact supplied for evaluation; evaluator did "
                "not run OCR."
            ),
        ),
        page_results=page_results,
        limitations=(
            "OCR candidate text was supplied as an artifact; the evaluator did "
            "not run OCR.",
            "Automated checks do not prove visual OCR fidelity.",
            "Owner review is required before PASS or accepted limitation claims.",
        ),
        summary=f"D.7a evaluated {len(page_results)} page OCR artifact(s).",
    )


def evaluate_engineering_ocr_page(
    *,
    document_key: str,
    filename: str,
    pdf_page_index: int,
    page_number: int,
    native_text: str,
    ocr_text: str,
    source_image_reference: str | None = None,
    native_text_reference: str | None = None,
    ocr_text_reference: str | None = None,
    owner_review: EngineeringOcrOwnerReviewDecision | None = None,
) -> EngineeringOcrPageEvidence:
    """Evaluate one page's native baseline text against one OCR candidate."""
    native = _normalize_text(native_text)
    ocr = _normalize_text(ocr_text)
    profiles = _classify_page_profiles(native, ocr)
    native_symbols = _symbol_counts(native)
    ocr_symbols = _symbol_counts(ocr)
    findings: list[EngineeringOcrFinding] = []
    metrics: list[EngineeringOcrMetric] = []

    native_chars = len(native)
    ocr_chars = len(ocr)
    coverage = _coverage_ratio(native, ocr)
    coverage_status = (
        "pass" if coverage >= 0.9 else "review" if coverage >= 0.75 else "fail"
    )
    metrics.append(
        EngineeringOcrMetric(
            name="character_coverage_ratio",
            status=coverage_status,
            value=round(coverage, 4),
            threshold=0.9,
        )
    )
    if native_chars and not ocr_chars:
        findings.append(
            _page_finding(
                "OCR_TEXT_EMPTY",
                "TEXT_FIDELITY",
                "critical",
                "OCR candidate text is empty while native baseline text is present.",
                page_number,
            )
        )
    elif coverage < 0.75:
        findings.append(
            _page_finding(
                "OCR_TEXT_COVERAGE_LOW",
                "TEXT_FIDELITY",
                "major",
                "OCR candidate text has low character coverage against baseline.",
                page_number,
                {"coverage_ratio": round(coverage, 4)},
            )
        )

    line_warnings = _reading_order_warnings(native, ocr)
    for warning in line_warnings:
        findings.append(
            _page_finding(
                warning,
                "READING_ORDER",
                "major",
                "Automated line-order comparison requires owner review.",
                page_number,
            )
        )
    substitution_warnings = _symbol_substitution_warnings(native, ocr)
    for warning in substitution_warnings:
        findings.append(
            _page_finding(
                warning,
                "SYMBOL_FIDELITY",
                "major",
                "Potential OCR symbol substitution requires owner review.",
                page_number,
            )
        )
    normalization_warnings = _normalization_warnings(native_text, ocr_text)
    symbol_status = "pass" if not substitution_warnings else "review"
    metrics.append(
        EngineeringOcrMetric(
            name="controlled_symbol_preservation",
            status=symbol_status,
            value={
                "native_symbol_total": sum(native_symbols.values()),
                "ocr_symbol_total": sum(ocr_symbols.values()),
                "warning_count": len(substitution_warnings),
            },
        )
    )
    formula_count = _formula_signal_count(ocr)
    table_count = _table_signal_count(ocr)
    figure_count = _figure_signal_count(ocr)
    metrics.extend(
        (
            EngineeringOcrMetric(
                name="formula_signal_count",
                status="pass",
                value=formula_count,
            ),
            EngineeringOcrMetric(
                name="table_signal_count",
                status="pass",
                value=table_count,
            ),
            EngineeringOcrMetric(
                name="figure_signal_count",
                status="pass",
                value=figure_count,
            ),
        )
    )
    if native_chars and ocr_chars and _token_set(ocr) - _token_set(native):
        findings.append(
            _page_finding(
                "OCR_EXTRA_TOKEN_REVIEW",
                "TEXT_FIDELITY",
                "minor",
                "OCR candidate contains tokens not found in the native baseline.",
                page_number,
            )
        )

    automated_outcome = _automated_outcome(findings, metrics)
    if owner_review is None:
        owner_status = PENDING
        final_outcome = REVIEW
        needs_second_review = False
        findings.append(
            _page_finding(
                "OWNER_REVIEW_PENDING",
                "OWNER_REVIEW_REQUIRED",
                "major",
                "Owner review is required before final OCR-fidelity acceptance.",
                page_number,
            )
        )
    else:
        owner_status = owner_review.review_status
        final_outcome, needs_second_review = _final_page_outcome(
            automated_outcome,
            owner_review,
        )

    return EngineeringOcrPageEvidence(
        document_key=document_key,
        filename=filename,
        pdf_page_index=pdf_page_index,
        page_number=page_number,
        source_page_image_reference=source_image_reference,
        native_text_baseline_reference=native_text_reference,
        ocr_text_candidate_reference=ocr_text_reference,
        source_profiles=profiles,
        native_text_character_count=native_chars,
        ocr_text_character_count=ocr_chars,
        native_line_count=len(_significant_lines(native)),
        ocr_line_count=len(_significant_lines(ocr)),
        native_symbol_counts=native_symbols,
        ocr_symbol_counts=ocr_symbols,
        extracted_formula_count=formula_count,
        extracted_table_signal_count=table_count,
        extracted_figure_signal_count=figure_count,
        reading_order_warnings=line_warnings,
        symbol_normalization_warnings=normalization_warnings,
        symbol_substitution_warnings=substitution_warnings,
        page_provenance={
            "document_key": document_key,
            "filename": filename,
            "pdf_page_index": pdf_page_index,
            "page_number": page_number,
        },
        owner_checklist_status=owner_status,
        automated_outcome=automated_outcome,
        final_page_outcome=final_outcome,
        needs_second_review=needs_second_review,
        findings=tuple(findings),
        metrics=tuple(metrics),
    )


def engineering_ocr_page_to_dict(
    page: EngineeringOcrPageEvidence,
) -> dict[str, Any]:
    """Serialize one page without source text or absolute paths."""
    return {
        "document_key": page.document_key,
        "filename": page.filename,
        "pdf_page_index": page.pdf_page_index,
        "page_number": page.page_number,
        "source_page_image_reference": page.source_page_image_reference,
        "native_text_baseline_reference": page.native_text_baseline_reference,
        "ocr_text_candidate_reference": page.ocr_text_candidate_reference,
        "source_profiles": list(page.source_profiles),
        "native_text_character_count": page.native_text_character_count,
        "ocr_text_character_count": page.ocr_text_character_count,
        "native_line_count": page.native_line_count,
        "ocr_line_count": page.ocr_line_count,
        "native_symbol_counts": dict(page.native_symbol_counts),
        "ocr_symbol_counts": dict(page.ocr_symbol_counts),
        "extracted_formula_count": page.extracted_formula_count,
        "extracted_table_signal_count": page.extracted_table_signal_count,
        "extracted_figure_signal_count": page.extracted_figure_signal_count,
        "reading_order_warnings": list(page.reading_order_warnings),
        "symbol_normalization_warnings": list(page.symbol_normalization_warnings),
        "symbol_substitution_warnings": list(page.symbol_substitution_warnings),
        "page_provenance": dict(page.page_provenance),
        "owner_checklist_status": page.owner_checklist_status,
        "automated_outcome": page.automated_outcome,
        "final_page_outcome": page.final_page_outcome,
        "needs_second_review": page.needs_second_review,
        "findings": [_finding_to_dict(finding) for finding in page.findings],
        "metrics": [_metric_to_dict(metric) for metric in page.metrics],
    }


def engineering_ocr_result_to_dict(
    result: EngineeringOcrEvaluationResult,
) -> dict[str, Any]:
    """Serialize the aggregate result as a sanitized dictionary."""
    return {
        "evaluation_scope": result.evaluation_scope,
        "policy_name": result.policy_name,
        "policy_version": result.policy_version,
        "outcome": result.outcome,
        "source_filename": result.source_filename,
        "source_sha256": result.source_sha256,
        "source_size_bytes": result.source_size_bytes,
        "expected_page_count": result.expected_page_count,
        "observed_page_count": result.observed_page_count,
        "capability": {
            "status": result.capability.status,
            "supported": result.capability.supported,
            "reason": result.capability.reason,
            "parser_ocr_runner_present": result.capability.parser_ocr_runner_present,
            "dependency_probe": dict(result.capability.dependency_probe),
        },
        "page_count": len(result.page_results),
        "finding_counts": dict(result.finding_counts),
        "severity_counts": dict(result.severity_counts),
        "page_outcome_counts": dict(result.page_outcome_counts),
        "source_profile_counts": dict(result.source_profile_counts),
        "limitations": list(result.limitations),
        "summary": result.summary,
        "parser_behavior_modified": result.parser_behavior_modified,
        "source_pdf_modified": result.source_pdf_modified,
        "aviationrag_modified": result.aviationrag_modified,
        "embeddings_or_vector_store_used": result.embeddings_or_vector_store_used,
        "ocr_run_by_evaluator": result.ocr_run_by_evaluator,
        "owner_review_required": result.owner_review_required,
        "pages": [engineering_ocr_page_to_dict(page) for page in result.page_results],
        "privacy": {
            "sanitized": True,
            "contains_source_text": False,
            "contains_rendered_images": False,
            "contains_absolute_paths": False,
        },
    }


def engineering_ocr_result_to_json(result: EngineeringOcrEvaluationResult) -> str:
    """Serialize the aggregate result to deterministic JSON."""
    return (
        json.dumps(
            engineering_ocr_result_to_dict(result),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def engineering_ocr_result_to_markdown(result: EngineeringOcrEvaluationResult) -> str:
    """Serialize the aggregate result to sanitized Markdown."""
    lines = [
        "# Engineering OCR Fidelity Evaluation",
        "",
        f"evaluation_scope: {result.evaluation_scope}",
        f"policy_name: {result.policy_name}",
        f"policy_version: {result.policy_version}",
        f"outcome: {result.outcome}",
        "ocr_run_by_evaluator: false",
        "parser_behavior_modified: false",
        "source_pdf_modified: false",
        "aviationrag_modified: false",
        "embeddings_or_vector_store_used: false",
        "",
        "## Source",
        "",
        f"- Filename: `{result.source_filename}`",
        f"- SHA-256: `{result.source_sha256}`",
        f"- Size bytes: `{result.source_size_bytes}`",
        f"- Expected pages: `{result.expected_page_count}`",
        f"- Observed pages: `{result.observed_page_count}`",
        "",
        "## Capability",
        "",
        f"- Status: `{result.capability.status}`",
        f"- Supported: `{result.capability.supported}`",
        f"- Reason: {result.capability.reason}",
        "",
        "## Summary",
        "",
        f"- {result.summary}",
        f"- Page outcomes: `{dict(result.page_outcome_counts)}`",
        f"- Finding counts: `{dict(result.finding_counts)}`",
        f"- Severity counts: `{dict(result.severity_counts)}`",
        f"- Source profiles: `{dict(result.source_profile_counts)}`",
        "",
        "## Page Evidence",
        "",
        "| Page | Profiles | Native chars | OCR chars | Owner status | Final |",
        "| ---: | --- | ---: | ---: | --- | --- |",
    ]
    for page in result.page_results:
        lines.append(
            f"| {page.page_number} | `{', '.join(page.source_profiles)}` | "
            f"{page.native_text_character_count} | "
            f"{page.ocr_text_character_count} | "
            f"`{page.owner_checklist_status}` | `{page.final_page_outcome}` |"
        )
    lines.extend(
        [
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
            "rendered page images, formulas, table contents, absolute paths, "
            "or proprietary procedure wording.",
        ]
    )
    return "\n".join(lines) + "\n"


def owner_review_decision_to_dict(
    decision: EngineeringOcrOwnerReviewDecision,
) -> dict[str, object]:
    """Serialize an owner review decision."""
    return {
        "document_key": decision.document_key,
        "pdf_page_index": decision.pdf_page_index,
        "page_number": decision.page_number,
        "review_status": decision.review_status,
        "checklist": dict(decision.checklist),
        "finding_codes": list(decision.finding_codes),
        "accepted_limitation_codes": list(decision.accepted_limitation_codes),
        "sanitized_notes": decision.sanitized_notes,
    }


def load_owner_review_decisions(
    paths: Sequence[str | Path],
    *,
    document_key: str,
) -> dict[int, EngineeringOcrOwnerReviewDecision]:
    """Load owner review checklist files keyed by page number."""
    decisions: dict[int, EngineeringOcrOwnerReviewDecision] = {}
    for path_value in paths:
        data = json.loads(Path(path_value).read_text(encoding="utf-8"))
        if not isinstance(data, Mapping):
            raise ValueError(f"Owner review checklist must be an object: {path_value}")
        pdf_page_index = _required_int(data, "pdf_page_index")
        decision = validate_owner_review_decision(
            data,
            expected_document_key=document_key,
            expected_pdf_page_index=pdf_page_index,
        )
        decisions[decision.page_number] = decision
    return decisions


def load_engineering_ocr_text_artifact(path_value: str | Path) -> dict[int, str]:
    """Load a page-keyed native or OCR text artifact."""
    return _load_page_text_artifact(path_value)


def _aggregate_result(
    *,
    outcome: str,
    source_profile: Mapping[str, object],
    source: Path,
    expected_page_count: int,
    observed_page_count: int,
    capability: EngineeringOcrCapability,
    page_results: tuple[EngineeringOcrPageEvidence, ...],
    limitations: tuple[str, ...],
    summary: str,
    extra_findings: tuple[EngineeringOcrFinding, ...] = (),
) -> EngineeringOcrEvaluationResult:
    finding_codes = Counter(
        finding.code for page in page_results for finding in page.findings
    )
    finding_codes.update(finding.code for finding in extra_findings)
    severity_counts = Counter(
        finding.severity for page in page_results for finding in page.findings
    )
    severity_counts.update(finding.severity for finding in extra_findings)
    page_outcome_counts = Counter(page.final_page_outcome for page in page_results)
    profile_counts = Counter(
        profile for page in page_results for profile in page.source_profiles
    )
    return EngineeringOcrEvaluationResult(
        outcome=outcome,
        source_filename=source.name if source.exists() else None,
        source_sha256=_optional_string(source_profile.get("sha256"), "sha256"),
        source_size_bytes=_optional_int(source_profile.get("size_bytes")),
        expected_page_count=expected_page_count,
        observed_page_count=observed_page_count,
        capability=capability,
        page_results=page_results,
        finding_counts=dict(sorted(finding_codes.items())),
        severity_counts=dict(sorted(severity_counts.items())),
        page_outcome_counts=dict(sorted(page_outcome_counts.items())),
        source_profile_counts=dict(sorted(profile_counts.items())),
        limitations=limitations,
        summary=summary,
    )


def _blocked_page_results(
    *,
    source_profile: Mapping[str, object],
    document_key: str,
    source_filename: str | None,
    expected_page_count: int,
) -> tuple[EngineeringOcrPageEvidence, ...]:
    pages = source_profile.get("page_profiles")
    if isinstance(pages, Sequence) and not isinstance(pages, str | bytes):
        records = pages
    else:
        records = []
    results: list[EngineeringOcrPageEvidence] = []
    if not records:
        records = [
            {
                "page_number": number,
                "pdf_page_index": number - 1,
                "native_text_character_count": 0,
                "source_profiles": ("source_unavailable",),
            }
            for number in range(1, expected_page_count + 1)
        ]
    for raw in records:
        if not isinstance(raw, Mapping):
            continue
        page_number = _required_int(raw, "page_number")
        native_chars = _required_int(raw, "native_text_character_count")
        profiles_value = raw.get("source_profiles", ("native_text",))
        profiles = (
            tuple(str(item) for item in profiles_value)
            if isinstance(profiles_value, Sequence)
            and not isinstance(profiles_value, str | bytes)
            else ("native_text",)
        )
        finding = EngineeringOcrFinding(
            code="OCR_COMPARISON_NOT_RUN",
            category="CAPABILITY_GAP",
            severity="critical",
            message="OCR comparison was not run for this page.",
            page_number=page_number,
        )
        results.append(
            EngineeringOcrPageEvidence(
                document_key=document_key,
                filename=source_filename or "source_unavailable.pdf",
                pdf_page_index=page_number - 1,
                page_number=page_number,
                source_page_image_reference=None,
                native_text_baseline_reference=None,
                ocr_text_candidate_reference=None,
                source_profiles=profiles,
                native_text_character_count=native_chars,
                ocr_text_character_count=0,
                native_line_count=_optional_int(raw.get("native_line_count")) or 0,
                ocr_line_count=0,
                native_symbol_counts={},
                ocr_symbol_counts={},
                extracted_formula_count=_optional_int(raw.get("formula_signal_count"))
                or 0,
                extracted_table_signal_count=_optional_int(
                    raw.get("table_signal_count")
                )
                or 0,
                extracted_figure_signal_count=_optional_int(
                    raw.get("figure_signal_count")
                )
                or 0,
                reading_order_warnings=("OCR_COMPARISON_NOT_RUN",),
                symbol_normalization_warnings=(),
                symbol_substitution_warnings=(),
                page_provenance={
                    "document_key": document_key,
                    "filename": source_filename,
                    "pdf_page_index": page_number - 1,
                    "page_number": page_number,
                },
                owner_checklist_status=BLOCKED_REVIEW,
                automated_outcome=BLOCKED,
                final_page_outcome=BLOCKED,
                needs_second_review=False,
                findings=(finding,),
                metrics=(
                    EngineeringOcrMetric(
                        name="ocr_candidate_available",
                        status="fail",
                        value=False,
                    ),
                ),
            )
        )
    return tuple(results)


def _load_source_profile(source: Path) -> dict[str, object]:
    if not source.exists():
        return {
            "sha256": None,
            "size_bytes": None,
            "observed_page_count": 0,
            "native_text_by_page": {},
            "page_profiles": [],
        }
    digest = sha256(source.read_bytes()).hexdigest()
    pages: list[dict[str, object]] = []
    native_text: dict[int, str] = {}
    with fitz.open(source) as document:
        for page_index, page in enumerate(document):
            page_number = page_index + 1
            text = page.get_text("text") or ""
            normalized = _normalize_text(text)
            native_text[page_number] = normalized
            image_count = len(page.get_images(full=True))
            profiles = _classify_page_profiles(normalized, "")
            if image_count:
                profiles = tuple(sorted(set(profiles) | {"image_content_present"}))
            pages.append(
                {
                    "page_number": page_number,
                    "pdf_page_index": page_index,
                    "native_text_character_count": len(normalized),
                    "native_line_count": len(_significant_lines(normalized)),
                    "image_count": image_count,
                    "source_profiles": profiles,
                    "formula_signal_count": _formula_signal_count(normalized),
                    "table_signal_count": _table_signal_count(normalized),
                    "figure_signal_count": _figure_signal_count(normalized),
                }
            )
        observed_page_count = document.page_count
    return {
        "sha256": digest,
        "size_bytes": source.stat().st_size,
        "observed_page_count": observed_page_count,
        "native_text_by_page": native_text,
        "page_profiles": pages,
    }


def _load_page_text_artifact(path_value: str | Path) -> dict[int, str]:
    path = Path(path_value)
    if not path.exists():
        raise FileNotFoundError(f"Text artifact not found: {path}")
    if path.is_dir():
        pages: dict[int, str] = {}
        for file_path in sorted(path.glob("*.txt")):
            match = re.search(r"(?:page[_-]?)?(\d+)", file_path.stem, re.I)
            if match:
                pages[int(match.group(1))] = file_path.read_text(encoding="utf-8")
        return pages
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return _page_text_from_json(data)
    return {1: path.read_text(encoding="utf-8")}


def _page_text_from_json(data: object) -> dict[int, str]:
    if isinstance(data, Mapping):
        raw_pages = data.get("pages")
        if isinstance(raw_pages, Sequence) and not isinstance(
            raw_pages,
            str | bytes,
        ):
            pages: dict[int, str] = {}
            for item in raw_pages:
                if not isinstance(item, Mapping):
                    continue
                page_number = int(item.get("page_number", item.get("page", 0)))
                text = item.get(
                    "text",
                    item.get("ocr_text", item.get("native_text", "")),
                )
                if page_number and isinstance(text, str):
                    pages[page_number] = text
            return pages
        return {
            int(key): str(value)
            for key, value in data.items()
            if str(key).isdigit() and isinstance(value, str)
        }
    raise ValueError("Text artifact JSON must be an object.")


def _observed_page_count(
    source_profile: Mapping[str, object],
    native_pages: Mapping[int, str],
    ocr_pages: Mapping[int, str],
) -> int:
    observed = _optional_int(source_profile.get("observed_page_count")) or 0
    artifact_max = max((*native_pages.keys(), *ocr_pages.keys(), 0))
    return max(observed, artifact_max)


def _classify_page_profiles(native: str, ocr: str) -> tuple[str, ...]:
    text = native or ocr
    if native:
        profiles = {"native_text"}
    elif ocr:
        profiles = {"ocr_text_only"}
    else:
        profiles = {"blank_or_no_text"}
    if len(text) < 250:
        profiles.add("short_text")
    if _formula_signal_count(text) >= 1:
        profiles.add("formula_heavy")
    if sum(_symbol_counts(text).values()) >= 3:
        profiles.add("greek_or_symbol_heavy")
    if _table_signal_count(text):
        profiles.add("table_candidate")
    if _figure_signal_count(text):
        profiles.add("figure_heavy")
    lines = _significant_lines(text)
    if len(lines) >= 8 and _line_length_variance(lines) > 45:
        profiles.add("mixed_layout")
    return tuple(sorted(profiles))


def _normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")


def _coverage_ratio(native: str, ocr: str) -> float:
    if not native:
        return 1.0 if not ocr else 0.0
    return min(len(ocr), len(native)) / len(native)


def _symbol_counts(text: str) -> dict[str, int]:
    counter = Counter(
        char for char in text if char in GREEK_SYMBOLS or char in MATH_SYMBOLS
    )
    return dict(sorted(counter.items()))


def _symbol_substitution_warnings(native: str, ocr: str) -> tuple[str, ...]:
    native_symbols = _symbol_counts(native)
    ocr_symbols = _symbol_counts(ocr)
    warnings: list[str] = []
    ocr_lower = ocr.lower()
    for symbol, replacements in SYMBOL_SUBSTITUTIONS.items():
        if native_symbols.get(symbol, 0) <= ocr_symbols.get(symbol, 0):
            continue
        for replacement in replacements:
            if replacement.lower() in ocr_lower:
                warnings.append(f"POSSIBLE_SYMBOL_SUBSTITUTION_{_symbol_name(symbol)}")
                break
    return tuple(sorted(set(warnings)))


def _normalization_warnings(native_text: str, ocr_text: str) -> tuple[str, ...]:
    warnings: list[str] = []
    if unicodedata.normalize("NFC", native_text) != native_text:
        warnings.append("NATIVE_TEXT_NOT_NFC")
    if unicodedata.normalize("NFC", ocr_text) != ocr_text:
        warnings.append("OCR_TEXT_NOT_NFC")
    return tuple(warnings)


def _reading_order_warnings(native: str, ocr: str) -> tuple[str, ...]:
    native_lines = _significant_lines(native)
    ocr_lines = _significant_lines(ocr)
    if len(native_lines) < 3 or len(ocr_lines) < 3:
        return ()
    first_native = _line_tokens(native_lines[0])
    last_native = _line_tokens(native_lines[-1])
    first_ocr = _line_tokens(ocr_lines[0])
    last_ocr = _line_tokens(ocr_lines[-1])
    warnings: list[str] = []
    if first_native and first_native <= _token_set(ocr_lines[-1]):
        warnings.append("POSSIBLE_READING_ORDER_INVERSION")
    if last_native and last_native <= _token_set(ocr_lines[0]):
        warnings.append("POSSIBLE_READING_ORDER_INVERSION")
    if len(ocr_lines) > len(native_lines) * 2:
        warnings.append("POSSIBLE_LINE_FRAGMENTATION")
    if len(native_lines) > len(ocr_lines) * 2:
        warnings.append("POSSIBLE_LINE_COLLAPSE")
    first_last = first_ocr | last_ocr
    if native_lines and ocr_lines and not first_last:
        warnings.append("READING_ORDER_NOT_MEASURABLE")
    return tuple(sorted(set(warnings)))


def _significant_lines(text: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def _line_tokens(line: str) -> set[str]:
    return _token_set(line)


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9]+", text.lower()))


def _line_length_variance(lines: Sequence[str]) -> int:
    lengths = [len(line) for line in lines]
    if not lengths:
        return 0
    return max(lengths) - min(lengths)


def _formula_signal_count(text: str) -> int:
    patterns = (
        r"[A-Za-zα-ωΑ-Ω]\s*=\s*",
        r"[∑√∫]",
        r"\b(eq\.?|equation)\b",
        r"[≤≥±]",
    )
    return sum(len(re.findall(pattern, text, re.I)) for pattern in patterns)


def _table_signal_count(text: str) -> int:
    return len(re.findall(r"\b(table|row|column|tabular)\b", text, re.I))


def _figure_signal_count(text: str) -> int:
    return len(re.findall(r"\b(fig\.?|figure|diagram|chart)\b", text, re.I))


def _automated_outcome(
    findings: Sequence[EngineeringOcrFinding],
    metrics: Sequence[EngineeringOcrMetric],
) -> str:
    if any(finding.severity == "critical" for finding in findings):
        return FAIL
    if any(metric.status in {"fail", "review"} for metric in metrics) or findings:
        return REVIEW
    return PASS


def _final_page_outcome(
    automated_outcome: str,
    owner_review: EngineeringOcrOwnerReviewDecision,
) -> tuple[str, bool]:
    if owner_review.review_status == NEEDS_SECOND_REVIEW:
        return REVIEW, True
    if owner_review.review_status == BLOCKED_REVIEW:
        return BLOCKED, False
    if owner_review.review_status != COMPLETED:
        return REVIEW, False
    values = set(owner_review.checklist.values())
    if "fail" in values or owner_review.finding_codes:
        return FAIL, False
    if "review" in values:
        return REVIEW, False
    if automated_outcome == FAIL:
        return FAIL, False
    if automated_outcome == REVIEW and owner_review.accepted_limitation_codes:
        return ACCEPTED_WITH_LIMITATIONS, False
    if automated_outcome == REVIEW:
        return REVIEW, False
    return PASS, False


def _corpus_outcome(page_results: Sequence[EngineeringOcrPageEvidence]) -> str:
    final = Counter(page.final_page_outcome for page in page_results)
    if final.get(BLOCKED):
        return BLOCKED
    if final.get(FAIL):
        return FAIL
    if final.get(NEEDS_SECOND_REVIEW):
        return OWNER_REVIEW_REQUIRED
    if final.get(REVIEW):
        return OWNER_REVIEW_REQUIRED
    if final and all(page.final_page_outcome == PASS for page in page_results):
        return PASS
    if final and all(
        page.final_page_outcome in {PASS, ACCEPTED_WITH_LIMITATIONS}
        for page in page_results
    ):
        return ACCEPTED_WITH_LIMITATIONS
    return OWNER_REVIEW_REQUIRED


def _page_finding(
    code: str,
    category: str,
    severity: str,
    message: str,
    page_number: int,
    details: Mapping[str, object] | None = None,
) -> EngineeringOcrFinding:
    if category not in FINDING_CATEGORIES:
        raise ValueError(f"Unknown finding category: {category}")
    if severity not in SEVERITIES:
        raise ValueError(f"Unknown finding severity: {severity}")
    return EngineeringOcrFinding(
        code=code,
        category=category,
        severity=severity,
        message=message,
        page_number=page_number,
        details={} if details is None else dict(details),
    )


def _finding_to_dict(finding: EngineeringOcrFinding) -> dict[str, object]:
    return {
        "code": finding.code,
        "category": finding.category,
        "severity": finding.severity,
        "message": finding.message,
        "page_number": finding.page_number,
        "details": dict(finding.details),
    }


def _metric_to_dict(metric: EngineeringOcrMetric) -> dict[str, object]:
    return {
        "name": metric.name,
        "status": metric.status,
        "value": metric.value,
        "threshold": metric.threshold,
        "message": metric.message,
        "details": dict(metric.details),
    }


def _symbol_name(symbol: str) -> str:
    try:
        return unicodedata.name(symbol).replace(" ", "_")
    except ValueError:
        return hex(ord(symbol))


def _reject_protected_payload(value: object) -> None:
    protected = {
        "absolute_path",
        "source_path",
        "pdf_path",
        "source_text",
        "native_text",
        "ocr_text",
        "formula_text",
        "table_contents",
        "image_path",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in protected:
                raise ValueError(f"Protected field is not allowed: {key}")
            _reject_windows_path(str(child))
            _reject_protected_payload(child)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for child in value:
            _reject_protected_payload(child)
    elif isinstance(value, str):
        _reject_windows_path(value)


def _reject_windows_path(value: str) -> None:
    parsed = PureWindowsPath(value)
    if parsed.is_absolute() or re.search(r"[A-Za-z]:\\", value):
        raise ValueError("Absolute paths are not allowed in owner review data.")


def _required_string(data: Mapping[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing required string field: {key}")
    return value


def _required_int(data: Mapping[str, object], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Missing required integer field: {key}")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return None


def _optional_string(value: object, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Invalid optional string field: {key}")
    return value


def _string_tuple(value: object, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise ValueError(f"{key} must be a list of strings.")
    result = tuple(item for item in value if isinstance(item, str))
    if len(result) != len(value):
        raise ValueError(f"{key} must contain only strings.")
    return result


__all__ = [
    "ACCEPTED_WITH_LIMITATIONS",
    "BLOCKED",
    "COMPLETED",
    "ENGINEERING_OCR_POLICY_NAME",
    "ENGINEERING_OCR_POLICY_VERSION",
    "ENGINEERING_OCR_SCOPE",
    "EXPECTED_SOURCE_PAGES",
    "FAIL",
    "NEEDS_SECOND_REVIEW",
    "NO_SUPPORTED_OCR_EXECUTION_PATH",
    "OWNER_REVIEW_REQUIRED",
    "PASS",
    "PENDING",
    "REVIEW",
    "REQUIRED_OWNER_CHECK_FIELDS",
    "EngineeringOcrCapability",
    "EngineeringOcrEvaluationResult",
    "EngineeringOcrFinding",
    "EngineeringOcrMetric",
    "EngineeringOcrOwnerReviewDecision",
    "EngineeringOcrPageEvidence",
    "default_owner_review_decision",
    "detect_supported_ocr_capability",
    "engineering_ocr_page_to_dict",
    "engineering_ocr_result_to_dict",
    "engineering_ocr_result_to_json",
    "engineering_ocr_result_to_markdown",
    "evaluate_engineering_ocr_fidelity",
    "evaluate_engineering_ocr_page",
    "load_owner_review_decisions",
    "load_engineering_ocr_text_artifact",
    "owner_review_decision_to_dict",
    "validate_owner_review_decision",
]
