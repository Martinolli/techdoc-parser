"""Tests for the offline AviationRAG compatibility gate."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from techdoc_parser.compatibility import (
    AviationRAGValidatorResult,
    aviationrag_compatibility_gate_result_to_dict,
    run_aviationrag_compatibility_gate,
    run_aviationrag_validator,
    write_aviationrag_compatibility_report,
)

FIXTURES = Path(__file__).parent / "fixtures" / "compatibility"
TOOL = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "compatibility"
    / "run-aviationrag-compatibility-gate.py"
)


def test_gate_passes_clean_artifact_manifest_validator_and_comparison(
    tmp_path: Path,
) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    comparison = tmp_path / "comparison.json"
    comparison.write_bytes(artifact.read_bytes())

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=comparison,
        validator_runner=_runner("aviationrag_validator_pass.json"),
        aviationrag_commit="37c8d6d validator",
    )

    assert result.outcome == "PASS"
    assert result.validator_is_valid is True
    assert result.determinism_checked is True
    assert result.determinism_passed is True
    assert result.aviationrag_commit == "37c8d6d validator"
    assert {check.status for check in result.checks} == {"pass"}


def test_missing_comparison_artifact_makes_gate_review(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        validator_runner=_runner("aviationrag_validator_pass.json"),
    )

    assert result.outcome == "REVIEW"
    assert _check(result, "determinism").status == "review"
    assert result.determinism_checked is False
    assert result.determinism_passed is None


def test_different_comparison_artifact_fails_determinism(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    comparison = tmp_path / "comparison.json"
    comparison.write_text("{}", encoding="utf-8")

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=comparison,
        validator_runner=_runner("aviationrag_validator_pass.json"),
    )

    assert result.outcome == "FAIL"
    assert _check(result, "determinism").status == "fail"


def test_validator_errors_fail_gate(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    comparison = tmp_path / "comparison.json"
    comparison.write_bytes(artifact.read_bytes())

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=comparison,
        validator_runner=_runner("aviationrag_validator_fail.json"),
    )

    assert result.outcome == "FAIL"
    assert _check(result, "aviationrag_validator").status == "fail"


def test_unapproved_validator_warning_fails_gate(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    comparison = tmp_path / "comparison.json"
    comparison.write_bytes(artifact.read_bytes())

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=comparison,
        validator_runner=_runner("aviationrag_validator_warning.json"),
    )

    assert result.outcome == "FAIL"
    assert result.unapproved_warning_codes == ["TABLE_STRUCTURE_CANDIDATE"]


def test_approved_validator_warning_returns_review(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    comparison = tmp_path / "comparison.json"
    comparison.write_bytes(artifact.read_bytes())

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=comparison,
        approved_warning_codes=["TABLE_STRUCTURE_CANDIDATE"],
        validator_runner=_runner("aviationrag_validator_warning.json"),
    )

    assert result.outcome == "REVIEW"
    assert _check(result, "validator_warning_policy").status == "review"


@pytest.mark.parametrize(
    ("mutator", "check_name"),
    [
        (
            lambda data: data["document"].update({"source_hash": "0" * 64}),
            "source_checksum",
        ),
        (
            lambda data: data.update({"parser_name": "other-parser"}),
            "metadata_consistency",
        ),
        (
            lambda data: data["document"].update({"source_filename": "other.pdf"}),
            "metadata_consistency",
        ),
    ],
)
def test_artifact_metadata_mismatches_fail_gate(
    tmp_path: Path,
    mutator: object,
    check_name: str,
) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(
        tmp_path,
        artifact_mutator=mutator,
    )
    _refresh_manifest_artifact_checksum(artifact, manifest)
    comparison = tmp_path / "comparison.json"
    comparison.write_bytes(artifact.read_bytes())

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=comparison,
        validator_runner=_runner("aviationrag_validator_pass.json"),
    )

    assert result.outcome == "FAIL"
    assert _check(result, check_name).status == "fail"


def test_manifest_artifact_checksum_mismatch_fails_gate(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["artifacts"][0]["artifact_sha256"] = "0" * 64
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    comparison = tmp_path / "comparison.json"
    comparison.write_bytes(artifact.read_bytes())

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=comparison,
        validator_runner=_runner("aviationrag_validator_pass.json"),
    )

    assert result.outcome == "FAIL"
    assert _check(result, "artifact_checksum").status == "fail"


def test_manifest_without_structured_artifact_fails_gate(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    manifest.write_text('{"artifacts": []}', encoding="utf-8")

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=artifact,
        validator_runner=_runner("aviationrag_validator_pass.json"),
    )

    assert result.outcome == "FAIL"
    assert _check(result, "manifest_artifact_registration").status == "fail"


def test_relative_manifest_artifact_path_is_supported(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["artifacts"][0]["path"] = artifact.name
    data["outputs"]["structured_document"] = artifact.name
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=artifact,
        validator_runner=_runner("aviationrag_validator_pass.json"),
    )

    assert _check(result, "manifest_artifact_registration").status == "pass"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda data: data["cross_references"][0].update({"target_id": "missing"}),
        lambda data: data["cross_references"][0].update(
            {"resolution_status": "made_up"}
        ),
        lambda data: data["cross_references"][0].update(
            {"resolution_status": "unresolved", "target_id": "compat-doc:s0001"}
        ),
    ],
)
def test_cross_reference_integrity_failures_are_caught(
    tmp_path: Path,
    mutator: object,
) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(
        tmp_path,
        artifact_mutator=mutator,
    )
    _refresh_manifest_artifact_checksum(artifact, manifest)

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=artifact,
        validator_runner=_runner("aviationrag_validator_pass.json"),
    )

    assert result.outcome == "FAIL"
    assert _check(result, "cross_reference_integrity").status == "fail"


def test_external_cross_reference_without_local_target_passes(tmp_path: Path) -> None:
    def make_external(data: dict[str, object]) -> None:
        references = data["cross_references"]
        assert isinstance(references, list)
        references[0] = {
            "reference_id": "compat-doc:r0001",
            "raw_text": "See SYN-STD-004.",
            "reference_type": "external_document",
            "resolution_status": "external",
            "target_identifier": "SYN-STD-004",
        }

    source, artifact, manifest = _write_artifact_and_manifest(
        tmp_path,
        artifact_mutator=make_external,
    )
    _refresh_manifest_artifact_checksum(artifact, manifest)

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=artifact,
        validator_runner=_runner("aviationrag_validator_pass.json"),
    )

    assert _check(result, "cross_reference_integrity").status == "pass"


def test_generic_confidence_field_returns_review(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(
        tmp_path,
        artifact_mutator=lambda data: data["blocks"][0].update({"confidence": 0.5}),
    )
    _refresh_manifest_artifact_checksum(artifact, manifest)

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=artifact,
        validator_runner=_runner("aviationrag_validator_pass.json"),
    )

    assert result.outcome == "REVIEW"
    assert result.confidence_field_paths == ["$.blocks[0].confidence"]


def test_invalid_confidence_field_fails_gate(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(
        tmp_path,
        artifact_mutator=lambda data: data["blocks"][0].update(
            {"extraction_confidence": True}
        ),
    )
    _refresh_manifest_artifact_checksum(artifact, manifest)

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=artifact,
        validator_runner=_runner("aviationrag_validator_pass.json"),
    )

    assert result.outcome == "FAIL"
    assert _check(result, "confidence_policy").status == "fail"


def test_table_blocks_only_count_is_review(tmp_path: Path) -> None:
    report = _load_fixture("aviationrag_validator_pass.json")
    report["summary"]["table_count"] = 1

    def remove_table_entity(data: dict[str, object]) -> None:
        data["tables"] = []

    source, artifact, manifest = _write_artifact_and_manifest(
        tmp_path,
        artifact_mutator=remove_table_entity,
    )
    _refresh_manifest_artifact_checksum(artifact, manifest)

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=artifact,
        validator_runner=_runner_from_report(report),
    )

    assert result.outcome == "REVIEW"
    assert result.entity_counts["table_count_interpretation"] == "table_blocks_only"


def test_validator_runner_exception_becomes_failed_gate_check(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)

    def fail_runner(**_: object) -> AviationRAGValidatorResult:
        raise RuntimeError("validator unavailable")

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=artifact,
        validator_runner=fail_runner,
    )

    assert result.outcome == "FAIL"
    assert (
        _check(result, "aviationrag_validator").details["error_type"] == "RuntimeError"
    )


def test_gate_report_omits_raw_validator_stdout_paths(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    validator_result = _validator_result("aviationrag_validator_pass.json")
    validator_result = AviationRAGValidatorResult(
        **{
            **validator_result.__dict__,
            "stdout": f"Report written: {tmp_path / 'private' / 'report.json'}",
        }
    )

    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=artifact,
        validator_runner=_runner_from_result(validator_result),
    )
    report = aviationrag_compatibility_gate_result_to_dict(result)

    assert "private" not in json.dumps(report)


def test_write_report_requires_overwrite_for_existing_file(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    result = run_aviationrag_compatibility_gate(
        artifact_path=artifact,
        manifest_path=manifest,
        source_path=source,
        aviationrag_root=tmp_path,
        comparison_artifact_path=artifact,
        validator_runner=_runner("aviationrag_validator_pass.json"),
    )
    output = tmp_path / "compatibility.json"
    output.write_text("old", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_aviationrag_compatibility_report(result, output)

    write_aviationrag_compatibility_report(result, output, overwrite=True)
    assert json.loads(output.read_text(encoding="utf-8"))["outcome"] == "PASS"


def test_subprocess_adapter_parses_report_and_does_not_write_inside_root(
    tmp_path: Path,
) -> None:
    root = _fake_aviationrag_root(
        tmp_path, _load_fixture("aviationrag_validator_pass.json")
    )
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}", encoding="utf-8")

    result = run_aviationrag_validator(
        artifact_path=artifact,
        aviationrag_root=root,
    )

    assert result.is_valid is True
    assert result.error_count == 0
    assert not (root / "logs").exists()


def test_subprocess_adapter_resolves_relative_artifact_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _fake_aviationrag_root(
        tmp_path,
        _load_fixture("aviationrag_validator_pass.json"),
    )
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = run_aviationrag_validator(
        artifact_path="artifact.json",
        aviationrag_root=root,
    )

    assert result.is_valid is True


def test_subprocess_adapter_rejects_malformed_report(tmp_path: Path) -> None:
    root = _fake_aviationrag_root(tmp_path, {"is_valid": "yes"})
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        run_aviationrag_validator(artifact_path=artifact, aviationrag_root=root)


def test_subprocess_adapter_times_out(tmp_path: Path) -> None:
    root = _fake_aviationrag_root(
        tmp_path,
        _load_fixture("aviationrag_validator_pass.json"),
        sleep_seconds=2,
    )
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}", encoding="utf-8")

    with pytest.raises(TimeoutError):
        run_aviationrag_validator(
            artifact_path=artifact,
            aviationrag_root=root,
            timeout_seconds=0.1,
        )


def test_cli_passes_without_writing_report_by_default(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    root = _fake_aviationrag_root(
        tmp_path, _load_fixture("aviationrag_validator_pass.json")
    )
    report = tmp_path / "compatibility.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--artifact",
            str(artifact),
            "--manifest",
            str(manifest),
            "--source",
            str(source),
            "--aviationrag-root",
            str(root),
            "--comparison-artifact",
            str(artifact),
            "--report",
            str(report),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert not report.exists()
    assert "Report not written" in completed.stdout


def test_cli_writes_report_only_when_allowed(tmp_path: Path) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    root = _fake_aviationrag_root(
        tmp_path, _load_fixture("aviationrag_validator_pass.json")
    )
    report = tmp_path / "compatibility.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--artifact",
            str(artifact),
            "--manifest",
            str(manifest),
            "--source",
            str(source),
            "--aviationrag-root",
            str(root),
            "--comparison-artifact",
            str(artifact),
            "--report",
            str(report),
            "--allow-report-write",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert json.loads(report.read_text(encoding="utf-8"))["outcome"] == "PASS"


def test_cli_returns_review_exit_code_when_determinism_not_checked(
    tmp_path: Path,
) -> None:
    source, artifact, manifest = _write_artifact_and_manifest(tmp_path)
    root = _fake_aviationrag_root(
        tmp_path, _load_fixture("aviationrag_validator_pass.json")
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--artifact",
            str(artifact),
            "--manifest",
            str(manifest),
            "--source",
            str(source),
            "--aviationrag-root",
            str(root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "Outcome: REVIEW" in completed.stdout


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _runner(name: str) -> object:
    return _runner_from_result(_validator_result(name))


def _runner_from_report(report: dict[str, object]) -> object:
    return _runner_from_result(_validator_result_from_mapping(report))


def _runner_from_result(result: AviationRAGValidatorResult) -> object:
    def runner(**_: object) -> AviationRAGValidatorResult:
        return result

    return runner


def _validator_result(name: str) -> AviationRAGValidatorResult:
    return _validator_result_from_mapping(_load_fixture(name))


def _validator_result_from_mapping(
    report: dict[str, object],
) -> AviationRAGValidatorResult:
    return AviationRAGValidatorResult(
        schema_name=report.get("schema_name")
        if isinstance(report.get("schema_name"), str)
        else None,
        schema_version=report.get("schema_version")
        if isinstance(report.get("schema_version"), str)
        else None,
        document_id=report.get("document_id")
        if isinstance(report.get("document_id"), str)
        else None,
        is_valid=bool(report["is_valid"]),
        error_count=int(report["error_count"]),
        warning_count=int(report["warning_count"]),
        issues=list(report["issues"]),
        summary=dict(report["summary"]),
        stdout="validator stdout",
        stderr="",
        return_code=0 if report["error_count"] == 0 else 1,
    )


def _write_artifact_and_manifest(
    tmp_path: Path,
    *,
    artifact_mutator: object | None = None,
) -> tuple[Path, Path, Path]:
    source = tmp_path / "manual.pdf"
    source.write_bytes(b"synthetic source bytes")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    artifact = tmp_path / "structured.json"
    manifest = tmp_path / "manifest.json"
    data = _artifact_data(source_hash)
    if artifact_mutator is not None:
        artifact_mutator(data)
    artifact.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest.write_text(
        json.dumps(_manifest_data(artifact, source_hash, artifact_hash), indent=2)
        + "\n",
        encoding="utf-8",
    )
    return source, artifact, manifest


def _refresh_manifest_artifact_checksum(artifact: Path, manifest: Path) -> None:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["artifacts"][0]["artifact_sha256"] = hashlib.sha256(
        artifact.read_bytes()
    ).hexdigest()
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _artifact_data(source_hash: str) -> dict[str, object]:
    return {
        "schema_name": "techdoc-structured-document",
        "schema_version": "0.1.0",
        "parser_name": "techdoc-parser",
        "parser_version": "0.1.0",
        "document": {
            "document_id": "compat-doc",
            "source_filename": "manual.pdf",
            "source_hash": source_hash,
            "page_count": 1,
        },
        "pages": [
            {
                "page_id": "page-0001",
                "pdf_page_index": 0,
                "page_number": 1,
                "printed_page_label": None,
            }
        ],
        "sections": [
            {
                "section_id": "compat-doc:s0001",
                "level": 1,
                "title": "Compatibility",
                "path": ["Compatibility"],
            }
        ],
        "blocks": [
            {
                "block_id": "heading-1",
                "block_type": "section_heading",
                "text": "1 Compatibility",
                "document_block_index": 0,
                "page_block_index": 0,
                "page_id": "page-0001",
                "page_number": 1,
                "pdf_page_index": 0,
                "section_id": "compat-doc:s0001",
            },
            {
                "block_id": "table-1",
                "block_type": "table",
                "text": "Table 1 Compatibility Matrix",
                "document_block_index": 1,
                "page_block_index": 1,
                "page_id": "page-0001",
                "page_number": 1,
                "pdf_page_index": 0,
                "section_id": "compat-doc:s0001",
            },
        ],
        "tables": [
            {
                "table_id": "compat-doc:p0:t0001",
                "page_start": 1,
                "page_end": 1,
                "pdf_page_index_start": 0,
                "pdf_page_index_end": 0,
                "source_block_ids": ["table-1"],
                "page_id": "page-0001",
                "page_number": 1,
                "pdf_page_index": 0,
                "section_id": "compat-doc:s0001",
                "columns": [],
                "rows": [],
                "cells": [],
                "header_rows": [],
                "merged_cells": [],
                "is_candidate": True,
                "extraction_status": "candidate",
            }
        ],
        "figures": [],
        "equations": [],
        "admonitions": [],
        "cross_references": [
            {
                "reference_id": "compat-doc:r0001",
                "raw_text": "See Section 1.",
                "reference_type": "section",
                "resolution_status": "resolved",
                "target_identifier": "1",
                "target_id": "compat-doc:s0001",
            }
        ],
    }


def _manifest_data(
    artifact: Path,
    source_hash: str,
    artifact_hash: str,
) -> dict[str, object]:
    return {
        "schema_version": "0.1.0",
        "parser": {"name": "techdoc-parser", "version": "0.1.0"},
        "source": {"path": "manual.pdf", "document_id": "compat-doc"},
        "outputs": {"structured_document": str(artifact)},
        "artifacts": [
            {
                "artifact_type": "structured_document",
                "path": str(artifact),
                "media_type": "application/json",
                "schema_name": "techdoc-structured-document",
                "schema_version": "0.1.0",
                "source_sha256": source_hash,
                "artifact_sha256": artifact_hash,
                "document_id": "compat-doc",
            }
        ],
    }


def _check(result: object, name: str) -> object:
    checks = result.checks
    for check in checks:
        if check.name == name:
            return check
    raise AssertionError(f"Missing check: {name}")


def _fake_aviationrag_root(
    tmp_path: Path,
    report: dict[str, object],
    *,
    sleep_seconds: int = 0,
) -> Path:
    root = tmp_path / "fake-aviationrag"
    tool_dir = root / "tools" / "chunking"
    tool_dir.mkdir(parents=True)
    script = tool_dir / "validate-structured-document.py"
    script.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import argparse, json, os, time",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--input')",
                "parser.add_argument('--report')",
                "parser.add_argument('--allow-report-write', action='store_true')",
                "args = parser.parse_args()",
                "if not os.path.exists(args.input):",
                "    raise SystemExit(7)",
                f"time.sleep({sleep_seconds})",
                f"report = {report!r}",
                "if args.allow_report_write:",
                "    with open(args.report, 'w', encoding='utf-8') as handle:",
                "        json.dump(report, handle)",
                "print('fake validator complete')",
            ]
        ),
        encoding="utf-8",
    )
    return root
