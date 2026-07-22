#!/usr/bin/env python
"""Run the offline AviationRAG compatibility gate for a structured artifact."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.compatibility import (  # noqa: E402
    aviationrag_compatibility_gate_result_to_dict,
    run_aviationrag_compatibility_gate,
    write_aviationrag_compatibility_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact",
        required=True,
        help="StructuredDocument JSON artifact.",
    )
    parser.add_argument(
        "--manifest",
        required=True,
        help="Manifest JSON containing artifacts[].",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Original source document path.",
    )
    parser.add_argument(
        "--aviationrag-root",
        required=True,
        help="Local AviationRAG repository root.",
    )
    parser.add_argument(
        "--comparison-artifact",
        help="Optional second artifact generated from the same input.",
    )
    parser.add_argument(
        "--approve-warning",
        action="append",
        default=[],
        help="Approve one AviationRAG validator warning code. Repeatable.",
    )
    parser.add_argument("--report", help="Optional compatibility report output path.")
    parser.add_argument(
        "--allow-report-write",
        action="store_true",
        help="Allow writing the compatibility report to --report.",
    )
    args = parser.parse_args(argv)

    result = run_aviationrag_compatibility_gate(
        artifact_path=args.artifact,
        manifest_path=args.manifest,
        source_path=args.source,
        aviationrag_root=args.aviationrag_root,
        comparison_artifact_path=args.comparison_artifact,
        approved_warning_codes=args.approve_warning,
    )

    _print_result(result=aviationrag_compatibility_gate_result_to_dict(result))
    if args.report:
        if args.allow_report_write:
            write_aviationrag_compatibility_report(
                result,
                args.report,
                overwrite=True,
            )
            print(f"Report written: {Path(args.report).name}")
        else:
            print(
                "Report not written. Re-run with --allow-report-write to "
                "write the report."
            )

    if result.outcome == "PASS":
        return 0
    if result.outcome == "REVIEW":
        return 2
    return 1


def _print_result(*, result: dict[str, object]) -> None:
    validator = _dict_value(result.get("validator"))
    warning_policy = _dict_value(result.get("warning_policy"))
    entity_counts = _dict_value(result.get("entity_counts"))
    checks = result.get("checks")
    print("AviationRAG compatibility gate is offline/report-only.")
    print(
        "No AviationRAG import, ingestion, embeddings, Astra, or FAISS work "
        "is performed."
    )
    print(f"Outcome: {result.get('outcome')}")
    print(f"Schema: {result.get('schema_name')} / {result.get('schema_version')}")
    print(f"Document ID: {result.get('document_id')}")
    print(f"Source file: {result.get('source_filename')}")
    print(f"Source checksum matches: {_check_status(result, 'source_checksum')}")
    print(f"Artifact checksum matches: {_check_status(result, 'artifact_checksum')}")
    print(f"Validator valid: {validator.get('is_valid')}")
    print(f"Validator errors: {validator.get('error_count')}")
    print(f"Validator warnings: {validator.get('warning_count')}")
    print(f"Unapproved warnings: {warning_policy.get('unapproved_warning_codes')}")
    print(
        f"Table count interpretation: {entity_counts.get('table_count_interpretation')}"
    )
    print(f"Cross references: {result.get('reference_status_counts')}")
    confidence_count = len(_list_value(result.get("confidence_field_paths")))
    print(f"Confidence fields: {confidence_count}")
    print(f"Determinism checked: {result.get('determinism_checked')}")
    print(f"AviationRAG commit: {result.get('aviationrag_commit')}")
    if isinstance(checks, list):
        for check in checks:
            if isinstance(check, dict) and check.get("status") in {"review", "fail"}:
                status = str(check.get("status")).upper()
                print(f"{status} {check.get('name')}: {check.get('message')}")


def _check_status(result: dict[str, object], name: str) -> str:
    checks = result.get("checks")
    if not isinstance(checks, list):
        return "unknown"
    for check in checks:
        if isinstance(check, dict) and check.get("name") == name:
            return str(check.get("status"))
    return "unknown"


def _dict_value(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list_value(value: object) -> list[object]:
    return value if isinstance(value, list) else []


if __name__ == "__main__":
    raise SystemExit(main())
