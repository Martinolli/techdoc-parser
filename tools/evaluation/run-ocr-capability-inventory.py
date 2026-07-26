#!/usr/bin/env python
"""Run read-only OCR capability and environment inventory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation.ocr_capability_inventory import (  # noqa: E402
    BLOCKED,
    ENGINE_INSTALLED_BUT_NOT_INTEGRATED,
    EXISTING_INTEGRATION_INCOMPLETE,
    EXISTING_SUPPORTED_ENGINE_AVAILABLE,
    NO_ENGINE_INSTALLED,
    inventory_ocr_capabilities,
)
from techdoc_parser.evaluation.ocr_capability_reporting import (  # noqa: E402
    write_ocr_capability_inventory_report,
)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    _print_scope()
    if bool(args.report_json) != bool(args.report_markdown):
        parser.error("--report-json and --report-markdown must be provided together.")
    if (args.report_json or args.report_markdown) and not args.allow_report_write:
        parser.error("Report writing requires --allow-report-write.")
    result = inventory_ocr_capabilities(repository_root=args.repository_root)
    print(f"Outcome: {result.outcome}")
    print(f"Recommended next action: {result.recommended_next_action}")
    print(
        "Supported execution path available: "
        f"{result.supported_execution_path_available}"
    )
    print(f"Page rendering available: {result.page_rendering_available}")
    print(f"Blocking gaps: {', '.join(result.blocking_gap_codes) or 'none'}")
    if args.report_json and args.report_markdown:
        write_ocr_capability_inventory_report(
            result,
            json_path=args.report_json,
            markdown_path=args.report_markdown,
            allow_write=args.allow_report_write,
        )
        print(f"Wrote sanitized JSON report: {args.report_json}")
        print(f"Wrote sanitized Markdown report: {args.report_markdown}")
    return _exit_code(result.outcome)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a read-only OCR capability inventory. The tool does not run "
            "OCR recognition, process source documents, install software, or "
            "download packages."
        )
    )
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--report-json")
    parser.add_argument("--report-markdown")
    parser.add_argument("--allow-report-write", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def _print_scope() -> None:
    print("Read-only OCR capability inventory.")
    print("No OCR recognition executed.")
    print("No software installed.")
    print("No packages downloaded.")
    print("No source document processed.")
    print("No AviationRAG changes.")


def _exit_code(outcome: str) -> int:
    if outcome == EXISTING_SUPPORTED_ENGINE_AVAILABLE:
        return 0
    if outcome in {
        ENGINE_INSTALLED_BUT_NOT_INTEGRATED,
        EXISTING_INTEGRATION_INCOMPLETE,
    }:
        return 2
    if outcome == NO_ENGINE_INSTALLED:
        return 3
    if outcome == BLOCKED:
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
