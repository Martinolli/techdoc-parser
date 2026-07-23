#!/usr/bin/env python
"""Run P0 owner visual-review merge and acceptance reporting."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation.source_accuracy import (  # noqa: E402
    SourceAccuracyPageResult,
    SourceAccuracyPlanPage,
    load_p0_source_accuracy_plan,
)
from techdoc_parser.evaluation.visual_review import (  # noqa: E402
    ACCEPTED,
    ACCEPTED_WITH_LIMITATIONS,
    INCOMPLETE,
    REJECTED,
    assess_p0_pilot_acceptance,
    default_visual_review_decision,
    load_source_accuracy_page_results_from_report,
    merge_visual_review_decision,
    validate_visual_review_checklist,
)
from techdoc_parser.evaluation.visual_review_reporting import (  # noqa: E402
    write_p0_visual_review_package,
    write_p0_visual_review_reports,
)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.all_p0 and not args.case:
        parser.error("Select --all-p0 or at least one --case.")
    if args.generate_review_package and not args.allow_local_write:
        parser.error("--generate-review-package requires --allow-local-write.")
    plan = load_p0_source_accuracy_plan(args.plan)
    selected_plan = _selected_plan(plan, args.case, all_p0=args.all_p0)
    automated_pages = _selected_automated_pages(
        _load_automated_pages(args.automated_report),
        selected_plan,
    )
    decisions = (
        _load_decisions(
            args.evidence_dir, automated_pages, reviewer_id=args.reviewer_id
        )
        if args.merge_checklists
        else {
            _page_key(page): default_visual_review_decision(
                document_key=page.document_key,
                pdf_page_index=page.pdf_page_index,
                page_number=page.page_number,
                reviewer_id=args.reviewer_id,
            )
            for page in automated_pages
        }
    )
    merged_pages = tuple(
        merge_visual_review_decision(page, decisions[_page_key(page)])
        for page in automated_pages
    )
    result = assess_p0_pilot_acceptance(merged_pages)

    if args.generate_review_package:
        written = write_p0_visual_review_package(
            output_dir=args.evidence_dir,
            input_dir=args.input_dir,
            page_results=automated_pages,
            allow_local_write=args.allow_local_write,
        )
        print(f"Local review package files written: {len(written)}")
    if args.list_pending:
        for page in merged_pages:
            if page.visual_review_status == "pending":
                print(_page_line(page))
        return 0
    if args.list_completed:
        for page in merged_pages:
            if page.visual_review_status == "completed":
                print(_page_line(page))
        return 0
    if args.report_json or args.report_markdown:
        written_reports = write_p0_visual_review_reports(
            result,
            json_path=args.report_json,
            markdown_path=args.report_markdown,
            allow_report_write=args.allow_report_write,
        )
        for path in written_reports:
            print(f"Wrote sanitized visual-review report: {path}")

    _print_summary(result)
    return _exit_code(result.outcome, strict=args.strict)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Merge explicit owner visual-review checklists with corrected P0 "
            "policy-v2 automated evidence. No parser modifications, no OCR, "
            "no AviationRAG work, no embeddings, and no external APIs are used."
        )
    )
    parser.add_argument("--input-dir")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--automated-report", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--all-p0", action="store_true")
    parser.add_argument("--generate-review-package", action="store_true")
    parser.add_argument("--allow-local-write", action="store_true")
    parser.add_argument("--merge-checklists", action="store_true")
    parser.add_argument("--reviewer-id")
    parser.add_argument("--report-json")
    parser.add_argument("--report-markdown")
    parser.add_argument("--allow-report-write", action="store_true")
    parser.add_argument("--list-pending", action="store_true")
    parser.add_argument("--list-completed", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def _load_automated_pages(path: str | Path) -> tuple[SourceAccuracyPageResult, ...]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Automated report must be a JSON object.")
    return load_source_accuracy_page_results_from_report(data)


def _selected_plan(
    plan: tuple[SourceAccuracyPlanPage, ...],
    cases: list[str],
    *,
    all_p0: bool,
) -> tuple[SourceAccuracyPlanPage, ...]:
    if all_p0:
        return plan
    requested = set(cases)
    return tuple(
        page
        for page in plan
        if page.document_key in requested
        or f"{page.document_key}:p{page.pdf_page_index}" in requested
        or f"{page.document_key}:page_{page.page_number}" in requested
    )


def _selected_automated_pages(
    automated_pages: tuple[SourceAccuracyPageResult, ...],
    selected_plan: tuple[SourceAccuracyPlanPage, ...],
) -> tuple[SourceAccuracyPageResult, ...]:
    selected = {(page.document_key, page.pdf_page_index) for page in selected_plan}
    pages = tuple(
        page
        for page in automated_pages
        if (page.document_key, page.pdf_page_index) in selected
    )
    if len(pages) != len(selected):
        raise ValueError(
            "Automated report does not cover the selected approved P0 scope."
        )
    return tuple(
        sorted(pages, key=lambda page: (page.document_key, page.pdf_page_index))
    )


def _load_decisions(
    evidence_dir: str | Path,
    pages: tuple[SourceAccuracyPageResult, ...],
    *,
    reviewer_id: str | None,
) -> dict[tuple[str, int], object]:
    root = Path(evidence_dir)
    decisions = {}
    for page in pages:
        path = (
            root
            / page.document_key
            / f"page_{page.page_number}"
            / "review_checklist.json"
        )
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"Checklist must be a JSON object: {path}")
            decisions[_page_key(page)] = validate_visual_review_checklist(
                data,
                expected_document_key=page.document_key,
                expected_pdf_page_index=page.pdf_page_index,
            )
        else:
            decisions[_page_key(page)] = default_visual_review_decision(
                document_key=page.document_key,
                pdf_page_index=page.pdf_page_index,
                page_number=page.page_number,
                reviewer_id=reviewer_id,
            )
    return decisions


def _print_summary(result: object) -> None:
    assert hasattr(result, "summary")
    summary = result.summary
    print("Scope: representative P0 pages only.")
    print("Review model: owner visual review; no checklist is auto-approved.")
    print("Parser behavior modified: false")
    print("OCR run: false")
    print("Source PDFs local and ignored: true")
    print("AviationRAG modified: false")
    print("Embeddings/external APIs used: false")
    print(f"Pages total: {summary.get('page_count', 0)}")
    print(f"Completed: {summary.get('completed_pages', 0)}")
    print(f"Pending: {summary.get('pending_pages', 0)}")
    print(f"Second review: {summary.get('second_review_pages', 0)}")
    print(f"Blocked: {summary.get('blocked_pages', 0)}")
    print(f"Completion percentage: {summary.get('completion_percentage', 0.0)}")
    print(f"Final page outcomes: {dict(summary.get('page_outcome_counts', {}))}")
    print(f"Document outcomes: {dict(result.document_outcomes)}")
    print(f"Confirmed defects: {dict(result.confirmed_defect_counts)}")
    print(f"Accepted limitations: {list(result.accepted_limitation_codes)}")
    print(f"Blocking findings: {list(result.blocking_finding_codes)}")
    print(
        f"Corrective recommendations: {list(result.corrective_phase_recommendations)}"
    )
    print(f"Pilot acceptance outcome: {result.outcome}")


def _page_line(page: SourceAccuracyPageResult) -> str:
    return (
        f"{page.document_key}\t{page.page_number}\t"
        f"{page.visual_review_status}\t{page.final_page_outcome}"
    )


def _page_key(page: SourceAccuracyPageResult) -> tuple[str, int]:
    return (page.document_key, page.pdf_page_index)


def _exit_code(outcome: str, *, strict: bool) -> int:
    if outcome == ACCEPTED:
        return 0
    if outcome in {ACCEPTED_WITH_LIMITATIONS, INCOMPLETE}:
        return 1 if strict else 2
    if outcome == REJECTED:
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
