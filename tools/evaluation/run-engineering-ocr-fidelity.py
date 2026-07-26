#!/usr/bin/env python
"""Run controlled D.7a engineering OCR-fidelity evaluation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation.engineering_ocr_fidelity import (  # noqa: E402
    ACCEPTED_WITH_LIMITATIONS,
    BLOCKED,
    FAIL,
    OWNER_REVIEW_REQUIRED,
    PASS,
    evaluate_engineering_ocr_fidelity,
    load_engineering_ocr_text_artifact,
    load_owner_review_decisions,
)
from techdoc_parser.evaluation.engineering_ocr_reporting import (  # noqa: E402
    write_engineering_ocr_reports,
    write_engineering_ocr_review_package,
)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    owner_reviews = (
        load_owner_review_decisions(
            args.review_checklist,
            document_key=args.document_key,
        )
        if args.review_checklist
        else None
    )
    result = evaluate_engineering_ocr_fidelity(
        source_path=args.source,
        native_text_artifact=args.native_text_artifact,
        ocr_text_artifact=args.ocr_text_artifact,
        document_key=args.document_key,
        expected_page_count=args.expected_pages,
        owner_reviews=owner_reviews,
    )
    _print_summary(result)
    if args.output_dir:
        if result.outcome == BLOCKED and args.ocr_text_artifact is None:
            print("Review package skipped: no supported OCR candidate artifact exists.")
        else:
            native_pages = (
                load_engineering_ocr_text_artifact(args.native_text_artifact)
                if args.native_text_artifact
                else None
            )
            ocr_pages = (
                load_engineering_ocr_text_artifact(args.ocr_text_artifact)
                if args.ocr_text_artifact
                else None
            )
            written = write_engineering_ocr_review_package(
                output_dir=args.output_dir,
                source_path=args.source,
                page_results=result.page_results,
                native_text_by_page=native_pages,
                ocr_text_by_page=ocr_pages,
                allow_local_write=args.allow_local_write,
            )
            print(f"Local review package files written: {len(written)}")
    if args.report_json or args.report_markdown:
        written_reports = write_engineering_ocr_reports(
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
            "Run controlled engineering OCR-fidelity evaluation. The tool does "
            "not run OCR; it compares supplied OCR artifacts or returns a "
            "controlled capability gap."
        )
    )
    parser.add_argument("--source", required=True)
    parser.add_argument("--document-key", default="wing_design_chapter_7")
    parser.add_argument("--expected-pages", type=int, default=43)
    parser.add_argument("--native-text-artifact")
    parser.add_argument("--ocr-text-artifact")
    parser.add_argument("--output-dir")
    parser.add_argument("--allow-local-write", action="store_true")
    parser.add_argument("--report-json")
    parser.add_argument("--report-markdown")
    parser.add_argument("--allow-report-write", action="store_true")
    parser.add_argument("--review-checklist", action="append", default=[])
    parser.add_argument("--strict", action="store_true")
    return parser


def _print_summary(result: object) -> None:
    assert hasattr(result, "outcome")
    assert hasattr(result, "capability")
    assert hasattr(result, "page_results")
    assert hasattr(result, "page_outcome_counts")
    assert hasattr(result, "source_profile_counts")
    print("Scope: controlled engineering OCR fidelity, D.7a-1 only.")
    print("D.7a-2 owner review completed: false")
    print("OCR run by evaluator: false")
    print("Parser behavior modified: false")
    print("Source PDF modified/copied/committed: false")
    print("AviationRAG modified: false")
    print("Embeddings/vector stores/retrieval used: false")
    print(f"Source filename: {result.source_filename}")
    print(f"Source SHA-256: {result.source_sha256}")
    print(f"Pages observed: {result.observed_page_count}")
    print(f"OCR capability status: {result.capability.status}")
    print(f"Pages evaluated/characterized: {len(result.page_results)}")
    print(f"Page outcomes: {dict(result.page_outcome_counts)}")
    print(f"Source profiles: {dict(result.source_profile_counts)}")
    print(f"Outcome: {result.outcome}")


def _exit_code(outcome: str, *, strict: bool) -> int:
    if outcome in {PASS, ACCEPTED_WITH_LIMITATIONS}:
        return 0
    if outcome == OWNER_REVIEW_REQUIRED:
        return 1 if strict else 2
    if outcome in {FAIL, BLOCKED}:
        return 1
    return 1 if strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
