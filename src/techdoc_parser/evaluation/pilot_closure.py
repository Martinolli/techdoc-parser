"""P0 pilot closure and accepted-limitation policy.

This module is evaluation-only. It does not parse PDFs, run OCR, change parser
behavior, write files, call external services, or authorize production
ingestion.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Any

from techdoc_parser.evaluation.source_accuracy import FAIL, PASS, REVIEW
from techdoc_parser.evaluation.visual_review import (
    ACCEPTED,
    ACCEPTED_WITH_LIMITATIONS,
    COMPLETED,
    PENDING,
    REJECTED,
    P0PilotAcceptanceResult,
)

P0_PILOT_CLOSURE_SCHEMA = "p0-pilot-closure"
P0_PILOT_CLOSURE_SCHEMA_VERSION = "1.0"
EXPECTED_P0_PAGE_COUNT = 32

STALE_REVIEW_STATE_CODES = (
    "VISUAL_REVIEW_PENDING",
    "VISUAL_CHECK_PENDING",
)
OBSOLETE_RECOMMENDATIONS = ("second_review_or_formal_limitation_acceptance",)
DOWNSTREAM_AUTHORIZATIONS: Mapping[str, bool] = {
    "controlled_downstream_use_authorized": True,
    "full_corpus_ingestion_authorized": False,
    "full_document_accuracy_established": False,
    "real_embedding_rebuild_authorized": False,
    "astra_rebuild_authorized": False,
    "faiss_rebuild_authorized": False,
}
AUTHORIZED_NEXT_WORK = (
    "AviationRAG persisted ChunkRecord mapping design",
    "controlled local sample-persistence dry run",
)
NOT_AUTHORIZED_WORK = (
    "full corpus reprocessing",
    "production migration",
    "embedding regeneration",
    "Astra reset/rebuild",
    "FAISS reset/rebuild",
    "production retrieval activation",
)
ACTIVE_LIMITATION_DISPOSITIONS: Mapping[str, str] = {
    "DUPLICATE_TEXT_LINES": "active_accepted_limitation",
    "READING_ORDER_VISUAL_REVIEW_REQUIRED": "resolved_by_visual_review",
    "READING_ORDER_INVERSION": "resolved_by_visual_review",
    "CROSS_REFERENCE_EVIDENCE_NOT_AUTOMATED": "resolved_by_visual_review",
    "CHUNK_SECTION_CROSSING_REVIEW": "active_accepted_limitation",
    "FIGURE_CAPTION_EVIDENCE_NOT_AUTOMATED": "resolved_by_visual_review",
    "TABLE_CANDIDATE_ONLY": "active_accepted_limitation",
    "TABLE_EVIDENCE_NOT_AUTOMATED": "resolved_by_visual_review",
    "ADMONITION_EVIDENCE_NOT_AUTOMATED": "resolved_by_visual_review",
    "VISUAL_REVIEW_PENDING": "resolved_review_state",
    "VISUAL_CHECK_PENDING": "resolved_review_state",
}
ACCEPTED_LIMITATION_REGISTRY: Mapping[str, Mapping[str, object]] = {
    "DUPLICATE_TEXT_LINES": {
        "category": "PARSER_OR_SOURCE_PROXY_TEXT_LIMITATION",
        "severity": "minor",
        "disposition": "accepted_for_pilot",
        "downstream_control": (
            "Do not treat duplicate-line evidence alone as a blocking parser "
            "defect after completed owner review."
        ),
        "corrective_status": "deferred_refinement",
        "message": "Duplicate-line evidence remains accepted for the P0 pilot.",
    },
    "CHUNK_SECTION_CROSSING_REVIEW": {
        "category": "CHUNK_BOUNDARY_LIMITATION",
        "severity": "minor",
        "disposition": "accepted_for_pilot",
        "downstream_control": (
            "Retain source-page provenance and do not infer final section "
            "boundaries from representative-page review alone."
        ),
        "corrective_status": "deferred_refinement",
        "message": "Chunk section-crossing review remains accepted for the pilot.",
    },
    "TABLE_CANDIDATE_ONLY": {
        "category": "TABLE_CAPABILITY_LIMITATION",
        "severity": "minor",
        "disposition": "accepted_for_pilot",
        "downstream_control": (
            "Treat candidate table evidence as a review signal, not proof of "
            "reconstructed tabular content."
        ),
        "corrective_status": "deferred_refinement",
        "message": "Candidate-level table evidence remains an accepted limitation.",
    },
    "TABLE_FALSE_POSITIVE_ON_FIGURE_PAGE": {
        "category": "CONTENT_TYPE_MISCLASSIFICATION",
        "severity": "minor",
        "disposition": "accepted_for_pilot",
        "downstream_control": (
            "Do not treat candidate table classification alone as proof of "
            "tabular content. Preserve source blocks and figure evidence for "
            "downstream review."
        ),
        "corrective_status": "deferred_refinement",
        "message": (
            "A reviewed horizontal figure page was classified with one table "
            "block even though owner review accepted the figure content."
        ),
    },
}


@dataclass(frozen=True)
class AcceptedPilotLimitation:
    """One sanitized accepted limitation or confirmed nonblocking issue."""

    code: str
    category: str
    severity: str
    disposition: str
    affected_document_keys: tuple[str, ...]
    affected_pages: tuple[int, ...]
    downstream_control: str | None
    corrective_status: str
    message: str

    def __post_init__(self) -> None:
        if self.severity not in {"minor", "moderate", "major"}:
            raise ValueError(
                f"Unsupported accepted limitation severity: {self.severity}"
            )
        if not self.code or not self.category or not self.disposition:
            raise ValueError(
                "Accepted limitations require code, category, and disposition."
            )
        if not self.corrective_status:
            raise ValueError("Accepted limitations require corrective_status.")
        if _looks_like_protected_text(self.message):
            raise ValueError("Accepted limitation message must be sanitized.")
        if self.downstream_control and _looks_like_protected_text(
            self.downstream_control
        ):
            raise ValueError(
                "Accepted limitation downstream_control must be sanitized."
            )
        object.__setattr__(
            self,
            "affected_document_keys",
            tuple(sorted(dict.fromkeys(self.affected_document_keys))),
        )
        object.__setattr__(
            self,
            "affected_pages",
            tuple(sorted(dict.fromkeys(self.affected_pages))),
        )


@dataclass(frozen=True)
class P0PilotClosureResult:
    """Deterministic sanitized P0 pilot closure result."""

    outcome: str
    review_completion_percentage: float
    page_outcome_counts: Mapping[str, int]
    document_outcomes: Mapping[str, str]
    historical_outcomes: Mapping[str, Any]
    historical_automated_findings: Mapping[str, int]
    historical_review_findings: Mapping[str, int]
    current_accepted_limitations: tuple[AcceptedPilotLimitation, ...]
    current_confirmed_nonblocking_issues: tuple[AcceptedPilotLimitation, ...]
    current_blocking_findings: tuple[str, ...]
    resolved_review_state_findings: tuple[str, ...]
    removed_obsolete_recommendations: tuple[str, ...]
    downstream_authorizations: Mapping[str, bool]
    authorized_next_work: tuple[str, ...]
    not_authorized_work: tuple[str, ...]
    corrective_backlog: tuple[str, ...]
    summary: Mapping[str, Any]


def accepted_pilot_limitation_to_dict(
    limitation: AcceptedPilotLimitation,
) -> dict[str, Any]:
    """Serialize one accepted limitation deterministically."""
    return {
        "affected_document_keys": list(limitation.affected_document_keys),
        "affected_pages": list(limitation.affected_pages),
        "category": limitation.category,
        "code": limitation.code,
        "corrective_status": limitation.corrective_status,
        "disposition": limitation.disposition,
        "downstream_control": limitation.downstream_control,
        "message": limitation.message,
        "severity": limitation.severity,
    }


def p0_pilot_closure_result_to_dict(
    result: P0PilotClosureResult,
) -> dict[str, Any]:
    """Serialize the final closure result without protected source material."""
    payload = {
        "accepted_limitations": [
            accepted_pilot_limitation_to_dict(item)
            for item in result.current_accepted_limitations
        ],
        "authorized_next_work": list(result.authorized_next_work),
        "blocking_finding_codes": list(result.current_blocking_findings),
        "confirmed_nonblocking_issues": [
            accepted_pilot_limitation_to_dict(item)
            for item in result.current_confirmed_nonblocking_issues
        ],
        "corrective_backlog": list(result.corrective_backlog),
        "document_outcomes": dict(result.document_outcomes),
        "downstream_authorizations": dict(result.downstream_authorizations),
        "historical_automated_findings": dict(result.historical_automated_findings),
        "historical_outcomes": dict(result.historical_outcomes),
        "historical_review_findings": dict(result.historical_review_findings),
        "not_authorized_work": list(result.not_authorized_work),
        "outcome": result.outcome,
        "page_outcome_counts": dict(result.page_outcome_counts),
        "review_completion_percentage": result.review_completion_percentage,
        "resolved_review_state_findings": list(result.resolved_review_state_findings),
        "removed_obsolete_recommendations": list(
            result.removed_obsolete_recommendations
        ),
        "schema_name": P0_PILOT_CLOSURE_SCHEMA,
        "schema_version": P0_PILOT_CLOSURE_SCHEMA_VERSION,
        "summary": dict(result.summary),
        "privacy": {
            "absolute_paths_included": False,
            "full_document_accuracy_established": False,
            "ocr_accuracy_established": False,
            "p1_p2_pages_reviewed": False,
            "rendered_images_committed": False,
            "reviewer_identity_included": False,
            "source_text_committed": False,
        },
    }
    _reject_protected_payload(payload)
    return payload


def p0_pilot_closure_result_to_json(result: P0PilotClosureResult) -> str:
    """Serialize closure JSON deterministically."""
    return (
        json.dumps(p0_pilot_closure_result_to_dict(result), indent=2, sort_keys=True)
        + "\n"
    )


def close_p0_pilot(
    *,
    visual_review_result: P0PilotAcceptanceResult,
    accepted_limitations: Sequence[AcceptedPilotLimitation],
) -> P0PilotClosureResult:
    """Close the completed P0 pilot without mutating the visual-review result."""
    pages = tuple(visual_review_result.page_results)
    if len(pages) != EXPECTED_P0_PAGE_COUNT:
        raise ValueError(
            f"P0 pilot closure requires {EXPECTED_P0_PAGE_COUNT} pages; "
            f"got {len(pages)}."
        )
    summary = dict(visual_review_result.summary)
    pending_pages = int(summary.get("pending_pages", 0))
    second_review_pages = int(summary.get("second_review_pages", 0))
    blocked_pages = int(summary.get("blocked_pages", 0))
    if pending_pages:
        raise ValueError("P0 pilot closure requires zero pending pages.")
    if second_review_pages:
        raise ValueError("P0 pilot closure requires zero second-review pages.")
    if blocked_pages:
        raise ValueError("P0 pilot closure requires zero blocked pages.")

    page_outcomes = _page_outcome_counts(pages)
    if page_outcomes.get(FAIL, 0):
        raise ValueError("P0 pilot closure cannot accept final FAIL pages.")

    active_limitations = _filter_current_accepted_limitations(accepted_limitations)
    _validate_unique_accepted_limitations(
        (*active_limitations, *_confirmed_nonblocking_issues(accepted_limitations))
    )
    if any(item.severity == "major" for item in accepted_limitations):
        raise ValueError(
            "Major accepted limitations require a separate evidence phase."
        )

    nonblocking = _confirmed_nonblocking_issues(accepted_limitations)
    outcome = (
        ACCEPTED_WITH_LIMITATIONS
        if active_limitations or nonblocking or page_outcomes.get(REVIEW, 0)
        else ACCEPTED
    )
    resolved_codes = _resolved_review_state_codes(visual_review_result)
    historical_automated, historical_review = _historical_finding_counts(
        visual_review_result
    )
    removed_recommendations = tuple(
        item
        for item in visual_review_result.corrective_phase_recommendations
        if item in OBSOLETE_RECOMMENDATIONS
    )
    clean_summary = {
        "accepted_limitation_count": len(active_limitations),
        "blocked_pages": blocked_pages,
        "completed_pages": int(summary.get("completed_pages", 0)),
        "confirmed_nonblocking_issue_count": len(nonblocking),
        "document_count": len(visual_review_result.document_outcomes),
        "final_page_outcomes": dict(page_outcomes),
        "full_corpus_ingestion_authorized": False,
        "page_count": len(pages),
        "pending_pages": pending_pages,
        "review_completion_state": "complete",
        "second_review_pages": second_review_pages,
    }
    result = P0PilotClosureResult(
        outcome=outcome,
        review_completion_percentage=float(
            summary.get("completion_percentage", _completion_percentage(pages))
        ),
        page_outcome_counts=dict(page_outcomes),
        document_outcomes=dict(sorted(visual_review_result.document_outcomes.items())),
        historical_outcomes=_historical_outcomes(),
        historical_automated_findings=dict(historical_automated),
        historical_review_findings=dict(historical_review),
        current_accepted_limitations=active_limitations,
        current_confirmed_nonblocking_issues=nonblocking,
        current_blocking_findings=tuple(visual_review_result.blocking_finding_codes),
        resolved_review_state_findings=resolved_codes,
        removed_obsolete_recommendations=removed_recommendations,
        downstream_authorizations=dict(DOWNSTREAM_AUTHORIZATIONS),
        authorized_next_work=AUTHORIZED_NEXT_WORK,
        not_authorized_work=NOT_AUTHORIZED_WORK,
        corrective_backlog=_corrective_backlog(active_limitations, nonblocking),
        summary=clean_summary,
    )
    _reject_protected_payload(p0_pilot_closure_result_to_dict(result))
    return result


def default_accepted_pilot_limitation(
    code: str,
    *,
    affected_document_keys: Sequence[str] = (),
    affected_pages: Sequence[int] = (),
) -> AcceptedPilotLimitation:
    """Create a known accepted limitation by code."""
    if code not in ACCEPTED_LIMITATION_REGISTRY:
        raise ValueError(f"Unknown accepted pilot limitation code: {code}")
    spec = ACCEPTED_LIMITATION_REGISTRY[code]
    return AcceptedPilotLimitation(
        code=code,
        category=str(spec["category"]),
        severity=str(spec["severity"]),
        disposition=str(spec["disposition"]),
        affected_document_keys=tuple(affected_document_keys),
        affected_pages=tuple(affected_pages),
        downstream_control=(
            str(spec["downstream_control"])
            if spec.get("downstream_control") is not None
            else None
        ),
        corrective_status=str(spec["corrective_status"]),
        message=str(spec["message"]),
    )


def load_p0_pilot_acceptance_result_from_report(
    data: Mapping[str, Any],
) -> P0PilotAcceptanceResult:
    """Load the sanitized visual-review report emitted by Phase 13I-c3."""
    from techdoc_parser.evaluation.source_accuracy import (
        SourceAccuracyFinding,
        SourceAccuracyPageResult,
    )

    raw_pages = data.get("page_results")
    if not isinstance(raw_pages, Sequence) or isinstance(raw_pages, str):
        raise ValueError("Visual-review report must include page_results.")
    pages = []
    for index, item in enumerate(raw_pages):
        if not isinstance(item, Mapping):
            raise ValueError("Visual-review page entries must be objects.")
        document_key = _required_string(item, "document_key")
        pdf_page_index = _required_int(item, "pdf_page_index")
        page_number = _required_int(item, "page_number")
        codes = _string_tuple(item.get("accepted_limitation_codes"))
        generalized = _string_tuple(item.get("generalized_finding_codes"))
        findings = tuple(
            SourceAccuracyFinding(
                finding_id=f"{document_key}:p{pdf_page_index}:closure:{seq:03d}",
                document_key=document_key,
                pdf_page_index=pdf_page_index,
                page_number=page_number,
                category=_category_for_loaded_code(code),
                severity="informational",
                code=code,
                message="Sanitized finding code loaded from visual-review report.",
                requires_manual_review=False,
            )
            for seq, code in enumerate((*codes, *generalized), start=1)
        )
        pages.append(
            SourceAccuracyPageResult(
                document_key=document_key,
                filename=f"{document_key}.pdf",
                pdf_page_index=pdf_page_index,
                page_number=page_number,
                printed_page_label=str(page_number),
                evaluation_roles=(),
                automated_outcome=str(item.get("automated_outcome", REVIEW)),
                visual_review_status=str(item.get("review_status", PENDING)),
                visual_review_outcome=str(item.get("visual_review_outcome", REVIEW)),
                final_page_outcome=str(item.get("final_outcome", REVIEW)),
                metrics=(),
                findings=findings,
                parser_counts={},
                source_proxy_counts={},
                review_artifact_labels=(),
            )
        )
        if index > EXPECTED_P0_PAGE_COUNT * 2:
            raise ValueError("Visual-review report contains too many pages.")
    summary = _mapping_or_empty(data.get("summary"))
    return P0PilotAcceptanceResult(
        outcome=_required_string(data, "outcome"),
        page_results=tuple(
            sorted(pages, key=lambda page: (page.document_key, page.pdf_page_index))
        ),
        document_outcomes={
            str(key): str(value)
            for key, value in _mapping_or_empty(data.get("document_outcomes")).items()
        },
        visual_review_counts={
            str(key): int(value)
            for key, value in _mapping_or_empty(
                data.get("visual_review_counts")
            ).items()
            if isinstance(value, int)
        },
        confirmed_defect_counts={
            str(key): int(value)
            for key, value in _mapping_or_empty(
                data.get("confirmed_defect_counts")
            ).items()
            if isinstance(value, int)
        },
        accepted_limitation_codes=_string_tuple(data.get("accepted_limitation_codes")),
        blocking_finding_codes=_string_tuple(data.get("blocking_finding_codes")),
        corrective_phase_recommendations=_string_tuple(
            data.get("corrective_phase_recommendations")
        ),
        summary=dict(summary),
    )


def _filter_current_accepted_limitations(
    accepted_limitations: Sequence[AcceptedPilotLimitation],
) -> tuple[AcceptedPilotLimitation, ...]:
    retained = []
    for item in accepted_limitations:
        disposition = ACTIVE_LIMITATION_DISPOSITIONS.get(item.code)
        if disposition == "active_accepted_limitation":
            retained.append(item)
    return tuple(sorted(retained, key=lambda item: item.code))


def _confirmed_nonblocking_issues(
    accepted_limitations: Sequence[AcceptedPilotLimitation],
) -> tuple[AcceptedPilotLimitation, ...]:
    return tuple(
        sorted(
            (
                item
                for item in accepted_limitations
                if item.code == "TABLE_FALSE_POSITIVE_ON_FIGURE_PAGE"
            ),
            key=lambda item: item.code,
        )
    )


def _validate_unique_accepted_limitations(
    accepted_limitations: Sequence[AcceptedPilotLimitation],
) -> None:
    counts = Counter(item.code for item in accepted_limitations)
    duplicates = sorted(code for code, count in counts.items() if count > 1)
    if duplicates:
        raise ValueError(f"Duplicate accepted limitation codes: {duplicates}")


def _resolved_review_state_codes(
    visual_review_result: P0PilotAcceptanceResult,
) -> tuple[str, ...]:
    if (
        int(visual_review_result.summary.get("pending_pages", 0)) != 0
        or int(visual_review_result.summary.get("second_review_pages", 0)) != 0
    ):
        return ()
    found = []
    for code in STALE_REVIEW_STATE_CODES:
        if code in visual_review_result.accepted_limitation_codes or any(
            finding.code == code
            for page in visual_review_result.page_results
            for finding in page.findings
        ):
            found.append(code)
    return tuple(found)


def _historical_finding_counts(
    visual_review_result: P0PilotAcceptanceResult,
) -> tuple[Mapping[str, int], Mapping[str, int]]:
    automated = Counter[str]()
    review = Counter[str]()
    for page in visual_review_result.page_results:
        for finding in page.findings:
            if finding.code in STALE_REVIEW_STATE_CODES or finding.code.startswith(
                "VISUAL_"
            ):
                review[finding.code] += 1
            else:
                automated[finding.code] += 1
    return dict(sorted(automated.items())), dict(sorted(review.items()))


def _historical_outcomes() -> Mapping[str, Any]:
    return {
        "owner_visual_review": {
            "FAIL": 0,
            "PASS": 28,
            "REVIEW": 4,
            "outcome": ACCEPTED_WITH_LIMITATIONS,
        },
        "policy_v1": {
            "FAIL": 25,
            "PASS": 0,
            "REVIEW": 7,
            "outcome": REJECTED,
        },
        "policy_v2_automated": {
            "FAIL": 0,
            "PASS": 2,
            "REVIEW": 30,
            "outcome": REVIEW,
        },
    }


def _corrective_backlog(
    active_limitations: Sequence[AcceptedPilotLimitation],
    nonblocking_issues: Sequence[AcceptedPilotLimitation],
) -> tuple[str, ...]:
    codes = tuple(item.code for item in (*active_limitations, *nonblocking_issues))
    return tuple(
        (
            f"{code}: "
            f"{ACTIVE_LIMITATION_DISPOSITIONS.get(code, 'confirmed_nonblocking_issue')}"
        )
        for code in codes
    )


def _page_outcome_counts(pages: Sequence[Any]) -> Mapping[str, int]:
    counts = Counter(str(page.final_page_outcome) for page in pages)
    return {key: counts.get(key, 0) for key in (PASS, REVIEW, FAIL)}


def _completion_percentage(pages: Sequence[Any]) -> float:
    if not pages:
        return 0.0
    completed = sum(1 for page in pages if page.visual_review_status == COMPLETED)
    return round((completed / len(pages)) * 100.0, 2)


def _category_for_loaded_code(code: str) -> str:
    if code in STALE_REVIEW_STATE_CODES or code.startswith("VISUAL_"):
        return "HISTORICAL_REVIEW_STATE"
    return "HISTORICAL_AUTOMATED_FINDING"


def _reject_protected_payload(value: Any, *, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_protected_payload(item, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, str):
        for index, item in enumerate(value):
            _reject_protected_payload(item, path=f"{path}[{index}]")
    elif isinstance(value, str) and _looks_like_protected_text(value):
        raise ValueError(f"Protected or non-sanitized text is not allowed: {path}")


def _looks_like_protected_text(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if stripped.startswith(("/", "\\", "file:")):
        return True
    if PureWindowsPath(stripped).drive:
        return True
    lowered = stripped.lower()
    return bool(
        re.match(r"^[A-Za-z]:[\\/]", stripped)
        or "source text:" in lowered
        or "table contents:" in lowered
        or "procedure text:" in lowered
    )


def _required_string(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Closure report requires non-empty string {key}.")
    return value.strip()


def _required_int(data: Mapping[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Closure report requires integer {key}.")
    return value


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError("Expected sequence of strings.")
    return tuple(str(item) for item in value if isinstance(item, str) and item)


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("Expected object mapping.")
    return value


__all__ = [
    "ACCEPTED_LIMITATION_REGISTRY",
    "ACTIVE_LIMITATION_DISPOSITIONS",
    "AUTHORIZED_NEXT_WORK",
    "DOWNSTREAM_AUTHORIZATIONS",
    "EXPECTED_P0_PAGE_COUNT",
    "NOT_AUTHORIZED_WORK",
    "OBSOLETE_RECOMMENDATIONS",
    "P0_PILOT_CLOSURE_SCHEMA",
    "P0_PILOT_CLOSURE_SCHEMA_VERSION",
    "STALE_REVIEW_STATE_CODES",
    "AcceptedPilotLimitation",
    "P0PilotClosureResult",
    "accepted_pilot_limitation_to_dict",
    "close_p0_pilot",
    "default_accepted_pilot_limitation",
    "load_p0_pilot_acceptance_result_from_report",
    "p0_pilot_closure_result_to_dict",
    "p0_pilot_closure_result_to_json",
]
