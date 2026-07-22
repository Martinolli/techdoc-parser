#!/usr/bin/env python
"""Run diagnosis-only P0 source-accuracy failure triage."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation.failure_triage import (  # noqa: E402
    BLOCKED,
    COMPLETE,
    REVIEW,
    FailureTriageResult,
    load_default_p0_failure_triage_plan,
    run_p0_failure_triage,
)
from techdoc_parser.evaluation.failure_triage_reporting import (  # noqa: E402
    write_failure_triage_evidence,
    write_failure_triage_reports,
)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    plan = load_default_p0_failure_triage_plan(args.plan)
    selected_cases = _selected_cases(plan, args.case, all_cases=args.all_cases)
    if args.list_cases:
        for case in selected_cases:
            print(
                f"{case.case_id}\t{case.document_key}\t"
                f"{case.page_number}\t{','.join(case.original_finding_codes)}"
            )
        return 0
    if not args.all_cases and not args.case:
        parser.error("Select --all-cases or at least one --case.")
    checklist_paths = ()
    if args.merge_review_checklists:
        if not args.output_dir:
            parser.error("--merge-review-checklists requires --output-dir.")
        checklist_paths = _review_checklist_paths(args.output_dir, selected_cases)
        print(f"Merged review checklists: {len(checklist_paths)}")

    result = run_p0_failure_triage(
        input_dir=args.input_dir,
        plan=plan,
        case_ids=set(args.case) if args.case else None,
        context_radius=args.context_radius,
        checklist_paths=checklist_paths,
    )
    _print_summary(result)
    if args.output_dir:
        written = write_failure_triage_evidence(
            result=result,
            output_dir=args.output_dir,
            input_dir=args.input_dir,
            allow_local_write=args.allow_local_write,
        )
        print(f"Local diagnostic evidence files written: {len(written)}")
    if args.report_json or args.report_markdown:
        written_reports = write_failure_triage_reports(
            result,
            json_path=args.report_json,
            markdown_path=args.report_markdown,
            allow_report_write=args.allow_report_write,
        )
        for path in written_reports:
            print(f"Wrote sanitized triage report: {path}")
    return _exit_code(result.outcome, strict=args.strict)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run diagnosis-only root-cause triage for selected approved P0 "
            "source-accuracy findings. No parser correction, OCR, "
            "AviationRAG work, embeddings, or external APIs are used."
        )
    )
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--all-cases", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--allow-local-write", action="store_true")
    parser.add_argument("--report-json")
    parser.add_argument("--report-markdown")
    parser.add_argument("--allow-report-write", action="store_true")
    parser.add_argument("--context-radius", type=int, default=1)
    parser.add_argument("--merge-review-checklists", action="store_true")
    parser.add_argument("--list-cases", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def _selected_cases(plan, cases: list[str], *, all_cases: bool):
    if all_cases or not cases:
        return plan
    selected = set(cases)
    return tuple(case for case in plan if case.case_id in selected)


def _review_checklist_paths(output_dir: str, cases) -> tuple[Path, ...]:
    root = Path(output_dir)
    return tuple(
        path
        for path in (
            root / case.case_id / "root_cause_checklist.json" for case in cases
        )
        if path.is_file()
    )


def _print_summary(result: FailureTriageResult) -> None:
    print("Scope: selected approved P0 findings only.")
    print("Diagnosis only: true")
    print("Parser correction applied: false")
    print("Evaluator policy changed: false")
    print("Original P0 outcomes changed: false")
    print("Full-document accuracy evaluated: false")
    print("OCR run: false")
    print("AviationRAG modified: false")
    print("Embeddings/external APIs used: false")
    print(f"Cases processed: {result.case_count}")
    print(f"Outcome: {result.outcome}")
    print(f"Original finding count: {sum(result.finding_counts.values())}")
    print(f"Classified finding count: {sum(result.root_cause_counts.values())}")
    print(
        "Confirmed parser defects: "
        f"{result.root_cause_counts.get('CONFIRMED_PARSER_DEFECT', 0)}"
    )
    print(
        "Evaluator defects: "
        f"{result.root_cause_counts.get('EVALUATION_FRAMEWORK_DEFECT', 0)}"
    )
    print(
        "Source-proxy limitations: "
        f"{result.root_cause_counts.get('SOURCE_PROXY_LIMITATION', 0)}"
    )
    print(
        "Expected multi-representation: "
        f"{result.root_cause_counts.get('EXPECTED_MULTI_REPRESENTATION', 0)}"
    )
    print(
        "Layout limitations: "
        f"{result.root_cause_counts.get('DOCUMENT_LAYOUT_LIMITATION', 0)}"
    )
    print(
        "Needs visual confirmation: "
        f"{result.root_cause_counts.get('NEEDS_VISUAL_CONFIRMATION', 0)}"
    )
    print(f"Findings by pipeline stage: {dict(result.pipeline_stage_counts)}")
    print(
        "Recommended corrective phases: " f"{dict(result.corrective_recommendations)}"
    )


def _exit_code(outcome: str, *, strict: bool) -> int:
    if outcome == COMPLETE:
        return 0
    if outcome == REVIEW:
        return 1 if strict else 2
    if outcome == BLOCKED:
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
