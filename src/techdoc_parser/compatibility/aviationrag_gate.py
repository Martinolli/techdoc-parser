"""Formal offline AviationRAG compatibility gate.

The gate validates one Phase 13G structured-document artifact plus its manifest
against local contract checks and the sibling AviationRAG validator. This module
does not import AviationRAG or write inside the AviationRAG repository.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from techdoc_parser.exporters.structured_document import compute_source_sha256
from techdoc_parser.version import PARSER_VERSION

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_REFERENCE_STATUSES = {
    "resolved",
    "unresolved",
    "external",
    "ambiguous",
    "not_attempted",
}
_KNOWN_CONFIDENCE_FIELDS = {
    "classification_confidence",
    "extraction_confidence",
    "ocr_confidence",
    "provenance_confidence",
    "structure_confidence",
}
_GENERIC_CONFIDENCE_FIELD = "confidence"


@dataclass(frozen=True)
class CompatibilityCheck:
    """One deterministic compatibility check outcome."""

    name: str
    status: str
    message: str
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AviationRAGValidatorResult:
    """Adapter result from the external AviationRAG validator CLI."""

    schema_name: str | None
    schema_version: str | None
    document_id: str | None
    is_valid: bool
    error_count: int
    warning_count: int
    issues: list[dict[str, object]]
    summary: dict[str, object]
    stdout: str
    stderr: str
    return_code: int


@dataclass(frozen=True)
class AviationRAGCompatibilityGateResult:
    """Machine-readable formal AviationRAG compatibility gate result."""

    outcome: str
    schema_name: str | None
    schema_version: str | None
    document_id: str | None
    source_filename: str
    source_sha256_expected: str | None
    source_sha256_actual: str | None
    artifact_sha256_expected: str | None
    artifact_sha256_actual: str | None
    validator_is_valid: bool
    validator_error_count: int
    validator_warning_count: int
    approved_warning_codes: list[str]
    unapproved_warning_codes: list[str]
    checks: list[CompatibilityCheck]
    entity_counts: dict[str, int | str | None]
    validator_summary: dict[str, object]
    reference_status_counts: dict[str, int]
    confidence_field_paths: list[str]
    determinism_checked: bool
    determinism_passed: bool | None
    techdoc_parser_version: str
    aviationrag_commit: str | None
    summary: str


ValidatorRunner = Callable[..., AviationRAGValidatorResult]


def run_aviationrag_validator(
    *,
    artifact_path: str | Path,
    aviationrag_root: str | Path,
    timeout_seconds: float = 30.0,
) -> AviationRAGValidatorResult:
    """Run the sibling AviationRAG validator through a subprocess.

    A temporary report path outside the AviationRAG repository is supplied with
    ``--allow-report-write`` so the validator can emit its canonical JSON report
    without mutating the sibling repository.
    """
    artifact = Path(artifact_path).resolve(strict=False)
    root = Path(aviationrag_root).resolve(strict=False)
    if not root.exists():
        raise FileNotFoundError(f"AviationRAG root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"AviationRAG root is not a directory: {root}")

    validator = root / "tools" / "chunking" / "validate-structured-document.py"
    if not validator.exists():
        raise FileNotFoundError(f"AviationRAG validator not found: {validator}")

    with tempfile.TemporaryDirectory(prefix="techdoc-aviationrag-gate-") as tmpdir:
        report_path = Path(tmpdir) / "aviationrag_validation_report.json"
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(validator),
                    "--input",
                    str(artifact),
                    "--report",
                    str(report_path),
                    "--allow-report-write",
                ],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"AviationRAG validator timed out after {timeout_seconds} seconds."
            ) from exc

        if not report_path.exists():
            raise RuntimeError(
                "AviationRAG validator did not write its requested temporary report."
            )
        report = _load_json_object(report_path)
        return _validator_result_from_report(
            report,
            stdout=completed.stdout,
            stderr=completed.stderr,
            return_code=completed.returncode,
        )


def run_aviationrag_compatibility_gate(
    *,
    artifact_path: str | Path,
    manifest_path: str | Path,
    source_path: str | Path,
    aviationrag_root: str | Path,
    comparison_artifact_path: str | Path | None = None,
    approved_warning_codes: Iterable[str] = (),
    validator_runner: ValidatorRunner = run_aviationrag_validator,
    aviationrag_commit: str | None = None,
) -> AviationRAGCompatibilityGateResult:
    """Run the formal offline compatibility gate."""
    artifact = Path(artifact_path).resolve(strict=False)
    manifest = Path(manifest_path).resolve(strict=False)
    source = Path(source_path).resolve(strict=False)
    comparison = Path(comparison_artifact_path) if comparison_artifact_path else None
    approved_codes = sorted(set(approved_warning_codes))
    checks: list[CompatibilityCheck] = []

    data = _load_json_object(artifact)
    manifest_data = _load_json_object(manifest)
    manifest_entry = _structured_artifact_entry(manifest_data)
    document = _mapping_value(data.get("document"))

    schema_name = _optional_str(data.get("schema_name"))
    schema_version = _optional_str(data.get("schema_version"))
    document_id = _optional_str(document.get("document_id"))
    source_filename = _optional_str(document.get("source_filename")) or source.name
    source_expected = _optional_str(manifest_entry.get("source_sha256"))
    source_from_artifact = _optional_str(document.get("source_hash"))
    source_actual = compute_source_sha256(source)
    artifact_expected = _optional_str(manifest_entry.get("artifact_sha256"))
    artifact_actual = _compute_file_sha256(artifact)

    checks.extend(
        _manifest_checks(
            artifact=artifact,
            manifest=manifest,
            data=data,
            manifest_data=manifest_data,
            manifest_entry=manifest_entry,
        )
    )
    checks.append(
        _checksum_check(
            name="source_checksum",
            expected=source_expected,
            actual=source_actual,
            artifact_value=source_from_artifact,
        )
    )
    checks.append(
        _checksum_check(
            name="artifact_checksum",
            expected=artifact_expected,
            actual=artifact_actual,
            artifact_value=artifact_actual,
        )
    )
    checks.append(
        _metadata_check(
            manifest_entry=manifest_entry,
            data=data,
            source_filename=source_filename,
            source_path=source,
        )
    )

    entity_counts = _entity_counts(data)
    validator_result, validator_check = _run_validator(
        artifact=artifact,
        aviationrag_root=Path(aviationrag_root),
        runner=validator_runner,
    )
    checks.append(validator_check)

    warning_check, unapproved_codes = _warning_policy_check(
        validator_result=validator_result,
        approved_codes=approved_codes,
    )
    checks.append(warning_check)

    table_check = _table_count_check(
        entity_counts=entity_counts,
        validator_summary=validator_result.summary,
    )
    checks.append(table_check)
    entity_counts["aviationrag_table_count"] = _int_value(
        validator_result.summary.get("table_count")
    )
    entity_counts["table_count_interpretation"] = str(
        table_check.details.get("interpretation", "unknown")
    )

    reference_counts, reference_check = _cross_reference_check(data)
    checks.append(reference_check)
    confidence_paths, confidence_check = _confidence_check(data)
    checks.append(confidence_check)

    determinism_checked = comparison is not None
    determinism_passed: bool | None = None
    checks.append(
        _determinism_check(
            artifact=artifact,
            comparison=comparison,
            determinism_checked=determinism_checked,
        )
    )
    if comparison is not None:
        determinism_passed = artifact.read_bytes() == comparison.read_bytes()

    commit = aviationrag_commit or _detect_git_commit(Path(aviationrag_root))
    outcome = _aggregate_outcome(checks)
    return AviationRAGCompatibilityGateResult(
        outcome=outcome,
        schema_name=schema_name,
        schema_version=schema_version,
        document_id=document_id,
        source_filename=source_filename,
        source_sha256_expected=source_expected,
        source_sha256_actual=source_actual,
        artifact_sha256_expected=artifact_expected,
        artifact_sha256_actual=artifact_actual,
        validator_is_valid=validator_result.is_valid,
        validator_error_count=validator_result.error_count,
        validator_warning_count=validator_result.warning_count,
        approved_warning_codes=approved_codes,
        unapproved_warning_codes=unapproved_codes,
        checks=checks,
        entity_counts=entity_counts,
        validator_summary=validator_result.summary,
        reference_status_counts=reference_counts,
        confidence_field_paths=confidence_paths,
        determinism_checked=determinism_checked,
        determinism_passed=determinism_passed,
        techdoc_parser_version=PARSER_VERSION,
        aviationrag_commit=commit,
        summary=_summary(outcome, checks),
    )


def aviationrag_compatibility_gate_result_to_dict(
    result: AviationRAGCompatibilityGateResult,
) -> dict[str, object]:
    """Return a JSON-serializable gate report without raw temp-path output."""
    return {
        "gate_name": "aviationrag_compatibility_gate",
        "outcome": result.outcome,
        "schema_name": result.schema_name,
        "schema_version": result.schema_version,
        "document_id": result.document_id,
        "source_filename": result.source_filename,
        "source_sha256_expected": result.source_sha256_expected,
        "source_sha256_actual": result.source_sha256_actual,
        "artifact_sha256_expected": result.artifact_sha256_expected,
        "artifact_sha256_actual": result.artifact_sha256_actual,
        "validator": {
            "is_valid": result.validator_is_valid,
            "error_count": result.validator_error_count,
            "warning_count": result.validator_warning_count,
            "summary": result.validator_summary,
        },
        "warning_policy": {
            "approved_warning_codes": result.approved_warning_codes,
            "unapproved_warning_codes": result.unapproved_warning_codes,
        },
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "message": check.message,
                "details": check.details,
            }
            for check in result.checks
        ],
        "entity_counts": result.entity_counts,
        "reference_status_counts": result.reference_status_counts,
        "confidence_field_paths": result.confidence_field_paths,
        "determinism_checked": result.determinism_checked,
        "determinism_passed": result.determinism_passed,
        "techdoc_parser_version": result.techdoc_parser_version,
        "aviationrag_commit": result.aviationrag_commit,
        "summary": result.summary,
    }


def aviationrag_compatibility_gate_result_to_json(
    result: AviationRAGCompatibilityGateResult,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a gate report deterministically."""
    return json.dumps(
        aviationrag_compatibility_gate_result_to_dict(result),
        indent=indent,
        sort_keys=True,
    )


