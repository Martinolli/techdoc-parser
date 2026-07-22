#!/usr/bin/env python
"""Run fixture-only chunk quality evaluation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation import (  # noqa: E402
    PASS,
    PROXY_NOTICE,
    REVIEW,
    ChunkQualityEvaluationCase,
    ChunkQualityEvaluationPolicy,
    chunk_quality_evaluation_results_to_dict,
    evaluate_chunk_quality_case,
    load_chunk_quality_cases,
    write_chunk_quality_reports,
)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    registry_path = Path(args.registry)
    cases = load_chunk_quality_cases(registry_path)
    if args.list_cases:
        for case in cases:
            print(f"{case.case_id}\t{case.fixture_path}\t{case.description}")
        return 0
    selected_cases = _select_cases(cases, args.case, args.all_cases)
    policy = ChunkQualityEvaluationPolicy()
    results = [
        evaluate_chunk_quality_case(
            case,
            registry_root=ROOT,
            policy=policy,
        )
        for case in selected_cases
    ]
    aggregate = chunk_quality_evaluation_results_to_dict(results)
    print(PROXY_NOTICE)
    print(
        "Scope: fixture-only; no source-page visual accuracy, OCR accuracy, "
        "embeddings, AviationRAG runtime, Astra, FAISS, external APIs, or LLM "
        "semantic similarity."
    )
    print(f"Outcome: {aggregate['outcome']}")
    print(f"Case count: {aggregate['case_count']}")
    print(f"PASS: {aggregate['pass_count']}")
    print(f"REVIEW: {aggregate['review_count']}")
    print(f"FAIL: {aggregate['fail_count']}")
    for result in sorted(results, key=lambda item: item.fixture_name):
        print(
            f"Case {result.fixture_name}: {result.outcome} "
            f"({result.chunk_count} chunks, {len(result.issues)} issues)"
        )
    if args.report_json or args.report_markdown:
        written = write_chunk_quality_reports(
            results,
            json_path=args.report_json,
            markdown_path=args.report_markdown,
            allow_report_write=args.allow_report_write,
        )
        for path in written:
            print(f"Wrote report: {path}")
    else:
        print("Reports not written.")
    outcome = str(aggregate["outcome"])
    if outcome == PASS:
        return 0
    if outcome == REVIEW:
        return 1 if args.strict else 2
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run deterministic fixture-only chunk quality evaluation. "
            "This does not evaluate source-page visual accuracy, OCR accuracy, "
            "real aviation-document accuracy, embeddings, AviationRAG runtime, "
            "Astra, FAISS, external APIs, or LLM semantic similarity."
        )
    )
    parser.add_argument(
        "--case", action="append", default=[], help="Case ID to evaluate; repeatable."
    )
    parser.add_argument(
        "--all-cases",
        action="store_true",
        help="Evaluate every registered fixture case.",
    )
    parser.add_argument(
        "--registry",
        default=str(
            ROOT / "tests" / "fixtures" / "chunk_quality" / "evaluation_cases.json"
        ),
        help="Path to the chunk quality fixture registry.",
    )
    parser.add_argument("--report-json", help="Optional JSON report path.")
    parser.add_argument("--report-markdown", help="Optional Markdown report path.")
    parser.add_argument(
        "--allow-report-write",
        action="store_true",
        help="Permit writing JSON/Markdown reports.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 1 for REVIEW instead of 2.",
    )
    parser.add_argument(
        "--list-cases", action="store_true", help="List registered cases and exit."
    )
    return parser


def _select_cases(
    cases: tuple[ChunkQualityEvaluationCase, ...],
    requested_case_ids: list[str],
    all_cases: bool,
) -> tuple[ChunkQualityEvaluationCase, ...]:
    if all_cases:
        return cases
    if not requested_case_ids:
        raise SystemExit("Select at least one --case or use --all-cases.")
    cases_by_id = {case.case_id: case for case in cases}
    selected: list[ChunkQualityEvaluationCase] = []
    for case_id in requested_case_ids:
        try:
            selected.append(cases_by_id[case_id])
        except KeyError as exc:
            known = ", ".join(sorted(cases_by_id))
            raise SystemExit(f"Unknown case {case_id!r}. Known cases: {known}") from exc
    return tuple(selected)


if __name__ == "__main__":
    raise SystemExit(main())
