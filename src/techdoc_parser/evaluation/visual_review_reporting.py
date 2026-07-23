"""Reporting and local package writers for P0 owner visual review."""

from __future__ import annotations

import html
import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from techdoc_parser.evaluation.source_accuracy import (
    SourceAccuracyPageResult,
    source_accuracy_page_result_to_dict,
)
from techdoc_parser.evaluation.visual_review import (
    REQUIRED_VISUAL_CHECK_FIELDS,
    P0PilotAcceptanceResult,
    default_visual_review_decision,
    p0_pilot_acceptance_result_to_dict,
    p0_pilot_acceptance_result_to_json,
    visual_review_decision_to_dict,
)


def p0_pilot_acceptance_result_to_markdown(
    result: P0PilotAcceptanceResult,
) -> str:
    """Serialize the visual-review acceptance result as sanitized Markdown."""
    data = p0_pilot_acceptance_result_to_dict(result)
    summary = data["summary"]
    assert isinstance(summary, dict)
    lines = [
        "# P0 Visual Review and Acceptance",
        "",
        "source_accuracy_scope: representative_p0_pages",
        "visual_review_scope: owner_visual_review_p0_pages",
        "full_document_accuracy_evaluated: false",
        "ocr_run: false",
        "parser_behavior_modified: false",
        "",
        "## Summary",
        "",
        f"- Corpus acceptance outcome: `{result.outcome}`",
        f"- P0 pages: `{summary.get('page_count', 0)}`",
        f"- Completed pages: `{summary.get('completed_pages', 0)}`",
        f"- Pending pages: `{summary.get('pending_pages', 0)}`",
        f"- Second-review pages: `{summary.get('second_review_pages', 0)}`",
        f"- Blocked pages: `{summary.get('blocked_pages', 0)}`",
        f"- Completion percentage: `{summary.get('completion_percentage', 0.0)}`",
        "",
        "## Page Outcomes",
        "",
        "| Document | Page | Automated | Visual status | Final |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for page in result.page_results:
        lines.append(
            f"| `{page.document_key}` | {page.page_number} | "
            f"`{page.automated_outcome}` | `{page.visual_review_status}` | "
            f"`{page.final_page_outcome}` |"
        )
    lines.extend(
        [
            "",
            "## Document Outcomes",
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
            "## Confirmed Defects",
            "",
            _code_line(result.confirmed_defect_counts),
            "",
            "## Accepted Limitations",
            "",
            _tuple_line(result.accepted_limitation_codes),
            "",
            "## Blocking Findings",
            "",
            _tuple_line(result.blocking_finding_codes),
            "",
            "## Corrective Phase Recommendations",
            "",
        ]
    )
    lines.extend(f"- `{item}`" for item in result.corrective_phase_recommendations)
    lines.extend(
        [
            "",
            "## Privacy",
            "",
            "This report is sanitized. It contains no extracted source text, rendered "
            "images, equations, procedure wording, table contents, absolute paths, "
            "or personal contact details.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_p0_visual_review_reports(
    result: P0PilotAcceptanceResult,
    *,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    allow_report_write: bool = False,
    overwrite: bool = True,
) -> tuple[Path, ...]:
    """Write sanitized visual-review reports only with explicit permission."""
    if (json_path is not None or markdown_path is not None) and not allow_report_write:
        raise PermissionError(
            "P0 visual-review reports require allow_report_write=True."
        )
    written: list[Path] = []
    if json_path is not None:
        path = Path(json_path)
        _write_text(
            path,
            p0_pilot_acceptance_result_to_json(result),
            overwrite=overwrite,
        )
        written.append(path)
    if markdown_path is not None:
        path = Path(markdown_path)
        _write_text(
            path,
            p0_pilot_acceptance_result_to_markdown(result),
            overwrite=overwrite,
        )
        written.append(path)
    return tuple(written)


def write_p0_visual_review_package(
    *,
    output_dir: str | Path,
    input_dir: str | Path | None,
    page_results: tuple[SourceAccuracyPageResult, ...],
    allow_local_write: bool = False,
) -> tuple[Path, ...]:
    """Write local review pages and checklist templates with explicit permission."""
    if not allow_local_write:
        raise PermissionError(
            "P0 visual-review package requires allow_local_write=True."
        )
    root = Path(output_dir)
    input_root = Path(input_dir) if input_dir is not None else None
    written: list[Path] = []
    for page in page_results:
        page_dir = _safe_child(root, page.document_key, f"page_{page.page_number}")
        page_dir.mkdir(parents=True, exist_ok=True)
        summary_path = page_dir / "automated_summary.json"
        _write_text(
            summary_path,
            json.dumps(
                _automated_summary(page),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            overwrite=True,
        )
        written.append(summary_path)
        checklist_path = page_dir / "review_checklist.json"
        if not checklist_path.exists():
            decision = default_visual_review_decision(
                document_key=page.document_key,
                pdf_page_index=page.pdf_page_index,
                page_number=page.page_number,
            )
            _write_text(
                checklist_path,
                json.dumps(
                    visual_review_decision_to_dict(decision),
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                overwrite=False,
            )
            written.append(checklist_path)
        html_path = page_dir / "review.html"
        _write_text(html_path, _review_html(page), overwrite=True)
        written.append(html_path)
        if input_root is not None:
            png_path = page_dir / "page.png"
            _render_page_png(
                source_path=input_root / page.filename,
                pdf_page_index=page.pdf_page_index,
                output_path=png_path,
            )
            written.append(png_path)
    return tuple(written)


def _automated_summary(page: SourceAccuracyPageResult) -> dict[str, object]:
    data = source_accuracy_page_result_to_dict(page)
    return {
        "document_key": data["document_key"],
        "filename": data["filename"],
        "pdf_page_index": data["pdf_page_index"],
        "page_number": data["page_number"],
        "printed_page_label": data["printed_page_label"],
        "evaluation_roles": data["evaluation_roles"],
        "automated_outcome": data["automated_outcome"],
        "policy_name": data["evaluation_policy_name"],
        "policy_version": data["evaluation_policy_version"],
        "parser_counts": data["parser_counts"],
        "source_proxy_counts": data["source_proxy_counts"],
        "metrics": data["metrics"],
        "findings": data["findings"],
        "privacy": {
            "sanitized": True,
            "contains_source_text": False,
            "contains_rendered_image": False,
        },
    }


def _review_html(page: SourceAccuracyPageResult) -> str:
    escaped_outcome = html.escape(page.automated_outcome)
    count_summary = html.escape(
        json.dumps(
            {
                "parser_counts": dict(page.parser_counts),
                "source_proxy_counts": dict(page.source_proxy_counts),
            },
            indent=2,
            sort_keys=True,
        )
    )
    rows = "\n".join(
        f"<tr><td>{html.escape(field)}</td><td>pending</td></tr>"
        for field in REQUIRED_VISUAL_CHECK_FIELDS
    )
    metric_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(metric.name)}</td>"
        f"<td>{html.escape(metric.status)}</td>"
        f"<td>{html.escape(str(metric.value))}</td>"
        "</tr>"
        for metric in page.metrics
    )
    finding_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(finding.code)}</td>"
        f"<td>{html.escape(finding.category)}</td>"
        f"<td>{html.escape(finding.severity)}</td>"
        f"<td>{html.escape(finding.message)}</td>"
        "</tr>"
        for finding in page.findings
    )
    roles = ", ".join(page.evaluation_roles) or "none"
    return (
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8"><title>P0 Visual Review</title>'
        "<style>"
        "body{font-family:Arial,sans-serif;margin:16px;color:#202124;}"
        ".layout{display:grid;grid-template-columns:minmax(320px,48vw) 1fr;gap:16px;}"
        "img{max-width:100%;border:1px solid #bbb;background:#fff;}"
        "table{border-collapse:collapse;width:100%;margin-bottom:16px;}"
        "th,td{border:1px solid #ccc;padding:4px 6px;vertical-align:top;}"
        "code{background:#f4f4f4;padding:1px 3px;}"
        ".note{border-left:4px solid #777;padding-left:8px;color:#333;}"
        "</style></head><body>\n"
        f"<h1>{html.escape(page.document_key)} page {page.page_number}</h1>\n"
        '<p class="note">Local owner review only. No checklist item is '
        "auto-approved. Edit <code>review_checklist.json</code> after visual "
        "inspection; keep notes sanitized.</p>\n"
        '<div class="layout"><div><img src="page.png" alt="rendered source page"></div>'
        "<div>"
        f"<p><strong>Automated outcome:</strong> {escaped_outcome}</p>"
        f"<p><strong>Evaluation roles:</strong> {html.escape(roles)}</p>"
        "<h2>Parser and Source Counts</h2><pre>"
        f"{count_summary}"
        "</pre>"
        "<h2>Metrics</h2><table><tr><th>Name</th><th>Status</th><th>Value</th></tr>"
        f"{metric_rows}</table>"
        "<h2>Automated Review Findings</h2><table>"
        "<tr><th>Code</th><th>Category</th><th>Severity</th><th>Message</th></tr>"
        f"{finding_rows}</table>"
        "</div></div>"
        "<h2>Required Checklist</h2><table><tr><th>Check</th><th>Status</th></tr>"
        f"{rows}</table>\n"
        "</body></html>\n"
    )


def _render_page_png(
    *,
    source_path: Path,
    pdf_page_index: int,
    output_path: Path,
) -> None:
    if not source_path.exists():
        return
    with fitz.open(source_path) as document:
        page = document.load_page(pdf_page_index)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        pixmap.save(output_path)


def _code_line(mapping: object) -> str:
    if not mapping:
        return "`none`"
    assert isinstance(mapping, dict)
    return ", ".join(f"`{key}`: `{value}`" for key, value in sorted(mapping.items()))


def _tuple_line(values: tuple[str, ...]) -> str:
    if not values:
        return "`none`"
    return ", ".join(f"`{value}`" for value in values)


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
    "p0_pilot_acceptance_result_to_markdown",
    "write_p0_visual_review_package",
    "write_p0_visual_review_reports",
]
