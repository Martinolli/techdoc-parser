#!/usr/bin/env python
"""Run read-only approved pilot corpus inventory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation.pilot_corpus_inventory import (  # noqa: E402
    ACCURACY_DISCLAIMER,
    FAIL,
    PASS,
    REVIEW,
    inventory_pilot_corpus,
)
from techdoc_parser.evaluation.pilot_corpus_reporting import (  # noqa: E402
    write_pilot_corpus_inventory_reports,
)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = inventory_pilot_corpus(
        args.input_dir,
        expected_document_count=args.expected_count,
        max_pages_per_document=args.max_pages_per_document,
    )
    if args.list_documents:
        for document in result.documents:
            print(f"{document.filename}\t{document.page_count}\t{document.text_mode}")
        return _exit_code(result.outcome, strict=args.strict)

    print(ACCURACY_DISCLAIMER)
    print(
        "Scope: inventory/planning only; no OCR, no PDF modification, no "
        "accuracy evaluation, no AviationRAG work, no embeddings, no external APIs."
    )
    print(f"Outcome: {result.outcome}")
    print(f"Document count: {result.document_count}")
    print(f"Git ignored: {result.git_ignore_summary.get('ignored', 0)}")
    print(f"Git tracked PDFs: {result.git_ignore_summary.get('tracked', 0)}")
    print(f"Duplicate hash groups: {len(result.duplicate_hashes)}")
    access_issue_count = sum(1 for issue in result.issues if issue.severity == "error")
    print(f"Access issues: {access_issue_count}")
    print(f"Total pages: {result.total_pages}")
    print(f"Text modes: {dict(result.text_mode_counts)}")
    print(f"Orientations: {dict(result.orientation_counts)}")
    print(f"Proposed page count: {result.proposed_page_count}")
    print(f"Priorities: {dict(result.priority_counts)}")

    if args.report_json or args.report_markdown:
        written = write_pilot_corpus_inventory_reports(
            result,
            json_path=args.report_json,
            markdown_path=args.report_markdown,
            allow_report_write=args.allow_report_write,
            include_hashes=True,
        )
        for path in written:
            print(f"Wrote report: {path}")
    else:
        print("Reports not written.")
    return _exit_code(result.outcome, strict=args.strict)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inventory approved local pilot PDFs and propose representative "
            "pages. This is read-only planning; it does not run OCR or evaluate "
            "source accuracy."
        )
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Local ignored input directory.",
    )
    parser.add_argument("--expected-count", type=int, default=8)
    parser.add_argument("--report-json", help="Optional JSON report path.")
    parser.add_argument("--report-markdown", help="Optional Markdown report path.")
    parser.add_argument("--allow-report-write", action="store_true")
    parser.add_argument("--max-pages-per-document", type=int, default=10)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--list-documents", action="store_true")
    return parser


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
