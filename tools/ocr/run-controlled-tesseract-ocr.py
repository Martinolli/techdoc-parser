#!/usr/bin/env python
"""Run the explicit controlled Tesseract OCR adapter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.ocr import (  # noqa: E402
    FAIL,
    OCR_ALL_PAGES,
    PASS,
    PASS_WITH_WARNINGS,
    ControlledOcrRequest,
    run_controlled_tesseract_ocr,
    write_controlled_ocr_artifacts,
)

CONTROLLED_NOTICE = (
    "Controlled OCR execution only.\n"
    "OCR ran only because it was explicitly requested.\n"
    "Default parser extraction was not changed.\n"
    "Raw and normalized OCR remain separate.\n"
    "No AviationRAG activity.\n"
    "No embeddings, Astra, or FAISS activity."
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    print(CONTROLLED_NOTICE)
    if args.output_dir and not args.allow_output_write:
        print(
            "Error: --output-dir requires --allow-output-write.",
            file=sys.stderr,
        )
        return 1
    try:
        request = ControlledOcrRequest(
            source_path=args.source,
            document_id=args.document_id,
            mode=args.mode,
            languages=tuple(args.language),
            selected_pages=_parse_pages(args.pages),
            dpi=args.dpi,
            psm=args.psm,
            oem=args.oem,
            timeout_seconds=args.timeout_seconds,
            strict=args.strict,
            preserve_rendered_pages=args.preserve_rendered_pages,
        )
    except ValueError as exc:
        print(f"Request invalid: {exc}", file=sys.stderr)
        return 1

    result = run_controlled_tesseract_ocr(request)
    print(f"Outcome: {result.outcome}")
    print(f"Document ID: {result.request.document_id}")
    print(f"Source filename: {result.source_filename}")
    print(f"Engine version: {result.engine_version or 'unavailable'}")
    print(f"Requested languages: {'+'.join(result.request.languages)}")
    print(f"Available languages: {', '.join(result.available_languages) or 'none'}")
    print(f"Requested pages: {list(result.requested_pages)}")
    print(f"Processed pages: {list(result.processed_pages)}")
    print(f"Failed pages: {list(result.failed_pages)}")
    if result.warnings:
        print(f"Warnings: {', '.join(result.warnings)}")
    if result.errors:
        print(f"Errors: {', '.join(result.errors)}")
    if result.limitations:
        print("Limitations:")
        for limitation in result.limitations:
            print(f"- {limitation}")

    if args.output_dir:
        try:
            written = write_controlled_ocr_artifacts(
                result,
                args.output_dir,
                allow_write=args.allow_output_write,
                overwrite=args.overwrite,
                preserve_rendered_pages=args.preserve_rendered_pages,
            )
        except (OSError, PermissionError, ValueError) as exc:
            print(f"Write failed: {exc}", file=sys.stderr)
            return 1
        print(f"OCR artifact: {written.artifact_path}")
        print(f"OCR artifact sha256: {written.artifact_sha256}")
        print(f"OCR manifest: {written.manifest_path}")
        print(f"OCR manifest sha256: {written.manifest_sha256}")

    if result.outcome == PASS:
        return 0
    if result.outcome == PASS_WITH_WARNINGS:
        return 2
    if result.outcome == FAIL:
        return 1
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run controlled, explicit Tesseract OCR for evaluation artifacts."
    )
    parser.add_argument("--source", required=True, help="Source PDF path.")
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--mode", default=OCR_ALL_PAGES)
    parser.add_argument("--language", action="append", required=True)
    parser.add_argument(
        "--pages",
        help="Comma-separated one-based page numbers for ocr_selected_pages.",
    )
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--psm", type=int, default=6)
    parser.add_argument("--oem", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--output-dir")
    parser.add_argument("--allow-output-write", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--preserve-rendered-pages", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def _parse_pages(value: str | None) -> tuple[int, ...] | None:
    if value is None or not value.strip():
        return None
    pages: list[int] = []
    for item in value.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        pages.append(int(stripped))
    return tuple(pages)


if __name__ == "__main__":
    raise SystemExit(main())
