"""Command-line interface for techdoc-parser."""

from __future__ import annotations

import argparse
import sys
from typing import cast

from techdoc_parser.chunking import create_semantic_chunks
from techdoc_parser.exporters import (
    export_chunks_json,
    export_document_json,
    export_validation_report_json,
)
from techdoc_parser.parser import parse_document
from techdoc_parser.validation import validate_document_and_chunks


def main(argv: list[str] | None = None) -> int:
    """Run the techdoc-parser command-line interface."""
    parser = argparse.ArgumentParser(
        prog="techdoc-parse",
        description="Parse a technical document and export it as JSON.",
    )
    parser.add_argument("input_path", help="Input document path.")
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output JSON path.",
    )
    parser.add_argument(
        "--indent",
        default=2,
        type=int,
        help="JSON indentation level.",
    )
    parser.add_argument(
        "--chunks-output",
        help="Optional semantic chunks JSON output path.",
    )
    parser.add_argument(
        "--chunk-max-chars",
        default=1200,
        type=int,
        help="Maximum characters per semantic chunk.",
    )
    parser.add_argument(
        "--validation-output",
        help="Optional validation report JSON output path.",
    )
    args = parser.parse_args(argv)

    input_path = cast(str, args.input_path)
    output_path = cast(str, args.output)
    indent = cast(int, args.indent)
    chunks_output_path = cast(str | None, args.chunks_output)
    chunk_max_chars = cast(int, args.chunk_max_chars)
    validation_output_path = cast(str | None, args.validation_output)

    try:
        document = parse_document(input_path)
        export_document_json(document, output_path, indent=indent)
        chunks = None
        if chunks_output_path is not None or validation_output_path is not None:
            chunks = create_semantic_chunks(document, max_chars=chunk_max_chars)
        if chunks_output_path is not None and chunks is not None:
            export_chunks_json(chunks, chunks_output_path, indent=indent)
        if validation_output_path is not None and chunks is not None:
            export_validation_report_json(
                validate_document_and_chunks(document, chunks),
                validation_output_path,
                indent=indent,
            )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    message = f"Parsed '{input_path}' and wrote JSON to '{output_path}'."
    if chunks_output_path is not None:
        message += f" Wrote chunks JSON to '{chunks_output_path}'."
    if validation_output_path is not None:
        message += f" Wrote validation JSON to '{validation_output_path}'."
    print(message)
    return 0