def write_aviationrag_compatibility_report(
    result: AviationRAGCompatibilityGateResult,
    output_path: str | Path,
    *,
    overwrite: bool = False,
    indent: int | None = 2,
) -> Path:
    """Write one compatibility report atomically when explicitly requested."""
    path = Path(output_path)
    _validate_report_output_path(path, overwrite=overwrite)
    payload = (
        aviationrag_compatibility_gate_result_to_json(result, indent=indent) + "\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    try:
        if temp_path.exists():
            temp_path.unlink()
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and not overwrite:
            raise FileExistsError(f"Compatibility report already exists: {path}")
        os.replace(temp_path, path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    return path


def _validator_result_from_report(
    report: Mapping[str, Any],
    *,
    stdout: str,
    stderr: str,
    return_code: int,
) -> AviationRAGValidatorResult:
    schema_name = _optional_str(report.get("schema_name"))
    schema_version = _optional_str(report.get("schema_version"))
    document_id = _optional_str(report.get("document_id"))
    is_valid = report.get("is_valid")
    error_count = report.get("error_count")
    warning_count = report.get("warning_count")
    summary = report.get("summary")
    issues = report.get("issues")
    if not isinstance(is_valid, bool):
        raise ValueError("AviationRAG report field is_valid must be a boolean.")
    if not isinstance(error_count, int) or error_count < 0:
        raise ValueError(
            "AviationRAG report field error_count must be a non-negative integer."
        )
    if not isinstance(warning_count, int) or warning_count < 0:
        raise ValueError(
            "AviationRAG report field warning_count must be a non-negative integer."
        )
    if not isinstance(summary, Mapping):
        raise ValueError("AviationRAG report field summary must be an object.")
    if not isinstance(issues, list):
        raise ValueError("AviationRAG report field issues must be a list.")
    return AviationRAGValidatorResult(
        schema_name=schema_name,
        schema_version=schema_version,
        document_id=document_id,
        is_valid=is_valid,
        error_count=error_count,
        warning_count=warning_count,
        issues=[_issue_dict(issue) for issue in issues],
        summary={str(key): value for key, value in summary.items()},
        stdout=stdout,
        stderr=stderr,
        return_code=return_code,
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path.name}")
    return data


def _structured_artifact_entry(manifest: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return {}
    matches = [
        artifact
        for artifact in artifacts
        if isinstance(artifact, Mapping)
        and artifact.get("artifact_type") == "structured_document"
    ]
    if len(matches) != 1:
        return {}
    return dict(matches[0])


def _manifest_checks(
    *,
    artifact: Path,
    manifest: Path,
    data: Mapping[str, Any],
    manifest_data: Mapping[str, Any],
    manifest_entry: Mapping[str, Any],
) -> list[CompatibilityCheck]:
    checks: list[CompatibilityCheck] = []
    artifacts = manifest_data.get("artifacts")
    if not isinstance(artifacts, list):
        checks.append(
            CompatibilityCheck(
                "manifest_artifact_registration",
                "fail",
                "Manifest must include artifacts[] with one structured_document entry.",
            )
        )
        return checks
    structured_entries = [
        entry
        for entry in artifacts
        if isinstance(entry, Mapping)
        and entry.get("artifact_type") == "structured_document"
    ]
    if len(structured_entries) != 1:
        checks.append(
            CompatibilityCheck(
                "manifest_artifact_registration",
                "fail",
                "Manifest must include exactly one structured_document artifact entry.",
                {"structured_document_entries": len(structured_entries)},
            )
        )
        return checks

    entry_path = _optional_str(manifest_entry.get("path"))
    output_path = _mapping_value(manifest_data.get("outputs")).get(
        "structured_document"
    )
    path_matches = artifact.resolve(strict=False) in _manifest_path_candidates(
        entry_path,
        manifest,
    )
    output_matches = output_path is None or str(output_path) == entry_path
    media_type = manifest_entry.get("media_type")
    registration_clean = (
        path_matches and output_matches and media_type == "application/json"
    )
    checks.append(
        CompatibilityCheck(
            "manifest_artifact_registration",
            "pass" if registration_clean else "fail",
            "Manifest structured_document entry points to the artifact."
            if registration_clean
            else "Manifest structured_document entry is inconsistent.",
            {
                "artifact_filename": artifact.name,
                "manifest_filename": manifest.name,
                "path_matches": path_matches,
                "output_matches": output_matches,
                "media_type": str(media_type),
            },
        )
    )

    schema_matches = manifest_entry.get("schema_name") == data.get(
        "schema_name"
    ) and manifest_entry.get("schema_version") == data.get("schema_version")
    document_id = _mapping_value(data.get("document")).get("document_id")
    document_id_matches = manifest_entry.get("document_id") == document_id
    checks.append(
        CompatibilityCheck(
            "manifest_schema_identity",
            "pass" if schema_matches and document_id_matches else "fail",
            "Manifest schema identity and document ID match the artifact."
            if schema_matches and document_id_matches
            else "Manifest schema identity or document ID does not match the artifact.",
            {
                "schema_matches": schema_matches,
                "document_id_matches": document_id_matches,
            },
        )
    )
    return checks


def _checksum_check(
    *,
    name: str,
    expected: str | None,
    actual: str | None,
    artifact_value: str | None,
) -> CompatibilityCheck:
    expected_valid = expected is not None and _valid_sha256(expected)
    actual_valid = actual is not None and _valid_sha256(actual)
    artifact_valid = artifact_value is not None and _valid_sha256(artifact_value)
    matches = expected == actual == artifact_value
    checksum_clean = expected_valid and actual_valid and artifact_valid and matches
    status = "pass" if checksum_clean else "fail"
    return CompatibilityCheck(
        name,
        status,
        f"{name} is present, lowercase SHA-256, and matches."
        if status == "pass"
        else f"{name} is missing, malformed, or mismatched.",
        {
            "expected_present": expected is not None,
            "actual_present": actual is not None,
            "artifact_value_present": artifact_value is not None,
            "expected_valid": expected_valid,
            "actual_valid": actual_valid,
            "artifact_value_valid": artifact_valid,
            "matches": matches,
        },
    )


def _metadata_check(
    *,
    manifest_entry: Mapping[str, Any],
    data: Mapping[str, Any],
    source_filename: str,
    source_path: Path,
) -> CompatibilityCheck:
    document = _mapping_value(data.get("document"))
    checks = {
        "schema_name": data.get("schema_name") == "techdoc-structured-document",
        "schema_version": data.get("schema_version") == "0.1.0",
        "parser_name": data.get("parser_name") == "techdoc-parser",
        "parser_version_present": isinstance(data.get("parser_version"), str)
        and bool(data.get("parser_version")),
        "document_id_present": isinstance(document.get("document_id"), str)
        and bool(document.get("document_id")),
        "source_filename_matches": source_filename == source_path.name,
        "manifest_media_type": manifest_entry.get("media_type") == "application/json",
    }
    status = "pass" if all(checks.values()) else "fail"
    return CompatibilityCheck(
        "metadata_consistency",
        status,
        "Structured-document metadata is internally consistent."
        if status == "pass"
        else "Structured-document metadata is incomplete or inconsistent.",
        checks,
    )


def _run_validator(
    *,
    artifact: Path,
    aviationrag_root: Path,
    runner: ValidatorRunner,
) -> tuple[AviationRAGValidatorResult, CompatibilityCheck]:
    try:
        result = runner(artifact_path=artifact, aviationrag_root=aviationrag_root)
    except Exception as exc:
        fallback = AviationRAGValidatorResult(
            schema_name=None,
            schema_version=None,
            document_id=None,
            is_valid=False,
            error_count=1,
            warning_count=0,
            issues=[
                {
                    "code": "AVIATIONRAG_VALIDATOR_FAILED",
                    "severity": "error",
                    "message": str(exc),
                    "path": "$",
                    "entity_id": None,
                }
            ],
            summary={},
            stdout="",
            stderr="",
            return_code=1,
        )
        return fallback, CompatibilityCheck(
            "aviationrag_validator",
            "fail",
            "AviationRAG validator could not be executed.",
            {"error_type": type(exc).__name__},
        )

    status = "pass" if result.is_valid and result.error_count == 0 else "fail"
    return result, CompatibilityCheck(
        "aviationrag_validator",
        status,
        "AviationRAG validator accepted the structured-document artifact."
        if status == "pass"
        else "AviationRAG validator reported errors.",
        {
            "return_code": result.return_code,
            "error_count": result.error_count,
            "warning_count": result.warning_count,
        },
    )


def _warning_policy_check(
    *,
    validator_result: AviationRAGValidatorResult,
    approved_codes: list[str],
) -> tuple[CompatibilityCheck, list[str]]:
    approved = set(approved_codes)
    warning_codes = sorted(
        {
            str(issue.get("code"))
            for issue in validator_result.issues
            if issue.get("severity") == "warning" and issue.get("code") is not None
        }
    )
    unapproved = [code for code in warning_codes if code not in approved]
    if not warning_codes:
        status = "pass"
        message = "AviationRAG validator reported no warnings."
    elif unapproved:
        status = "fail"
        message = "AviationRAG validator reported unapproved warnings."
    else:
        status = "review"
        message = "AviationRAG warnings are explicitly approved and require review."
    return (
        CompatibilityCheck(
            "validator_warning_policy",
            status,
            message,
            {"warning_codes": warning_codes, "unapproved_warning_codes": unapproved},
        ),
        unapproved,
    )


def _entity_counts(data: Mapping[str, Any]) -> dict[str, int | str | None]:
    blocks = _list_value(data.get("blocks"))
    return {
        "page_count": len(_list_value(data.get("pages"))),
        "block_count": len(blocks),
        "section_count": len(_list_value(data.get("sections"))),
        "table_entity_count": len(_list_value(data.get("tables"))),
        "table_block_count": _block_type_count(blocks, {"table"}),
        "figure_entity_count": len(_list_value(data.get("figures"))),
        "figure_caption_block_count": _block_type_count(blocks, {"figure_caption"}),
        "equation_entity_count": len(_list_value(data.get("equations"))),
        "equation_block_count": _block_type_count(blocks, {"equation"}),
        "admonition_entity_count": len(_list_value(data.get("admonitions"))),
        "cross_reference_count": len(_list_value(data.get("cross_references"))),
    }


def _table_count_check(
    *,
    entity_counts: Mapping[str, int | str | None],
    validator_summary: Mapping[str, object],
) -> CompatibilityCheck:
    validator_count = _int_value(validator_summary.get("table_count"))
    table_entities = _int_value(entity_counts.get("table_entity_count"))
    table_blocks = _int_value(entity_counts.get("table_block_count"))
    if validator_count is None:
        return CompatibilityCheck(
            "table_count_interpretation",
            "review",
            "AviationRAG table count is unavailable.",
            {"interpretation": "unknown"},
        )
    if table_entities is None or table_blocks is None:
        interpretation = "unknown"
        status = "review"
    elif validator_count == table_entities == table_blocks:
        interpretation = "table_entities_and_blocks_equal"
        status = "pass"
    elif validator_count == table_entities:
        interpretation = "table_entities_only"
        status = "pass"
    elif validator_count == table_blocks:
        interpretation = "table_blocks_only"
        status = "review"
    elif validator_count == table_entities + table_blocks:
        interpretation = "aggregate_entities_and_blocks"
        status = "pass"
    else:
        interpretation = "unknown"
        status = "review"
    return CompatibilityCheck(
        "table_count_interpretation",
        status,
        "AviationRAG table count interpretation is documented.",
        {
            "aviationrag_table_count": validator_count,
            "table_entity_count": table_entities,
            "table_block_count": table_blocks,
            "interpretation": interpretation,
        },
    )


def _cross_reference_check(
    data: Mapping[str, Any],
) -> tuple[dict[str, int], CompatibilityCheck]:
    references = _list_value(data.get("cross_references"))
    target_ids = _local_target_ids(data)
    counts: Counter[str] = Counter()
    invalid: list[str] = []
    for index, reference in enumerate(references):
        if not isinstance(reference, Mapping):
            invalid.append(f"$.cross_references[{index}]")
            continue
        status = _optional_str(reference.get("resolution_status")) or "missing"
        counts[status] += 1
        target_id = _optional_str(reference.get("target_id"))
        path = f"$.cross_references[{index}]"
        invalid_status = status not in _ALLOWED_REFERENCE_STATUSES
        invalid_resolved_target = status == "resolved" and target_id not in target_ids
        invalid_unresolved_target = (
            status in {"unresolved", "ambiguous"} and target_id is not None
        )
        if invalid_status or invalid_resolved_target or invalid_unresolved_target:
            invalid.append(path)
    status = "pass" if not invalid else "fail"
    return (
        dict(sorted(counts.items())),
        CompatibilityCheck(
            "cross_reference_integrity",
            status,
            "Cross-reference statuses and local targets are consistent."
            if status == "pass"
            else "Cross-reference statuses or local target claims are inconsistent.",
            {"invalid_paths": invalid},
        ),
    )


def _confidence_check(data: Mapping[str, Any]) -> tuple[list[str], CompatibilityCheck]:
    findings: list[tuple[str, str, Any]] = []
    _collect_confidence_fields(data, "$", findings)
    invalid: list[str] = []
    generic: list[str] = []
    valid_paths: list[str] = []
    for path, field_name, value in findings:
        valid_paths.append(path)
        if field_name == _GENERIC_CONFIDENCE_FIELD:
            generic.append(path)
        invalid_value = (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not 0 <= value <= 1
        )
        if invalid_value:
            invalid.append(path)
    if invalid:
        status = "fail"
        message = "Confidence fields must be numeric values between 0 and 1."
    elif generic:
        status = "review"
        message = "Generic confidence fields are valid but require review."
    else:
        status = "pass"
        message = "Confidence fields are absent or use known bounded numeric names."
    return (
        sorted(valid_paths),
        CompatibilityCheck(
            "confidence_policy",
            status,
            message,
            {"field_paths": sorted(valid_paths), "invalid_paths": sorted(invalid)},
        ),
    )


def _determinism_check(
    *,
    artifact: Path,
    comparison: Path | None,
    determinism_checked: bool,
) -> CompatibilityCheck:
    if not determinism_checked or comparison is None:
        return CompatibilityCheck(
            "determinism",
            "review",
            "Comparison artifact was not supplied; determinism was not checked.",
        )
    matches = artifact.read_bytes() == comparison.read_bytes()
    return CompatibilityCheck(
        "determinism",
        "pass" if matches else "fail",
        "Structured-document bytes match the comparison artifact."
        if matches
        else "Structured-document bytes differ from the comparison artifact.",
        {
            "artifact_sha256": _compute_file_sha256(artifact),
            "comparison_artifact_sha256": _compute_file_sha256(comparison),
        },
    )


def _aggregate_outcome(checks: Iterable[CompatibilityCheck]) -> str:
    statuses = [check.status for check in checks]
    if "fail" in statuses:
        return "FAIL"
    if "review" in statuses:
        return "REVIEW"
    return "PASS"


def _summary(outcome: str, checks: Iterable[CompatibilityCheck]) -> str:
    counts = Counter(check.status for check in checks)
    return (
        f"{outcome}: {counts.get('pass', 0)} pass, "
        f"{counts.get('review', 0)} review, {counts.get('fail', 0)} fail."
    )


def _mapping_value(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _list_value(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _issue_dict(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("AviationRAG report issues must contain objects.")
    return {str(key): item for key, item in value.items()}


def _valid_sha256(value: str) -> bool:
    return _SHA256_RE.fullmatch(value) is not None


def _compute_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_path_candidates(value: str | None, manifest_path: Path) -> set[Path]:
    if value is None:
        return set()
    path = Path(value)
    candidates = {path.resolve(strict=False)}
    if not path.is_absolute():
        candidates.add((manifest_path.parent / path).resolve(strict=False))
    return candidates


def _block_type_count(blocks: list[Any], block_types: set[str]) -> int:
    return sum(
        1
        for block in blocks
        if isinstance(block, Mapping) and block.get("block_type") in block_types
    )


def _int_value(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _local_target_ids(data: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for collection, key in (
        ("sections", "section_id"),
        ("blocks", "block_id"),
        ("tables", "table_id"),
        ("figures", "figure_id"),
        ("equations", "equation_id"),
        ("admonitions", "admonition_id"),
    ):
        for item in _list_value(data.get(collection)):
            if isinstance(item, Mapping):
                value = _optional_str(item.get(key))
                if value is not None:
                    ids.add(value)
    return ids


def _collect_confidence_fields(
    value: object,
    path: str,
    findings: list[tuple[str, str, Any]],
) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}"
            if (
                key_text in _KNOWN_CONFIDENCE_FIELDS
                or key_text == _GENERIC_CONFIDENCE_FIELD
            ):
                findings.append((child_path, key_text, item))
            _collect_confidence_fields(item, child_path, findings)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _collect_confidence_fields(item, f"{path}[{index}]", findings)


def _detect_git_commit(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--oneline"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def _validate_report_output_path(path: Path, *, overwrite: bool) -> None:
    if path.exists() and path.is_dir():
        raise IsADirectoryError(f"Compatibility report output is a directory: {path}")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Compatibility report already exists: {path}")


__all__ = [
    "AviationRAGCompatibilityGateResult",
    "AviationRAGValidatorResult",
    "CompatibilityCheck",
    "aviationrag_compatibility_gate_result_to_dict",
    "aviationrag_compatibility_gate_result_to_json",
    "run_aviationrag_compatibility_gate",
    "run_aviationrag_validator",
    "write_aviationrag_compatibility_report",
]
