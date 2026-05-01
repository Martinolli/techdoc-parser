"""Command-line interface for techdoc-parser."""

from __future__ import annotations

import argparse
import sys
from typing import cast

from techdoc_parser.exporters import export_document_json
from techdoc_parser.parser import parse_document


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
    args = parser.parse_args(argv)

    input_path = cast(str, args.input_path)
    output_path = cast(str, args.output)
    indent = cast(int, args.indent)

    try:
        document = parse_document(input_path)
        export_document_json(document, output_path, indent=indent)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Parsed '{input_path}' and wrote JSON to '{output_path}'.")
    return 0
