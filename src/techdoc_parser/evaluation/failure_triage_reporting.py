"""Report and local evidence writers for P0 failure triage."""

from __future__ import annotations

import html
import json
from pathlib import Path

from techdoc_parser.evaluation.failure_triage import (
    FailureTriageCaseResult,
    FailureTriageLocalEvidence,
    FailureTriageResult,
    build_failure_triage_local_evidence,
    failure_triage_result_to_json,
    failure_triage_result_to_markdown,
    local_failure_triage_evidence_to_dict,
)
from techdoc_parser.ingestion import PDFLoader


def write_failure_triage_reports(
    result: FailureTriageResult,
    *,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    allow_report_write: bool = False,
    overwrite: bool = True,
) -> tuple[Path, ...]:
    """Write sanitized aggregate triage reports only with explicit permission."""
    if (json_path is not None or markdown_path is not None) and not allow_report_write:
        raise PermissionError(
            "Failure-triage report writing requires allow_report_write=True."
        )
    written: list[Path] = []
    if json_path is not None:
        path = Path(json_path)
        _write_text(path, failure_triage_result_to_json(result), overwrite=overwrite)
        written.append(path)
    if markdown_path is not None:
        path = Path(markdown_path)
        _write_text(
            path,
            failure_triage_result_to_markdown(result),
            overwrite=overwrite,
        )
        written.append(path)
    return tuple(written)


def write_failure_triage_evidence(
    *,
    result: FailureTriageResult,
    output_dir: str | Path,
    input_dir: str | Path,
    allow_local_write: bool = False,
    overwrite: bool = True,
) -> tuple[Path, ...]:
    """Write local full diagnostic evidence only when explicitly allowed."""
    if not allow_local_write:
        raise PermissionError(
            "Local failure-triage evidence writing requires allow_local_write=True."
        )
    input_root = Path(input_dir)
    root = Path(output_dir)
    by_source: dict[Path, list[FailureTriageCaseResult]] = {}
    for case in result.cases:
        by_source.setdefault(input_root / case.filename, []).append(case)

    written: list[Path] = []
    for source_path, cases in sorted(by_source.items(), key=lambda item: item[0].name):
        parser_document = PDFLoader(str(source_path)).load()
        for case in sorted(cases, key=lambda item: item.case_id):
            evidence = build_failure_triage_local_evidence(
                source_path=source_path,
                case_result=case,
                parser_document=parser_document,
            )
            case_dir = _safe_child(root, case.case_id)
            case_dir.mkdir(parents=True, exist_ok=True)
            written.extend(
                _write_case_evidence_files(
                    case_dir=case_dir,
                    evidence=evidence,
                    overwrite=overwrite,
                )
            )
    return tuple(written)


def _write_case_evidence_files(
    *,
    case_dir: Path,
    evidence: FailureTriageLocalEvidence,
    overwrite: bool,
) -> tuple[Path, ...]:
    payload = local_failure_triage_evidence_to_dict(evidence)
    filenames = {
        "source_proxy.json": payload["source_proxy"],
        "parser_blocks_raw.json": payload["parser_blocks_raw"],
        "parser_blocks_ordered.json": payload["parser_blocks_ordered"],
        "normalized_blocks.json": payload["normalized_blocks"],
        "entities.json": payload["structured_entities"],
        "chunks.json": payload["semantic_chunks"],
        "evaluator_input.json": payload["evaluator_input"],
        "evaluator_findings.json": payload["evaluator_findings"],
        "comparison_report.json": payload["comparison_report"],
        "root_cause_checklist.json": payload["root_cause_checklist"],
    }
    written: list[Path] = []
    for filename, data in filenames.items():
        path = case_dir / filename
        if filename == "root_cause_checklist.json" and path.exists():
            continue
        _write_text(
            path,
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            overwrite=overwrite,
        )
        written.append(path)
    html_path = case_dir / "review.html"
    _write_text(html_path, _review_html(evidence), overwrite=overwrite)
    written.append(html_path)
    return tuple(written)


def _review_html(evidence: FailureTriageLocalEvidence) -> str:
    result = evidence.case_result
    finding_rows = "\n".join(
        (
            f"<tr><td>{html.escape(finding.original_finding_code)}</td>"
            f"<td>{html.escape(finding.failure_dimension)}</td>"
            f"<td>{html.escape(finding.root_cause_classification)}</td>"
            f"<td>{html.escape(finding.diagnostic_certainty)}</td>"
            f"<td>{html.escape(finding.introduced_at_stage)}</td></tr>"
        )
        for finding in result.triage_findings
    )
    observation_rows = "\n".join(
        (
            f"<tr><td>{html.escape(observation.stage)}</td>"
            f"<td>{observation.entity_count}</td>"
            f"<td>{observation.text_line_count}</td>"
            f"<td>{html.escape(str(dict(observation.coverage_summary)))}</td></tr>"
        )
        for observation in result.stage_observations
    )
    return (
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8"><title>P0 Failure Triage</title>'
        "<style>body{font-family:Arial,sans-serif;margin:1rem;}"
        "table{border-collapse:collapse;width:100%;margin-bottom:1rem;}"
        "td,th{border:1px solid #ccc;padding:.25rem;vertical-align:top;}"
        "</style></head><body>\n"
        f"<h1>{html.escape(result.case_id)}</h1>\n"
        "<p>Local diagnostic evidence only. No parser correction was applied.</p>\n"
        "<h2>Findings</h2><table>"
        "<tr><th>Original</th><th>Dimension</th><th>Root Cause</th>"
        "<th>Certainty</th><th>Stage</th></tr>"
        f"{finding_rows}</table>\n"
        "<h2>Stage Observations</h2><table>"
        "<tr><th>Stage</th><th>Entities</th><th>Lines</th><th>Summary</th></tr>"
        f"{observation_rows}</table>\n"
        "</body></html>\n"
    )


def _write_text(path: Path, text: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_child(root: Path, *parts: str) -> Path:
    base = root.resolve()
    target = base.joinpath(*parts).resolve()
    target.relative_to(base)
    return target


__all__ = [
    "write_failure_triage_evidence",
    "write_failure_triage_reports",
]
