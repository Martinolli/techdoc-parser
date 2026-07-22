"""Command-line interface for techdoc-parser."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import cast

from techdoc_parser.chunking import create_semantic_chunks
from techdoc_parser.core import Chunk
from techdoc_parser.exporters import (
    create_output_manifest,
    export_chunks_json,
    export_document_json,
    export_output_manifest_json,
    export_structured_document,
    export_validation_gate_json,
    export_validation_gate_markdown,
    export_validation_report_json,
)
from techdoc_parser.parser import parse_document
from techdoc_parser.validation import (
    ValidationDecision,
    ValidationReport,
    validate_document_and_chunks_with_decision,
)


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
    parser.add_argument(
        "--validation-gate-output",
        help="Optional combined validation gate JSON output path.",
    )
    parser.add_argument(
        "--validation-summary-output",
        help="Optional validation gate Markdown summary output path.",
    )
    parser.add_argument(
        "--manifest-output",
        help="Optional output manifest JSON path.",
    )
    parser.add_argument(
        "--structured-document-output",
        help=(
            "Optional techdoc-structured-document / 0.1.0 JSON output path. "
            "Requires --structured-document-id."
        ),
    )
    parser.add_argument(
        "--structured-document-id",
        help="Required document ID when --structured-document-output is supplied.",
    )
    parser.add_argument(
        "--document-title",
        help="Optional explicit structured-document title metadata.",
    )
    parser.add_argument(
        "--document-number",
        help="Optional explicit structured-document number metadata.",
    )
    parser.add_argument(
        "--document-revision",
        help="Optional explicit structured-document revision metadata.",
    )
    parser.add_argument(
        "--document-issue",
        help="Optional explicit structured-document issue metadata.",
    )
    parser.add_argument(
        "--document-effective-date",
        help="Optional explicit structured-document effective-date metadata.",
    )
    parser.add_argument(
        "--structured-document-overwrite",
        action="store_true",
        help="Allow replacing an existing structured-document output file.",
    )
    args = parser.parse_args(argv)

    input_path = cast(str, args.input_path)
    output_path = cast(str, args.output)
    indent = cast(int, args.indent)
    chunks_output_path = cast(str | None, args.chunks_output)
    chunk_max_chars = cast(int, args.chunk_max_chars)
    validation_output_path = cast(str | None, args.validation_output)
    validation_gate_output_path = cast(str | None, args.validation_gate_output)
    validation_summary_output_path = cast(
        str | None,
        args.validation_summary_output,
    )
    manifest_output_path = cast(str | None, args.manifest_output)
    structured_document_output_path = cast(
        str | None,
        args.structured_document_output,
    )
    structured_document_id = cast(str | None, args.structured_document_id)
    document_title = cast(str | None, args.document_title)
    document_number = cast(str | None, args.document_number)
    document_revision = cast(str | None, args.document_revision)
    document_issue = cast(str | None, args.document_issue)
    document_effective_date = cast(str | None, args.document_effective_date)
    structured_document_overwrite = cast(bool, args.structured_document_overwrite)

    structured_metadata_supplied = any(
        value is not None
        for value in (
            structured_document_id,
            document_title,
            document_number,
            document_revision,
            document_issue,
            document_effective_date,
        )
    )
    if structured_document_output_path is None and (
        structured_metadata_supplied or structured_document_overwrite
    ):
        print(
            "Error: structured-document metadata and overwrite flags require "
            "--structured-document-output.",
            file=sys.stderr,
        )
        return 1
    if structured_document_output_path is not None and structured_document_id is None:
        print(
            "Error: --structured-document-id is required when "
            "--structured-document-output is supplied.",
            file=sys.stderr,
        )
        return 1
    if structured_document_output_path is not None:
        structured_output = Path(structured_document_output_path)
        if structured_output.resolve(strict=False) == Path(input_path).resolve(
            strict=False
        ):
            print(
                "Error: structured-document output path must not be the input "
                "source path.",
                file=sys.stderr,
            )
            return 1
        if structured_output.exists() and structured_output.is_dir():
            print(
                "Error: structured-document output path is a directory.",
                file=sys.stderr,
            )
            return 1
        if structured_output.exists() and not structured_document_overwrite:
            print(
                "Error: structured-document output already exists; pass "
                "--structured-document-overwrite to replace it.",
                file=sys.stderr,
            )
            return 1

    try:
        document = parse_document(input_path)
        export_document_json(document, output_path, indent=indent)
        structured_document_manifest_entry: dict[str, object] | None = None
        if structured_document_output_path is not None and structured_document_id:
            structured_document_artifact = export_structured_document(
                document,
                source_path=input_path,
                output_path=structured_document_output_path,
                document_id=structured_document_id,
                document_title=document_title,
                document_number=document_number,
                revision=document_revision,
                issue=document_issue,
                effective_date=document_effective_date,
                overwrite=structured_document_overwrite,
                indent=indent,
            )
            structured_document_manifest_entry = (
                structured_document_artifact.to_manifest_entry()
            )
        chunks: list[Chunk] | None = None
        report: ValidationReport | None = None
        decision: ValidationDecision | None = None
        if (
            chunks_output_path is not None
            or validation_output_path is not None
            or validation_gate_output_path is not None
            or validation_summary_output_path is not None
        ):
            chunks = create_semantic_chunks(document, max_chars=chunk_max_chars)
        if chunks_output_path is not None and chunks is not None:
            export_chunks_json(chunks, chunks_output_path, indent=indent)
        if (
            validation_output_path is not None
            or validation_gate_output_path is not None
            or validation_summary_output_path is not None
        ) and chunks is not None:
            report, decision = validate_document_and_chunks_with_decision(
                document,
                chunks,
            )
            if validation_output_path is not None:
                export_validation_report_json(
                    report,
                    validation_output_path,
                    indent=indent,
                )
            if validation_gate_output_path is not None:
                export_validation_gate_json(
                    report,
                    decision,
                    validation_gate_output_path,
                    indent=indent,
                )
            if validation_summary_output_path is not None:
                export_validation_gate_markdown(
                    report,
                    decision,
                    validation_summary_output_path,
                )
        if manifest_output_path is not None:
            manifest = create_output_manifest(
                document=document,
                chunks=chunks,
                validation_report=report,
                validation_decision=decision,
                document_json_path=output_path,
                chunks_json_path=chunks_output_path,
                validation_json_path=validation_output_path,
                gate_json_path=validation_gate_output_path,
                validation_summary_markdown_path=validation_summary_output_path,
                structured_document_artifact=structured_document_manifest_entry,
            )
            export_output_manifest_json(
                manifest,
                manifest_output_path,
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
    if validation_gate_output_path is not None:
        message += f" Wrote validation gate JSON to '{validation_gate_output_path}'."
    if validation_summary_output_path is not None:
        message += (
            f" Wrote validation summary Markdown to '{validation_summary_output_path}'."
        )
    if structured_document_output_path is not None:
        message += (
            f" Wrote structured-document JSON to '{structured_document_output_path}'."
        )
    if manifest_output_path is not None:
        message += f" Wrote output manifest JSON to '{manifest_output_path}'."
    print(message)
    return 0
