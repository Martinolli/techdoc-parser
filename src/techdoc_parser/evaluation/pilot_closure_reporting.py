"""Reporting helpers for final P0 pilot closure."""

from __future__ import annotations

from pathlib import Path

from techdoc_parser.evaluation.pilot_closure import (
    P0PilotClosureResult,
    p0_pilot_closure_result_to_json,
)


def p0_pilot_closure_result_to_markdown(result: P0PilotClosureResult) -> str:
    """Serialize final P0 closure as sanitized deterministic Markdown."""
    summary = dict(result.summary)
    lines = [
        "# P0 Pilot Final Acceptance",
        "",
        "## Purpose",
        "",
        "Formally close the 32-page representative P0 source-accuracy pilot with "
        "accepted limitations and explicit downstream controls.",
        "",
        "## Pilot Scope",
        "",
        "- Scope: representative P0 pages only.",
        "- Source PDFs: local, ignored, and not committed.",
        "- Parser behavior modified: false.",
        "- OCR run: false.",
        "- AviationRAG modified: false.",
        "",
        "## Historical Evaluation Sequence",
        "",
        "| Stage | PASS | REVIEW | FAIL | Outcome |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for key in ("policy_v1", "policy_v2_automated", "owner_visual_review"):
        historical = dict(result.historical_outcomes[key])
        lines.append(
            f"| `{key}` | {historical['PASS']} | {historical['REVIEW']} | "
            f"{historical['FAIL']} | `{historical['outcome']}` |"
        )
    lines.extend(
        [
            "",
            "## Final Page Outcomes",
            "",
            f"- Reviewed pages: `{summary.get('completed_pages', 0)}/"
            f"{summary.get('page_count', 0)}`",
            f"- PASS: `{result.page_outcome_counts.get('PASS', 0)}`",
            f"- REVIEW: `{result.page_outcome_counts.get('REVIEW', 0)}`",
            f"- FAIL: `{result.page_outcome_counts.get('FAIL', 0)}`",
            "",
            "## Final Document Outcomes",
            "",
            "| Document | Outcome |",
            "| --- | --- |",
        ]
    )
    for document_key, outcome in sorted(result.document_outcomes.items()):
        lines.append(f"| `{document_key}` | `{outcome}` |")
    lines.extend(
        [
            "",
            "## Corpus Acceptance Outcome",
            "",
            f"`{result.outcome}`",
            "",
            "## Confirmed Blocking Defects",
            "",
            _tuple_line(result.current_blocking_findings),
            "",
            "## Confirmed Nonblocking Issues",
            "",
        ]
    )
    if result.current_confirmed_nonblocking_issues:
        for issue in result.current_confirmed_nonblocking_issues:
            pages = ", ".join(str(page) for page in issue.affected_pages) or "none"
            docs = ", ".join(issue.affected_document_keys) or "none"
            lines.append(
                f"- `{issue.code}`: `{issue.category}`, `{issue.severity}`, "
                f"documents `{docs}`, pages `{pages}`, `{issue.corrective_status}`."
            )
    else:
        lines.append("`none`")
    lines.extend(
        [
            "",
            "## Accepted Limitations",
            "",
        ]
    )
    if result.current_accepted_limitations:
        for limitation in result.current_accepted_limitations:
            docs = (
                ", ".join(limitation.affected_document_keys)
                or "representative P0 scope"
            )
            pages = (
                ", ".join(str(page) for page in limitation.affected_pages) or "various"
            )
            lines.append(
                f"- `{limitation.code}`: `{limitation.category}`, "
                f"`{limitation.severity}`, documents `{docs}`, pages `{pages}`, "
                f"`{limitation.corrective_status}`."
            )
    else:
        lines.append("`none`")
    lines.extend(
        [
            "",
            "## Resolved Stale Review-State Findings",
            "",
            _tuple_line(result.resolved_review_state_findings),
            "",
            "## Downstream Controls",
            "",
            "| Activity | Authorized |",
            "| --- | --- |",
            "| AviationRAG persisted ChunkRecord mapping design | Yes |",
            "| Controlled local sample-persistence dry run | Yes |",
            "| Full corpus ingestion | No |",
            "| Embedding regeneration | No |",
            "| Astra rebuild | No |",
            "| FAISS rebuild | No |",
            "",
            "## Privacy and Source Protection",
            "",
            "The closure record is sanitized. It contains no source text, rendered "
            "images, equations, table contents, proprietary procedures, absolute "
            "paths, source hashes, or personal reviewer details.",
            "",
            "## Decision Statement",
            "",
            "P0 PILOT: ACCEPTED_WITH_LIMITATIONS",
            "",
            "Reviewed pages: 32/32",
            "PASS: 28",
            "REVIEW: 4",
            "FAIL: 0",
            "",
            "Blocking defects: 0",
            "Controlled downstream use: authorized",
            "Full-corpus ingestion: not authorized",
            "",
            "Full-document accuracy was not established. OCR accuracy was not "
            "established. P1/P2 pages were not reviewed. The full corpus was not "
            "processed.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_p0_pilot_closure_reports(
    result: P0PilotClosureResult,
    *,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    allow_report_write: bool = False,
    overwrite: bool = True,
) -> tuple[Path, ...]:
    """Write sanitized closure reports only with explicit permission."""
    if (json_path is not None or markdown_path is not None) and not allow_report_write:
        raise PermissionError(
            "P0 pilot closure reports require allow_report_write=True."
        )
    written: list[Path] = []
    if json_path is not None:
        path = Path(json_path)
        _write_text(path, p0_pilot_closure_result_to_json(result), overwrite=overwrite)
        written.append(path)
    if markdown_path is not None:
        path = Path(markdown_path)
        _write_text(
            path,
            p0_pilot_closure_result_to_markdown(result),
            overwrite=overwrite,
        )
        written.append(path)
    return tuple(written)


def _tuple_line(values: tuple[str, ...]) -> str:
    if not values:
        return "`none`"
    return ", ".join(f"`{value}`" for value in values)


def _write_text(path: Path, text: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


__all__ = [
    "p0_pilot_closure_result_to_markdown",
    "write_p0_pilot_closure_reports",
]
