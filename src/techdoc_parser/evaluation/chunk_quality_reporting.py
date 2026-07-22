"""Reporting helpers for fixture-only chunk-quality evaluations."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from techdoc_parser.evaluation.chunk_quality import (
    FAIL,
    PASS,
    PROXY_NOTICE,
    REVIEW,
    ChunkQualityEvaluationResult,
    ChunkQualityIssue,
    ChunkQualityMetricResult,
)


def chunk_quality_evaluation_result_to_dict(
    result: ChunkQualityEvaluationResult,
) -> dict[str, Any]:
    """Convert one chunk-quality result to a deterministic JSON shape."""
    return {
        "evaluation_scope": result.evaluation_scope,
        "proxy_notice": result.proxy_notice,
        "source_accuracy_evaluated": result.source_accuracy_evaluated,
        "ocr_accuracy_evaluated": result.ocr_accuracy_evaluated,
        "visual_layout_accuracy_evaluated": result.visual_layout_accuracy_evaluated,
        "outcome": result.outcome,
        "manual_review_required": result.manual_review_required,
        "fixture_name": result.fixture_name,
        "document_id": result.document_id,
        "chunk_count": result.chunk_count,
        "source_block_count": result.source_block_count,
        "determinism_checked": result.determinism_checked,
        "determinism_passed": result.determinism_passed,
        "content_type_counts": dict(result.content_type_counts),
        "provenance_status_counts": dict(result.provenance_status_counts),
        "chunk_size_summary": dict(result.chunk_size_summary),
        "coverage_summary": _jsonable_mapping(result.coverage_summary),
        "special_content_summary": _jsonable_mapping(result.special_content_summary),
        "metric_count": len(result.metrics),
        "metrics": [_metric_to_dict(metric) for metric in result.metrics],
        "issue_count": len(result.issues),
        "error_count": sum(1 for issue in result.issues if issue.severity == "error"),
        "warning_count": sum(
            1 for issue in result.issues if issue.severity == "warning"
        ),
        "issues": [_issue_to_dict(issue) for issue in result.issues],
    }


def chunk_quality_evaluation_result_to_json(
    result: ChunkQualityEvaluationResult,
) -> str:
    """Serialize one chunk-quality result as deterministic JSON."""
    return (
        json.dumps(
            chunk_quality_evaluation_result_to_dict(result),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def chunk_quality_evaluation_result_to_markdown(
    result: ChunkQualityEvaluationResult,
) -> str:
    """Serialize one chunk-quality result as human-readable Markdown."""
    data = chunk_quality_evaluation_result_to_dict(result)
    lines = [
        f"# Chunk Quality Evaluation: {result.fixture_name}",
        "",
        PROXY_NOTICE,
        "",
        f"- Outcome: `{result.outcome}`",
        f"- Document ID: `{result.document_id}`",
        f"- Chunk count: `{result.chunk_count}`",
        f"- Source block count: `{result.source_block_count}`",
        f"- Determinism checked: `{result.determinism_checked}`",
        f"- Determinism passed: `{result.determinism_passed}`",
        "",
        "## Metrics",
        "",
        "| Metric | Status | Value |",
        "| --- | --- | --- |",
    ]
    for metric in data["metrics"]:
        lines.append(
            f"| `{metric['name']}` | `{metric['status']}` | `{metric['value']}` |"
        )
    lines.extend(["", "## Issues", ""])
    if result.issues:
        for issue in data["issues"]:
            lines.append(
                f"- `{issue['severity']}` `{issue['code']}`: {issue['message']}"
            )
    else:
        lines.append("No issues were emitted.")
    lines.extend(["", "## Scope Boundary", ""])
    lines.append("- Source-page visual accuracy evaluated: `False`")
    lines.append("- OCR accuracy evaluated: `False`")
    lines.append("- Real aviation-document accuracy evaluated: `False`")
    return "\n".join(lines) + "\n"


def chunk_quality_evaluation_results_to_dict(
    results: Sequence[ChunkQualityEvaluationResult],
) -> dict[str, Any]:
    """Convert multiple case results to a deterministic aggregate report."""
    outcome = _aggregate_outcome(results)
    return {
        "evaluation_scope": "fixture_chunk_quality_proxy",
        "proxy_notice": PROXY_NOTICE,
        "outcome": outcome,
        "case_count": len(results),
        "pass_count": sum(1 for result in results if result.outcome == PASS),
        "review_count": sum(1 for result in results if result.outcome == REVIEW),
        "fail_count": sum(1 for result in results if result.outcome == FAIL),
        "source_accuracy_evaluated": False,
        "ocr_accuracy_evaluated": False,
        "visual_layout_accuracy_evaluated": False,
        "case_results": [
            chunk_quality_evaluation_result_to_dict(result)
            for result in sorted(results, key=lambda item: item.fixture_name)
        ],
    }


def chunk_quality_evaluation_results_to_json(
    results: Sequence[ChunkQualityEvaluationResult],
) -> str:
    """Serialize multiple case results as deterministic JSON."""
    return (
        json.dumps(
            chunk_quality_evaluation_results_to_dict(results),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def chunk_quality_evaluation_results_to_markdown(
    results: Sequence[ChunkQualityEvaluationResult],
) -> str:
    """Serialize multiple case results as human-readable Markdown."""
    data = chunk_quality_evaluation_results_to_dict(results)
    lines = [
        "# Fixture Chunk Quality Evaluation",
        "",
        PROXY_NOTICE,
        "",
        f"- Outcome: `{data['outcome']}`",
        f"- Case count: `{data['case_count']}`",
        f"- PASS: `{data['pass_count']}`",
        f"- REVIEW: `{data['review_count']}`",
        f"- FAIL: `{data['fail_count']}`",
        "",
        "## Cases",
        "",
        "| Case | Outcome | Chunks | Issues |",
        "| --- | --- | ---: | ---: |",
    ]
    for result in sorted(results, key=lambda item: item.fixture_name):
        lines.append(
            f"| `{result.fixture_name}` | `{result.outcome}` | "
            f"{result.chunk_count} | {len(result.issues)} |"
        )
    lines.extend(["", "## Scope Boundary", ""])
    lines.append("- Source-page visual accuracy evaluated: `False`")
    lines.append("- OCR accuracy evaluated: `False`")
    lines.append("- Real aviation-document accuracy evaluated: `False`")
    return "\n".join(lines) + "\n"


def write_chunk_quality_reports(
    results: ChunkQualityEvaluationResult | Sequence[ChunkQualityEvaluationResult],
    *,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    allow_report_write: bool = False,
) -> tuple[Path, ...]:
    """Write reports only when explicitly allowed by the caller."""
    if (json_path is not None or markdown_path is not None) and not allow_report_write:
        raise PermissionError(
            "Chunk quality report writing requires allow_report_write=True."
        )
    result_sequence = _result_sequence(results)
    written: list[Path] = []
    if json_path is not None:
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            chunk_quality_evaluation_results_to_json(result_sequence), encoding="utf-8"
        )
        written.append(path)
    if markdown_path is not None:
        path = Path(markdown_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            chunk_quality_evaluation_results_to_markdown(result_sequence),
            encoding="utf-8",
        )
        written.append(path)
    return tuple(written)


def _result_sequence(
    results: ChunkQualityEvaluationResult | Sequence[ChunkQualityEvaluationResult],
) -> tuple[ChunkQualityEvaluationResult, ...]:
    if isinstance(results, ChunkQualityEvaluationResult):
        return (results,)
    return tuple(results)


def _aggregate_outcome(results: Sequence[ChunkQualityEvaluationResult]) -> str:
    if any(result.outcome == FAIL for result in results):
        return FAIL
    if any(result.outcome == REVIEW for result in results):
        return REVIEW
    return PASS


def _metric_to_dict(metric: ChunkQualityMetricResult) -> dict[str, Any]:
    data = asdict(metric)
    data["details"] = _jsonable_mapping(metric.details)
    return data


def _issue_to_dict(issue: ChunkQualityIssue) -> dict[str, Any]:
    data = asdict(issue)
    data["details"] = _jsonable_mapping(issue.details)
    return data


def _jsonable_mapping(mapping: Mapping[str, object]) -> dict[str, object]:
    return {key: _jsonable(value) for key, value in mapping.items()}


def _jsonable(value: object) -> object:
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value
