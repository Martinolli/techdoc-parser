#!/usr/bin/env python
"""Close the completed P0 visual-review pilot with accepted limitations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation.pilot_closure import (  # noqa: E402
    close_p0_pilot,
    default_accepted_pilot_limitation,
    load_p0_pilot_acceptance_result_from_report,
)
from techdoc_parser.evaluation.pilot_closure_reporting import (  # noqa: E402
    write_p0_pilot_closure_reports,
)
from techdoc_parser.evaluation.visual_review import (  # noqa: E402
    ACCEPTED,
    ACCEPTED_WITH_LIMITATIONS,
)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    if (args.report_json or args.report_markdown) and not args.allow_report_write:
        raise PermissionError(
            "--report-json/--report-markdown require --allow-report-write."
        )
    data = json.loads(Path(args.visual_review_report).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Visual-review report must be a JSON object.")
    visual_result = load_p0_pilot_acceptance_result_from_report(data)
    limitations = tuple(
        default_accepted_pilot_limitation(
            code,
            affected_document_keys=_affected_documents(code),
            affected_pages=_affected_pages(code),
        )
        for code in args.accepted_limitation
    )
    result = close_p0_pilot(
        visual_review_result=visual_result,
        accepted_limitations=limitations,
    )
    written = write_p0_pilot_closure_reports(
        result,
        json_path=args.report_json,
        markdown_path=args.report_markdown,
        allow_report_write=args.allow_report_write,
    )
    for path in written:
        print(f"Wrote sanitized P0 pilot closure report: {path}")
    _print_summary(result)
    return _exit_code(result.outcome, strict=args.strict)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Close a completed P0 pilot visual-review result. Closure only; no "
            "parser changes, no OCR, no AviationRAG modifications, and no "
            "full-corpus ingestion authorization."
        )
    )
    parser.add_argument("--visual-review-report", required=True)
    parser.add_argument("--accepted-limitation", action="append", default=[])
    parser.add_argument("--report-json")
    parser.add_argument("--report-markdown")
    parser.add_argument("--allow-report-write", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def _affected_documents(code: str) -> tuple[str, ...]:
    if code == "TABLE_FALSE_POSITIVE_ON_FIGURE_PAGE":
        return ("aircraft_system_safety",)
    return ()


def _affected_pages(code: str) -> tuple[int, ...]:
    if code == "TABLE_FALSE_POSITIVE_ON_FIGURE_PAGE":
        return (52,)
    return ()


def _print_summary(result: object) -> None:
    assert hasattr(result, "summary")
    summary = result.summary
    page_counts = dict(result.page_outcome_counts)
    print("Closure only: true")
    print("Parser behavior modified: false")
    print("OCR run: false")
    print("AviationRAG modified: false")
    print("Full-corpus ingestion authorized: false")
    print(f"Pages reviewed: {summary.get('completed_pages', 0)}")
    print(f"PASS: {page_counts.get('PASS', 0)}")
    print(f"REVIEW: {page_counts.get('REVIEW', 0)}")
    print(f"FAIL: {page_counts.get('FAIL', 0)}")
    print(f"Document outcomes: {dict(result.document_outcomes)}")
    print(
        "Accepted limitations: "
        f"{[item.code for item in result.current_accepted_limitations]}"
    )
    print(
        "Confirmed nonblocking issues: "
        f"{[item.code for item in result.current_confirmed_nonblocking_issues]}"
    )
    print(f"Blocking findings: {list(result.current_blocking_findings)}")
    print(f"Downstream authorizations: {dict(result.downstream_authorizations)}")
    print(f"Outcome: {result.outcome}")


def _exit_code(outcome: str, *, strict: bool) -> int:
    if outcome == ACCEPTED:
        return 0
    if outcome == ACCEPTED_WITH_LIMITATIONS:
        return 1 if strict else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
