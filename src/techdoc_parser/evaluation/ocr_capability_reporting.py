"""Sanitized reporting for read-only OCR capability inventory."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from techdoc_parser.evaluation.ocr_capability_inventory import (
    INVENTORY_SCHEMA_NAME,
    INVENTORY_SCHEMA_VERSION,
    OcrCapabilityInventoryResult,
    OcrEngineCandidateAssessment,
    OcrExecutableCapability,
    OcrPythonPackageCapability,
    OcrRepositoryCapability,
)


def ocr_capability_inventory_to_sanitized_dict(
    result: OcrCapabilityInventoryResult,
) -> dict[str, Any]:
    """Serialize inventory results without local paths, usernames, or secrets."""
    payload: dict[str, Any] = {
        "inventory_schema_name": INVENTORY_SCHEMA_NAME,
        "inventory_schema_version": INVENTORY_SCHEMA_VERSION,
        "overall_outcome": result.outcome,
        "recommended_next_action": result.recommended_next_action,
        "supported_execution_path_available": result.supported_execution_path_available,
        "inventory_complete": result.inventory_complete,
        "page_rendering_available": result.page_rendering_available,
        "repository_capabilities": [
            _repository_capability_to_dict(capability)
            for capability in result.repository_capabilities
        ],
        "python_packages": [
            _python_package_to_dict(package) for package in result.python_packages
        ],
        "executables": [
            _executable_to_dict(executable) for executable in result.executables
        ],
        "engine_candidates": [
            _engine_candidate_to_dict(candidate)
            for candidate in result.engine_candidates
        ],
        "blocking_gap_codes": list(result.blocking_gap_codes),
        "summary": _sanitize_value(result.summary),
        "safety": {
            "ocr_recognition_executed": False,
            "software_installed": False,
            "packages_downloaded": False,
            "source_document_processed": False,
            "aviationrag_changed": False,
            "absolute_paths_included": False,
            "sensitive_environment_included": False,
        },
    }
    _reject_unsafe_payload(payload)
    return payload


def write_ocr_capability_inventory_report(
    result: OcrCapabilityInventoryResult,
    *,
    json_path: str | Path,
    markdown_path: str | Path,
    allow_write: bool = False,
) -> None:
    """Write deterministic sanitized reports only with explicit permission."""
    if not allow_write:
        raise PermissionError(
            "OCR capability inventory report writing requires allow_write=True."
        )
    payload = ocr_capability_inventory_to_sanitized_dict(result)
    json_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    markdown_text = ocr_capability_inventory_to_markdown(result)
    _reject_unsafe_text(json_text)
    _reject_unsafe_text(markdown_text)
    _write_text(Path(json_path), json_text)
    _write_text(Path(markdown_path), markdown_text)


def ocr_capability_inventory_to_json(result: OcrCapabilityInventoryResult) -> str:
    """Return deterministic sanitized JSON."""
    return (
        json.dumps(
            ocr_capability_inventory_to_sanitized_dict(result),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def ocr_capability_inventory_to_markdown(
    result: OcrCapabilityInventoryResult,
) -> str:
    """Return deterministic sanitized Markdown."""
    payload = ocr_capability_inventory_to_sanitized_dict(result)
    lines = [
        "# OCR Capability and Environment Inventory",
        "",
        "Read-only OCR capability inventory.",
        "No OCR recognition executed.",
        "No software installed.",
        "No packages downloaded.",
        "No source document processed.",
        "No AviationRAG changes.",
        "",
        "## Summary",
        "",
        f"- Outcome: `{payload['overall_outcome']}`",
        f"- Recommended next action: `{payload['recommended_next_action']}`",
        "- D.7a current blocking code: `NO_SUPPORTED_OCR_EXECUTION_PATH`",
        "",
        "## Repository OCR Capability",
        "",
        "| Capability | Status | Evidence type |",
        "| --- | --- | --- |",
    ]
    for capability in result.repository_capabilities:
        lines.append(
            "| "
            f"{_md(capability.capability_id)} | "
            f"{_md(capability.implementation_status)} | "
            f"{_md(capability.capability_type)} |"
        )
    lines.extend(
        [
            "",
            "## Python Package Inventory",
            "",
            "| Package | Installed | Version | Role | Integrated |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for package in result.python_packages:
        if package.installed or package.capability_role in {
            "OCR engine",
            "OCR wrapper",
            "rendering",
        }:
            lines.append(
                "| "
                f"{_md(package.distribution_name)} | "
                f"{str(package.installed).lower()} | "
                f"{_md(package.version or 'not_installed')} | "
                f"{_md(package.capability_role)} | "
                f"{str(package.repository_integration_present).lower()} |"
            )
    lines.extend(
        [
            "",
            "## Executable Inventory",
            "",
            "| Executable | Available | Version | Role |",
            "| --- | --- | --- | --- |",
        ]
    )
    for executable in result.executables:
        lines.append(
            "| "
            f"{_md(executable.executable_name)} | "
            f"{str(executable.installed).lower()} | "
            f"{_md(executable.version or executable.version_probe_status)} | "
            f"{_md(executable.capability_role)} |"
        )
    lines.extend(
        [
            "",
            "## OCR Engine Candidate Matrix",
            "",
            "| Engine | Available | Adapter | Forced OCR | Selective pages | "
            "Provenance | Manifest | Candidate status |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for candidate in result.engine_candidates:
        lines.append(
            "| "
            f"{_md(candidate.engine_id)} | "
            f"{str(candidate.engine_available).lower()} | "
            f"{str(candidate.repository_adapter_present).lower()} | "
            f"{str(candidate.forced_ocr_supported).lower()} | "
            f"{str(candidate.selective_page_ocr_supported).lower()} | "
            f"{str(candidate.page_provenance_supported).lower()} | "
            f"{str(candidate.manifest_metadata_supported).lower()} | "
            f"{_md(candidate.candidate_status)} |"
        )
    lines.extend(
        [
            "",
            "## Rendering",
            "",
            "- Page rendering available: `"
            f"{str(result.page_rendering_available).lower()}`",
            "- Backends: `" + ", ".join(_rendering_backends(result)) + "`",
            "",
            "## Blocking Gaps",
            "",
        ]
    )
    if result.blocking_gap_codes:
        lines.extend(f"- `{gap}`" for gap in result.blocking_gap_codes)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- OCR language/model presence does not prove Greek-symbol fidelity.",
            "- Local licensing notes are metadata observations, not legal advice.",
            "- D.7a remains blocked unless the outcome is "
            "`EXISTING_SUPPORTED_ENGINE_AVAILABLE`.",
        ]
    )
    text = "\n".join(lines) + "\n"
    _reject_unsafe_text(text)
    return text


def _repository_capability_to_dict(
    capability: OcrRepositoryCapability,
) -> dict[str, Any]:
    return {
        "capability_id": capability.capability_id,
        "capability_type": capability.capability_type,
        "evidence_locations": list(capability.evidence_locations),
        "implementation_status": capability.implementation_status,
        "supported_modes": list(capability.supported_modes),
        "manifest_support": capability.manifest_support,
        "page_provenance_support": capability.page_provenance_support,
        "notes": list(capability.notes),
    }


def _python_package_to_dict(package: OcrPythonPackageCapability) -> dict[str, Any]:
    return {
        "distribution_name": package.distribution_name,
        "module_name": package.module_name,
        "installed": package.installed,
        "version": package.version,
        "module_discoverable": package.module_discoverable,
        "declared_license": package.declared_license,
        "capability_role": package.capability_role,
        "repository_integration_present": package.repository_integration_present,
    }


def _executable_to_dict(executable: OcrExecutableCapability) -> dict[str, Any]:
    return {
        "executable_name": executable.executable_name,
        "installed": executable.installed,
        "version": executable.version,
        "version_probe_status": executable.version_probe_status,
        "capability_role": executable.capability_role,
        "supported_languages": list(executable.supported_languages),
    }


def _engine_candidate_to_dict(
    candidate: OcrEngineCandidateAssessment,
) -> dict[str, Any]:
    return {
        "engine_id": candidate.engine_id,
        "engine_type": candidate.engine_type,
        "engine_available": candidate.engine_available,
        "repository_adapter_present": candidate.repository_adapter_present,
        "supported_by_current_cli": candidate.supported_by_current_cli,
        "forced_ocr_supported": candidate.forced_ocr_supported,
        "selective_page_ocr_supported": candidate.selective_page_ocr_supported,
        "page_provenance_supported": candidate.page_provenance_supported,
        "manifest_metadata_supported": candidate.manifest_metadata_supported,
        "unicode_output_supported": candidate.unicode_output_supported,
        "greek_support_status": candidate.greek_support_status,
        "deterministic_configuration_status": (
            candidate.deterministic_configuration_status
        ),
        "network_required": candidate.network_required,
        "declared_license": candidate.declared_license,
        "candidate_status": candidate.candidate_status,
        "blocking_gap_codes": list(candidate.blocking_gap_codes),
    }


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if re.search(r"secret|token|password", key_text, re.IGNORECASE):
                sanitized[key_text] = "<redacted>"
            else:
                sanitized[key_text] = _sanitize_value(child)
        return sanitized
    if isinstance(value, tuple | list):
        return [_sanitize_value(child) for child in value]
    if isinstance(value, str):
        if re.search(r"secret|token|password", value, re.IGNORECASE):
            return "<redacted>"
        return _sanitize_text(value)
    return value


def _sanitize_text(value: str) -> str:
    sanitized = re.sub(r"[A-Za-z]:\\[^\s`|]+", "<path>", value)
    sanitized = sanitized.replace(str(Path.home()), "<home>")
    return sanitized


def _rendering_backends(result: OcrCapabilityInventoryResult) -> tuple[str, ...]:
    rendering = result.summary.get("rendering")
    if not isinstance(rendering, dict):
        return ()
    backends = rendering.get("rendering_backend_candidates", ())
    if not isinstance(backends, list | tuple):
        return ()
    return tuple(str(backend) for backend in backends)


def _reject_unsafe_payload(payload: Any) -> None:
    _reject_unsafe_text(json.dumps(payload, sort_keys=True))


def _reject_unsafe_text(text: str) -> None:
    patterns = (
        r"[A-Za-z]:\\",
        re.escape(str(Path.home())),
        r"\bPATH\b\s*[:=]",
        r"\b(SECRET|TOKEN|PASSWORD)\b\s*[:=]",
    )
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            raise ValueError("Sanitized OCR capability report contains unsafe text.")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _md(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


__all__ = [
    "ocr_capability_inventory_to_json",
    "ocr_capability_inventory_to_markdown",
    "ocr_capability_inventory_to_sanitized_dict",
    "write_ocr_capability_inventory_report",
]
