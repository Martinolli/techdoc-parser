#!/usr/bin/env python
"""Run the controlled approved-P0 source-accuracy pilot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation.source_accuracy import (  # noqa: E402
    FAIL,
    PASS,
    REVIEW,
    SourceAccuracyPilotResult,
    SourceAccuracyPlanPage,
    load_p0_source_accuracy_plan,
    run_source_accuracy_pilot,
)
from techdoc_parser.evaluation.source_accuracy_reporting import (  # noqa: E402
    write_local_pilot_evidence_package,
    write_source_accuracy_reports,
)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    plan = load_p0_source_accuracy_plan(args.plan)
    if args.list_pages:
        for page in _selected_plan(plan, args.case, all_p0=args.all_p0):
            print(
                f"{page.document_key}\t{page.filename}\t"
                f"{page.page_number}\t{','.join(page.evaluation_roles)}"
            )
        return 0
    if not args.all_p0 and not args.case:
        parser.error("Select --all-p0 or at least one --case.")
    if args.merge_review_checklists and not args.review_checklist:
        parser.error("--merge-review-checklists requires --review-checklist.")

    result = run_source_accuracy_pilot(
        input_dir=args.input_dir,
        plan=plan,
        document_keys=set(args.case) if args.case else None,
        context_radius=args.context_radius,
        checklist_paths=args.review_checklist if args.merge_review_checklists else (),
    )
    print("Scope: representative P0 pages only.")
    print("Full-document accuracy evaluated: false")
    print("OCR run: false")
    print("Parser behavior modified: false")
    print("AviationRAG modified: false")
    print("Embeddings/external APIs used: false")
    print(f"Pages evaluated: {result.page_count}")
    print(f"Outcome: {result.outcome}")
    print(f"Final outcomes: {dict(result.page_outcome_counts)}")
    print(f"Visual review: {dict(result.visual_review_completion_counts)}")
    print(f"Finding categories: {dict(result.category_counts)}")
    print(f"Finding severities: {dict(result.severity_counts)}")
    print(_metric_line(result, "raw_character_coverage", "Text coverage"))
    print(_metric_line(result, "order_inversion_count", "Order violations"))
    print(
        _metric_line(
            result,
            "page_provenance_consistency",
            "Provenance consistency",
        )
    )
    print(_metric_line(result, "section_parent_integrity", "Section issues"))
    print(_metric_line(result, "table_evidence_count", "Table evidence"))
    print(_metric_line(result, "figure_caption_evidence_count", "Figure evidence"))
    print(_metric_line(result, "equation_evidence_count", "Equation evidence"))
    print(_metric_line(result, "admonition_evidence_count", "Admonition evidence"))
    print(
        _metric_line(
            result,
            "cross_reference_evidence_count",
            "Cross-reference evidence",
        )
    )
    print(_metric_line(result, "chunk_source_block_coverage", "Chunk coverage"))
    print(_metric_line(result, "sr22_native_text_classification", "SR22 text"))

    if args.output_dir:
        written = write_local_pilot_evidence_package(
            output_dir=args.output_dir,
            input_dir=args.input_dir,
            result=result,
            allow_local_write=args.allow_local_write,
        )
        print(f"Local evidence files written: {len(written)}")
    if args.report_json or args.report_markdown:
        written_reports = write_source_accuracy_reports(
            result,
            json_path=args.report_json,
            markdown_path=args.report_markdown,
            allow_report_write=args.allow_report_write,
        )
        for path in written_reports:
            print(f"Wrote sanitized report: {path}")
    return _exit_code(result.outcome, strict=args.strict)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run controlled source-accuracy proxy checks for approved P0 pages. "
            "No OCR, parser repair, AviationRAG work, embeddings, or external "
            "APIs are used."
        )
    )
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--all-p0", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--allow-local-write", action="store_true")
    parser.add_argument("--report-json")
    parser.add_argument("--report-markdown")
    parser.add_argument("--allow-report-write", action="store_true")
    parser.add_argument("--context-radius", type=int, default=1)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--list-pages", action="store_true")
    parser.add_argument("--merge-review-checklists", action="store_true")
    parser.add_argument("--review-checklist", action="append", default=[])
    return parser


def _selected_plan(
    plan: tuple[SourceAccuracyPlanPage, ...],
    cases: list[str],
    *,
    all_p0: bool,
) -> tuple[SourceAccuracyPlanPage, ...]:
    if all_p0 or not cases:
        return plan
    selected = set(cases)
    return tuple(page for page in plan if page.document_key in selected)


def _metric_line(
    result: SourceAccuracyPilotResult,
    metric_name: str,
    label: str,
) -> str:
    summary = result.metric_summaries.get(metric_name, {})
    return f"{label}: {dict(summary)}"


def _exit_code(outcome: str, *, strict: bool) -> int:
    if outcome == PASS:
        return 0
    if outcome == REVIEW:
        return 1 if strict else 2
    if outcome == FAIL:
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
