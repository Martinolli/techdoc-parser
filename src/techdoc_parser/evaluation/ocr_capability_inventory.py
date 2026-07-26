"""Read-only OCR capability and environment inventory.

This module inventories repository references, Python package metadata, and a
small allowlist of local executables. It does not run OCR recognition, process
source PDFs, install software, download packages, write files, or change parser
behavior.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EXISTING_SUPPORTED_ENGINE_AVAILABLE = "EXISTING_SUPPORTED_ENGINE_AVAILABLE"
ENGINE_INSTALLED_BUT_NOT_INTEGRATED = "ENGINE_INSTALLED_BUT_NOT_INTEGRATED"
NO_ENGINE_INSTALLED = "NO_ENGINE_INSTALLED"
EXISTING_INTEGRATION_INCOMPLETE = "EXISTING_INTEGRATION_INCOMPLETE"
BLOCKED = "BLOCKED"

SUPPORTED_AND_AVAILABLE = "SUPPORTED_AND_AVAILABLE"
AVAILABLE_NOT_INTEGRATED = "AVAILABLE_NOT_INTEGRATED"
INTEGRATION_INCOMPLETE = "INTEGRATION_INCOMPLETE"
NOT_AVAILABLE = "NOT_AVAILABLE"
UNSUPPORTED_FOR_CURRENT_SCOPE = "UNSUPPORTED_FOR_CURRENT_SCOPE"
UNKNOWN = "UNKNOWN"

USE_EXISTING_SUPPORTED_PATH = "USE_EXISTING_SUPPORTED_PATH"
IMPLEMENT_ADAPTER_FOR_INSTALLED_ENGINE = "IMPLEMENT_ADAPTER_FOR_INSTALLED_ENGINE"
REPAIR_EXISTING_INTEGRATION = "REPAIR_EXISTING_INTEGRATION"
REQUEST_ENGINE_INSTALLATION_APPROVAL = "REQUEST_ENGINE_INSTALLATION_APPROVAL"
REQUEST_LANGUAGE_OR_MODEL_APPROVAL = "REQUEST_LANGUAGE_OR_MODEL_APPROVAL"
INVENTORY_BLOCKED = "INVENTORY_BLOCKED"

NO_OCR_ENGINE_AVAILABLE = "NO_OCR_ENGINE_AVAILABLE"
OCR_WRAPPER_WITHOUT_ENGINE = "OCR_WRAPPER_WITHOUT_ENGINE"
OCR_ENGINE_NOT_INTEGRATED = "OCR_ENGINE_NOT_INTEGRATED"
OCR_ADAPTER_INCOMPLETE = "OCR_ADAPTER_INCOMPLETE"
FORCED_OCR_NOT_SUPPORTED = "FORCED_OCR_NOT_SUPPORTED"
SELECTIVE_PAGE_OCR_NOT_SUPPORTED = "SELECTIVE_PAGE_OCR_NOT_SUPPORTED"
OCR_PAGE_PROVENANCE_NOT_RECORDED = "OCR_PAGE_PROVENANCE_NOT_RECORDED"
OCR_ENGINE_VERSION_NOT_RECORDED = "OCR_ENGINE_VERSION_NOT_RECORDED"
OCR_PROCESSED_PAGES_NOT_RECORDED = "OCR_PROCESSED_PAGES_NOT_RECORDED"
OCR_MANIFEST_METADATA_MISSING = "OCR_MANIFEST_METADATA_MISSING"
RAW_OCR_OUTPUT_NOT_PRESERVED = "RAW_OCR_OUTPUT_NOT_PRESERVED"
OCR_NORMALIZATION_NOT_SEPARATED = "OCR_NORMALIZATION_NOT_SEPARATED"
PDF_RENDERING_UNAVAILABLE = "PDF_RENDERING_UNAVAILABLE"
GREEK_LANGUAGE_MODEL_UNAVAILABLE = "GREEK_LANGUAGE_MODEL_UNAVAILABLE"
GREEK_SUPPORT_UNKNOWN = "GREEK_SUPPORT_UNKNOWN"
NETWORK_MODEL_DOWNLOAD_REQUIRED = "NETWORK_MODEL_DOWNLOAD_REQUIRED"
LICENSE_METADATA_UNAVAILABLE = "LICENSE_METADATA_UNAVAILABLE"
DETERMINISTIC_OCR_CONFIGURATION_UNDEFINED = "DETERMINISTIC_OCR_CONFIGURATION_UNDEFINED"

INVENTORY_SCHEMA_NAME = "techdoc-parser-ocr-capability-inventory"
INVENTORY_SCHEMA_VERSION = "0.1"

CONTROLLED_GAP_CODES = (
    NO_OCR_ENGINE_AVAILABLE,
    OCR_WRAPPER_WITHOUT_ENGINE,
    OCR_ENGINE_NOT_INTEGRATED,
    OCR_ADAPTER_INCOMPLETE,
    FORCED_OCR_NOT_SUPPORTED,
    SELECTIVE_PAGE_OCR_NOT_SUPPORTED,
    OCR_PAGE_PROVENANCE_NOT_RECORDED,
    OCR_ENGINE_VERSION_NOT_RECORDED,
    OCR_PROCESSED_PAGES_NOT_RECORDED,
    OCR_MANIFEST_METADATA_MISSING,
    RAW_OCR_OUTPUT_NOT_PRESERVED,
    OCR_NORMALIZATION_NOT_SEPARATED,
    PDF_RENDERING_UNAVAILABLE,
    GREEK_LANGUAGE_MODEL_UNAVAILABLE,
    GREEK_SUPPORT_UNKNOWN,
    NETWORK_MODEL_DOWNLOAD_REQUIRED,
    LICENSE_METADATA_UNAVAILABLE,
    DETERMINISTIC_OCR_CONFIGURATION_UNDEFINED,
)

OCR_SEARCH_TERMS = (
    "ocr",
    "OCR",
    "tesseract",
    "pytesseract",
    "tesserocr",
    "ocrmypdf",
    "easyocr",
    "paddleocr",
    "rapidocr",
    "doctr",
    "keras_ocr",
    "winrt",
    "Windows.Media.Ocr",
    "image_to_string",
    "page_requires_ocr",
    "requires_ocr",
    "force_ocr",
    "ocr_pages",
    "render_page",
    "raster",
)

REPOSITORY_SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "input",
    "output",
}
REPOSITORY_TEXT_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

PYTHON_PACKAGE_SPECS: tuple[tuple[str, str, str], ...] = (
    ("pytesseract", "pytesseract", "OCR wrapper"),
    ("tesserocr", "tesserocr", "OCR wrapper"),
    ("ocrmypdf", "ocrmypdf", "OCR wrapper"),
    ("easyocr", "easyocr", "OCR engine"),
    ("paddleocr", "paddleocr", "OCR engine"),
    ("paddlepaddle", "paddle", "runtime/model dependency"),
    ("rapidocr_onnxruntime", "rapidocr_onnxruntime", "OCR engine"),
    ("onnxruntime", "onnxruntime", "runtime/model dependency"),
    ("python-doctr", "doctr", "OCR engine"),
    ("keras-ocr", "keras_ocr", "OCR engine"),
    ("opencv-python", "cv2", "image preprocessing"),
    ("opencv-python-headless", "cv2", "image preprocessing"),
    ("Pillow", "PIL", "image preprocessing"),
    ("pdf2image", "pdf2image", "rendering"),
    ("pypdfium2", "pypdfium2", "rendering"),
    ("PyMuPDF", "fitz", "rendering"),
    ("pdfplumber", "pdfplumber", "rendering"),
    ("pypdf", "pypdf", "rendering"),
    ("torch", "torch", "runtime/model dependency"),
)

EXECUTABLE_SPECS: Mapping[str, tuple[tuple[str, ...], str]] = {
    "tesseract": (("--version",), "OCR engine"),
    "ocrmypdf": (("--version",), "OCR wrapper"),
    "pdftoppm": (("-v",), "rendering"),
    "pdftotext": (("-v",), "native text extraction"),
    "pdfinfo": (("-v",), "PDF metadata"),
    "mutool": (("-v",), "rendering"),
    "magick": (("-version",), "rendering"),
    "gswin64c": (("-version",), "rendering"),
    "gswin32c": (("-version",), "rendering"),
}

RENDERING_PACKAGE_NAMES = {"PyMuPDF", "pdf2image", "pypdfium2"}
RENDERING_EXECUTABLE_NAMES = {
    "pdftoppm",
    "mutool",
    "magick",
    "gswin64c",
    "gswin32c",
}
OCR_ENGINE_EXECUTABLE_NAMES = {"tesseract", "ocrmypdf"}
OCR_ENGINE_PACKAGE_NAMES = {
    "easyocr",
    "paddleocr",
    "rapidocr_onnxruntime",
    "python-doctr",
    "keras-ocr",
}
OCR_WRAPPER_PACKAGE_NAMES = {"pytesseract", "tesserocr", "ocrmypdf"}


@dataclass(frozen=True)
class OcrRepositoryCapability:
    capability_id: str
    capability_type: str
    evidence_locations: tuple[str, ...]
    implementation_status: str
    supported_modes: tuple[str, ...]
    manifest_support: bool
    page_provenance_support: bool
    notes: tuple[str, ...]


@dataclass(frozen=True)
class OcrPythonPackageCapability:
    distribution_name: str
    module_name: str
    installed: bool
    version: str | None
    module_discoverable: bool
    declared_license: str | None
    capability_role: str
    repository_integration_present: bool


@dataclass(frozen=True)
class OcrExecutableCapability:
    executable_name: str
    installed: bool
    version: str | None
    version_probe_status: str
    capability_role: str
    supported_languages: tuple[str, ...]


@dataclass(frozen=True)
class OcrEngineCandidateAssessment:
    engine_id: str
    engine_type: str
    engine_available: bool
    repository_adapter_present: bool
    supported_by_current_cli: bool
    forced_ocr_supported: bool
    selective_page_ocr_supported: bool
    page_provenance_supported: bool
    manifest_metadata_supported: bool
    unicode_output_supported: str
    greek_support_status: str
    deterministic_configuration_status: str
    network_required: str
    declared_license: str | None
    candidate_status: str
    blocking_gap_codes: tuple[str, ...]


@dataclass(frozen=True)
class OcrCapabilityInventoryResult:
    outcome: str
    repository_capabilities: tuple[OcrRepositoryCapability, ...]
    python_packages: tuple[OcrPythonPackageCapability, ...]
    executables: tuple[OcrExecutableCapability, ...]
    engine_candidates: tuple[OcrEngineCandidateAssessment, ...]
    page_rendering_available: bool
    supported_execution_path_available: bool
    inventory_complete: bool
    blocking_gap_codes: tuple[str, ...]
    recommended_next_action: str
    summary: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProbeCompletedProcess:
    returncode: int
    stdout: str
    stderr: str


CommandResolver = Callable[[str], str | None]
CommandRunner = Callable[[Sequence[str], int], ProbeCompletedProcess]
FindSpec = Callable[[str], object | None]
VersionReader = Callable[[str], str]
MetadataReader = Callable[[str], Mapping[str, str]]


def inventory_ocr_capabilities(
    *,
    repository_root: str | Path,
    python_executable: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> OcrCapabilityInventoryResult:
    """Run the read-only OCR capability inventory."""
    root = Path(repository_root)
    env = os.environ if environment is None else environment
    del python_executable
    try:
        if not root.is_dir():
            raise ValueError("Repository root does not exist or is not a directory.")
        reference_classes = classify_repository_ocr_references(root)
        repository_capabilities = inspect_repository_ocr_capabilities(
            root,
            reference_classes=reference_classes,
        )
        python_packages = inspect_python_package_capabilities(
            repository_capabilities=repository_capabilities
        )
        executables = inspect_executable_capabilities(environment=env)
        engine_candidates = assess_ocr_engine_candidates(
            repository_capabilities=repository_capabilities,
            python_packages=python_packages,
            executables=executables,
        )
        rendering = assess_pdf_rendering_capability(
            python_packages=python_packages,
            executables=executables,
        )
        outcome, recommended, gaps = determine_overall_outcome(
            repository_capabilities=repository_capabilities,
            engine_candidates=engine_candidates,
            page_rendering_available=rendering["page_rendering_available"] is True,
        )
        summary = _build_summary(
            reference_classes=reference_classes,
            python_packages=python_packages,
            executables=executables,
            engine_candidates=engine_candidates,
            rendering=rendering,
        )
        return OcrCapabilityInventoryResult(
            outcome=outcome,
            repository_capabilities=repository_capabilities,
            python_packages=python_packages,
            executables=executables,
            engine_candidates=engine_candidates,
            page_rendering_available=rendering["page_rendering_available"] is True,
            supported_execution_path_available=outcome
            == EXISTING_SUPPORTED_ENGINE_AVAILABLE,
            inventory_complete=True,
            blocking_gap_codes=gaps,
            recommended_next_action=recommended,
            summary=summary,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return OcrCapabilityInventoryResult(
            outcome=BLOCKED,
            repository_capabilities=(),
            python_packages=(),
            executables=(),
            engine_candidates=(),
            page_rendering_available=False,
            supported_execution_path_available=False,
            inventory_complete=False,
            blocking_gap_codes=("INVENTORY_PROBE_FAILED",),
            recommended_next_action=INVENTORY_BLOCKED,
            summary={"error": _sanitize_text(str(exc))},
        )


def classify_repository_ocr_references(
    repository_root: str | Path,
    *,
    file_texts: Mapping[str, str] | None = None,
) -> Mapping[str, tuple[str, ...]]:
    """Classify OCR references by evidence type using repository-local text."""
    texts = (
        dict(file_texts)
        if file_texts is not None
        else _read_repository_text_files(Path(repository_root))
    )
    classes: dict[str, set[str]] = {
        "warning_or_detection_only": set(),
        "declared_integration": set(),
        "implemented_adapter": set(),
        "optional_dependency": set(),
        "test_fixture_only": set(),
        "documentation_only": set(),
        "obsolete_or_unused": set(),
    }
    for raw_path, text in texts.items():
        lowered = text.lower()
        if not _contains_ocr_reference(text):
            continue
        path = raw_path.replace("\\", "/")
        if _is_test_or_fixture_path(path):
            classes["test_fixture_only"].add(path)
        if _is_documentation_path(path):
            classes["documentation_only"].add(path)
        if (
            path.endswith(("pyproject.toml", "requirements.txt"))
            or "requirements" in path
        ):
            classes["optional_dependency"].add(path)
        if (
            "requires_ocr" in lowered
            or "page_requires_ocr" in lowered
            or "ocr-required" in lowered
            or "need ocr" in lowered
            or "requires ocr" in lowered
        ):
            classes["warning_or_detection_only"].add(path)
        if (
            "detect_supported_ocr_capability" in lowered
            or "ocr_text_artifact" in lowered
            or "get_textpage_ocr" in lowered
        ):
            classes["declared_integration"].add(path)
        if _looks_like_adapter(text):
            classes["implemented_adapter"].add(path)
        if "obsolete" in lowered or "unused" in lowered:
            classes["obsolete_or_unused"].add(path)
    return {
        key: tuple(sorted(values)) for key, values in sorted(classes.items()) if values
    }


def inspect_repository_ocr_capabilities(
    repository_root: str | Path,
    *,
    reference_classes: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[OcrRepositoryCapability, ...]:
    """Summarize repository OCR capabilities without treating warnings as OCR."""
    classes = (
        classify_repository_ocr_references(repository_root)
        if reference_classes is None
        else reference_classes
    )
    capabilities: list[OcrRepositoryCapability] = []
    detection_locations = classes.get("warning_or_detection_only", ())
    if detection_locations:
        capabilities.append(
            OcrRepositoryCapability(
                capability_id="ocr_need_detection",
                capability_type="warning_or_detection_only",
                evidence_locations=detection_locations,
                implementation_status="detection_only",
                supported_modes=("native_text_presence_detection",),
                manifest_support=False,
                page_provenance_support=False,
                notes=(
                    "Repository can flag OCR-required pages.",
                    "Detection does not produce OCR text.",
                ),
            )
        )
    declared_locations = tuple(
        location
        for location in classes.get("declared_integration", ())
        if "ocr_capability_inventory" not in location
        and "OCR_CAPABILITY_AND_ENVIRONMENT_INVENTORY" not in location
    )
    if declared_locations:
        capabilities.append(
            OcrRepositoryCapability(
                capability_id="engineering_ocr_fidelity_evaluator",
                capability_type="declared_integration",
                evidence_locations=declared_locations,
                implementation_status="partial",
                supported_modes=("supplied_native_ocr_artifact_comparison",),
                manifest_support=False,
                page_provenance_support=True,
                notes=(
                    "D.7a can compare supplied OCR artifacts.",
                    "D.7a does not run OCR or expose a parser OCR runner.",
                ),
            )
        )
    adapter_locations = tuple(
        location
        for location in classes.get("implemented_adapter", ())
        if "ocr_capability_inventory" not in location
        and "run-ocr-capability-inventory" not in location
    )
    explicit_controlled_adapter = any(
        location.startswith("src/techdoc_parser/ocr/")
        or location == "tools/ocr/run-controlled-tesseract-ocr.py"
        for location in adapter_locations
    )
    capabilities.append(
        OcrRepositoryCapability(
            capability_id="parser_ocr_execution_adapter",
            capability_type="implemented_adapter",
            evidence_locations=adapter_locations,
            implementation_status="implemented" if adapter_locations else "absent",
            supported_modes=(
                (
                    "ocr_all_pages",
                    "ocr_selected_pages",
                )
                if explicit_controlled_adapter
                else ("ocr_execution",)
                if adapter_locations
                else ()
            ),
            manifest_support=explicit_controlled_adapter,
            page_provenance_support=explicit_controlled_adapter,
            notes=(
                (
                    "No production parser OCR execution adapter was found."
                    if not adapter_locations
                    else (
                        "Explicit controlled OCR adapter references were found."
                        if explicit_controlled_adapter
                        else "Production OCR execution adapter references were found."
                    )
                ),
            ),
        )
    )
    if not capabilities:
        capabilities.append(
            OcrRepositoryCapability(
                capability_id="repository_ocr_references",
                capability_type="absent",
                evidence_locations=(),
                implementation_status="absent",
                supported_modes=(),
                manifest_support=False,
                page_provenance_support=False,
                notes=("No OCR references found.",),
            )
        )
    return tuple(sorted(capabilities, key=lambda item: item.capability_id))


def inspect_python_package_capabilities(
    *,
    repository_capabilities: Sequence[OcrRepositoryCapability] = (),
    package_specs: Sequence[tuple[str, str, str]] = PYTHON_PACKAGE_SPECS,
    find_spec: FindSpec | None = None,
    version_reader: VersionReader | None = None,
    metadata_reader: MetadataReader | None = None,
) -> tuple[OcrPythonPackageCapability, ...]:
    """Inspect Python package metadata without importing candidate libraries."""
    spec_reader = importlib.util.find_spec if find_spec is None else find_spec
    version_lookup = _metadata_version if version_reader is None else version_reader
    metadata_lookup = _metadata_mapping if metadata_reader is None else metadata_reader
    integrated_names = _repository_integration_names(repository_capabilities)
    packages: list[OcrPythonPackageCapability] = []
    for distribution_name, module_name, role in sorted(package_specs):
        version: str | None = None
        installed = False
        try:
            version = version_lookup(distribution_name)
            installed = True
        except importlib.metadata.PackageNotFoundError:
            installed = False
        metadata: Mapping[str, str] = {}
        if installed:
            try:
                metadata = metadata_lookup(distribution_name)
            except importlib.metadata.PackageNotFoundError:
                metadata = {}
        packages.append(
            OcrPythonPackageCapability(
                distribution_name=distribution_name,
                module_name=module_name,
                installed=installed,
                version=version,
                module_discoverable=spec_reader(module_name) is not None,
                declared_license=_metadata_license(metadata),
                capability_role=role,
                repository_integration_present=distribution_name.lower()
                in integrated_names
                or module_name.lower() in integrated_names,
            )
        )
    return tuple(packages)


def inspect_executable_capabilities(
    *,
    executable_specs: Mapping[str, tuple[tuple[str, ...], str]] = EXECUTABLE_SPECS,
    command_resolver: CommandResolver | None = None,
    command_runner: CommandRunner | None = None,
    timeout_seconds: int = 5,
    environment: Mapping[str, str] | None = None,
) -> tuple[OcrExecutableCapability, ...]:
    """Probe the executable allowlist with version and language commands only."""
    del environment
    resolver = _resolve_command if command_resolver is None else command_resolver
    runner = _run_probe if command_runner is None else command_runner
    executables: list[OcrExecutableCapability] = []
    for name in sorted(executable_specs):
        if name not in EXECUTABLE_SPECS:
            raise ValueError(f"Executable is not allowlisted: {name}")
        version_args, role = executable_specs[name]
        resolved = resolver(name)
        if resolved is None:
            executables.append(
                OcrExecutableCapability(
                    executable_name=name,
                    installed=False,
                    version=None,
                    version_probe_status="not_found",
                    capability_role=role,
                    supported_languages=(),
                )
            )
            continue
        version, status = _probe_executable_version(
            name=name,
            args=version_args,
            runner=runner,
            timeout_seconds=timeout_seconds,
        )
        languages = (
            _probe_tesseract_languages(runner=runner, timeout_seconds=timeout_seconds)
            if name == "tesseract"
            else ()
        )
        executables.append(
            OcrExecutableCapability(
                executable_name=name,
                installed=True,
                version=version,
                version_probe_status=status,
                capability_role=role,
                supported_languages=languages,
            )
        )
    return tuple(executables)


def assess_pdf_rendering_capability(
    *,
    python_packages: Sequence[OcrPythonPackageCapability],
    executables: Sequence[OcrExecutableCapability],
) -> Mapping[str, object]:
    """Assess deterministic local page-rendering support without rendering pages."""
    package_backends = tuple(
        package.distribution_name
        for package in python_packages
        if package.installed and package.distribution_name in RENDERING_PACKAGE_NAMES
    )
    executable_backends = tuple(
        executable.executable_name
        for executable in executables
        if executable.installed
        and executable.executable_name in RENDERING_EXECUTABLE_NAMES
    )
    backends = tuple(sorted((*package_backends, *executable_backends)))
    available = bool(backends)
    deterministic = bool(
        set(backends) & {"PyMuPDF", "pypdfium2", "pdf2image", "pdftoppm", "mutool"}
    )
    return {
        "page_rendering_available": available,
        "rendering_backend_candidates": backends,
        "deterministic_dpi_control_available": deterministic,
        "page_range_control_available": deterministic,
        "PNG_output_available": available,
    }


def assess_ocr_engine_candidates(
    *,
    repository_capabilities: Sequence[OcrRepositoryCapability],
    python_packages: Sequence[OcrPythonPackageCapability],
    executables: Sequence[OcrExecutableCapability],
) -> tuple[OcrEngineCandidateAssessment, ...]:
    """Evaluate candidate OCR engines against D.7a execution requirements."""
    adapter_present = any(
        capability.capability_id == "parser_ocr_execution_adapter"
        and capability.implementation_status == "implemented"
        for capability in repository_capabilities
    )
    manifest_present = any(
        capability.manifest_support for capability in repository_capabilities
    )
    page_provenance_present = any(
        capability.page_provenance_support
        and capability.capability_id == "parser_ocr_execution_adapter"
        for capability in repository_capabilities
    )
    executable_by_name = {item.executable_name: item for item in executables}
    package_by_name = {item.distribution_name: item for item in python_packages}
    candidates: list[OcrEngineCandidateAssessment] = []
    tesseract = executable_by_name.get("tesseract")
    pytesseract = package_by_name.get("pytesseract")
    if tesseract is not None or (pytesseract is not None and pytesseract.installed):
        candidates.append(
            _assess_tesseract_candidate(
                tesseract=tesseract,
                wrapper=pytesseract,
                adapter_present=adapter_present,
                manifest_present=manifest_present,
                page_provenance_present=page_provenance_present,
            )
        )
    ocrmypdf_exec = executable_by_name.get("ocrmypdf")
    ocrmypdf_pkg = package_by_name.get("ocrmypdf")
    if (
        ocrmypdf_exec is not None
        and ocrmypdf_exec.installed
        or ocrmypdf_pkg is not None
        and ocrmypdf_pkg.installed
    ):
        candidates.append(
            _assess_generic_candidate(
                engine_id="ocrmypdf",
                engine_type="OCR wrapper",
                engine_available=bool(ocrmypdf_exec and ocrmypdf_exec.installed),
                repository_adapter_present=adapter_present,
                manifest_metadata_supported=manifest_present,
                page_provenance_supported=page_provenance_present,
                version_recordable=bool(
                    ocrmypdf_exec and ocrmypdf_exec.installed and ocrmypdf_exec.version
                ),
                license_value=(
                    ocrmypdf_pkg.declared_license if ocrmypdf_pkg is not None else None
                ),
                network_required="no",
                greek_support_status="unknown",
            )
        )
    for package_name in sorted(OCR_ENGINE_PACKAGE_NAMES):
        package = package_by_name.get(package_name)
        if package is None or not package.installed:
            continue
        candidates.append(
            _assess_generic_candidate(
                engine_id=package_name,
                engine_type=package.capability_role,
                engine_available=True,
                repository_adapter_present=adapter_present,
                manifest_metadata_supported=manifest_present,
                page_provenance_supported=page_provenance_present,
                version_recordable=package.version is not None,
                license_value=package.declared_license,
                network_required="unknown",
                greek_support_status="unknown",
            )
        )
    if not candidates:
        candidates.append(
            OcrEngineCandidateAssessment(
                engine_id="none",
                engine_type="none",
                engine_available=False,
                repository_adapter_present=adapter_present,
                supported_by_current_cli=False,
                forced_ocr_supported=False,
                selective_page_ocr_supported=False,
                page_provenance_supported=False,
                manifest_metadata_supported=False,
                unicode_output_supported="unknown",
                greek_support_status="unknown",
                deterministic_configuration_status="unknown",
                network_required="unknown",
                declared_license=None,
                candidate_status=NOT_AVAILABLE,
                blocking_gap_codes=(NO_OCR_ENGINE_AVAILABLE,),
            )
        )
    return tuple(sorted(candidates, key=lambda item: item.engine_id))


def determine_overall_outcome(
    *,
    repository_capabilities: Sequence[OcrRepositoryCapability],
    engine_candidates: Sequence[OcrEngineCandidateAssessment],
    page_rendering_available: bool,
) -> tuple[str, str, tuple[str, ...]]:
    """Reduce candidate assessments to a controlled D.7b-1 outcome."""
    gaps: set[str] = set()
    for candidate in engine_candidates:
        gaps.update(candidate.blocking_gap_codes)
    if not page_rendering_available:
        gaps.add(PDF_RENDERING_UNAVAILABLE)
    if any(
        candidate.candidate_status == SUPPORTED_AND_AVAILABLE
        for candidate in engine_candidates
    ):
        return (
            EXISTING_SUPPORTED_ENGINE_AVAILABLE,
            USE_EXISTING_SUPPORTED_PATH,
            _sort_gap_codes(gaps),
        )
    adapter_present = any(
        capability.capability_id == "parser_ocr_execution_adapter"
        and capability.implementation_status == "implemented"
        for capability in repository_capabilities
    )
    if adapter_present:
        return (
            EXISTING_INTEGRATION_INCOMPLETE,
            REPAIR_EXISTING_INTEGRATION,
            _sort_gap_codes(gaps | {OCR_ADAPTER_INCOMPLETE}),
        )
    if any(candidate.engine_available for candidate in engine_candidates):
        return (
            ENGINE_INSTALLED_BUT_NOT_INTEGRATED,
            IMPLEMENT_ADAPTER_FOR_INSTALLED_ENGINE,
            _sort_gap_codes(gaps | {OCR_ENGINE_NOT_INTEGRATED}),
        )
    if any(
        OCR_WRAPPER_WITHOUT_ENGINE in candidate.blocking_gap_codes
        for candidate in engine_candidates
    ):
        return (
            EXISTING_INTEGRATION_INCOMPLETE,
            REPAIR_EXISTING_INTEGRATION,
            _sort_gap_codes(gaps),
        )
    return (
        NO_ENGINE_INSTALLED,
        REQUEST_ENGINE_INSTALLATION_APPROVAL,
        _sort_gap_codes(gaps | {NO_OCR_ENGINE_AVAILABLE}),
    )


def _assess_tesseract_candidate(
    *,
    tesseract: OcrExecutableCapability | None,
    wrapper: OcrPythonPackageCapability | None,
    adapter_present: bool,
    manifest_present: bool,
    page_provenance_present: bool,
) -> OcrEngineCandidateAssessment:
    engine_available = bool(tesseract and tesseract.installed)
    languages = set(tesseract.supported_languages if tesseract is not None else ())
    gaps = _common_candidate_gaps(
        engine_available=engine_available,
        adapter_present=adapter_present,
        manifest_present=manifest_present,
        page_provenance_present=page_provenance_present,
        version_recordable=bool(tesseract and tesseract.version),
    )
    if wrapper is not None and wrapper.installed and not engine_available:
        gaps.add(OCR_WRAPPER_WITHOUT_ENGINE)
    if engine_available and "ell" not in languages:
        gaps.add(GREEK_LANGUAGE_MODEL_UNAVAILABLE)
    if engine_available and not languages:
        gaps.add(GREEK_SUPPORT_UNKNOWN)
    candidate_status = _candidate_status(
        engine_available=engine_available,
        adapter_present=adapter_present,
        manifest_present=manifest_present,
        page_provenance_present=page_provenance_present,
        gaps=gaps - {GREEK_LANGUAGE_MODEL_UNAVAILABLE},
    )
    return OcrEngineCandidateAssessment(
        engine_id="tesseract",
        engine_type="OCR engine",
        engine_available=engine_available,
        repository_adapter_present=adapter_present,
        supported_by_current_cli=candidate_status == SUPPORTED_AND_AVAILABLE,
        forced_ocr_supported=False,
        selective_page_ocr_supported=False,
        page_provenance_supported=page_provenance_present,
        manifest_metadata_supported=manifest_present,
        unicode_output_supported="yes" if engine_available else "unknown",
        greek_support_status=(
            "yes"
            if "ell" in languages
            else "no"
            if engine_available and languages
            else "unknown"
        ),
        deterministic_configuration_status=(
            "partial" if engine_available else "unknown"
        ),
        network_required="no" if engine_available else "unknown",
        declared_license=wrapper.declared_license if wrapper is not None else None,
        candidate_status=candidate_status,
        blocking_gap_codes=_sort_gap_codes(gaps),
    )


def _assess_generic_candidate(
    *,
    engine_id: str,
    engine_type: str,
    engine_available: bool,
    repository_adapter_present: bool,
    manifest_metadata_supported: bool,
    page_provenance_supported: bool,
    version_recordable: bool,
    license_value: str | None,
    network_required: str,
    greek_support_status: str,
) -> OcrEngineCandidateAssessment:
    gaps = _common_candidate_gaps(
        engine_available=engine_available,
        adapter_present=repository_adapter_present,
        manifest_present=manifest_metadata_supported,
        page_provenance_present=page_provenance_supported,
        version_recordable=version_recordable,
    )
    if network_required == "yes":
        gaps.add(NETWORK_MODEL_DOWNLOAD_REQUIRED)
    if greek_support_status == "unknown":
        gaps.add(GREEK_SUPPORT_UNKNOWN)
    return OcrEngineCandidateAssessment(
        engine_id=engine_id,
        engine_type=engine_type,
        engine_available=engine_available,
        repository_adapter_present=repository_adapter_present,
        supported_by_current_cli=False,
        forced_ocr_supported=False,
        selective_page_ocr_supported=False,
        page_provenance_supported=page_provenance_supported,
        manifest_metadata_supported=manifest_metadata_supported,
        unicode_output_supported="unknown",
        greek_support_status=greek_support_status,
        deterministic_configuration_status="unknown",
        network_required=network_required,
        declared_license=license_value,
        candidate_status=_candidate_status(
            engine_available=engine_available,
            adapter_present=repository_adapter_present,
            manifest_present=manifest_metadata_supported,
            page_provenance_present=page_provenance_supported,
            gaps=gaps,
        ),
        blocking_gap_codes=_sort_gap_codes(gaps),
    )


def _common_candidate_gaps(
    *,
    engine_available: bool,
    adapter_present: bool,
    manifest_present: bool,
    page_provenance_present: bool,
    version_recordable: bool,
) -> set[str]:
    gaps: set[str] = set()
    if not engine_available:
        gaps.add(NO_OCR_ENGINE_AVAILABLE)
    if not adapter_present:
        gaps.add(OCR_ENGINE_NOT_INTEGRATED)
    if not version_recordable:
        gaps.add(OCR_ENGINE_VERSION_NOT_RECORDED)
    if not manifest_present:
        gaps.add(OCR_MANIFEST_METADATA_MISSING)
    if not page_provenance_present:
        gaps.add(OCR_PAGE_PROVENANCE_NOT_RECORDED)
    if not adapter_present:
        gaps.update(
            {
                FORCED_OCR_NOT_SUPPORTED,
                SELECTIVE_PAGE_OCR_NOT_SUPPORTED,
                OCR_PROCESSED_PAGES_NOT_RECORDED,
                RAW_OCR_OUTPUT_NOT_PRESERVED,
                OCR_NORMALIZATION_NOT_SEPARATED,
                DETERMINISTIC_OCR_CONFIGURATION_UNDEFINED,
            }
        )
    return gaps


def _candidate_status(
    *,
    engine_available: bool,
    adapter_present: bool,
    manifest_present: bool,
    page_provenance_present: bool,
    gaps: set[str],
) -> str:
    if (
        engine_available
        and adapter_present
        and manifest_present
        and page_provenance_present
        and not gaps
    ):
        return SUPPORTED_AND_AVAILABLE
    if engine_available and not adapter_present:
        return AVAILABLE_NOT_INTEGRATED
    if engine_available:
        return INTEGRATION_INCOMPLETE
    if OCR_WRAPPER_WITHOUT_ENGINE in gaps:
        return INTEGRATION_INCOMPLETE
    return NOT_AVAILABLE


def _read_repository_text_files(root: Path) -> Mapping[str, str]:
    texts: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in REPOSITORY_TEXT_SUFFIXES:
            continue
        if any(part in REPOSITORY_SKIP_PARTS for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        try:
            texts[relative] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return texts


def _contains_ocr_reference(text: str) -> bool:
    return any(term in text for term in OCR_SEARCH_TERMS)


def _is_test_or_fixture_path(path: str) -> bool:
    return path.startswith("tests/") or "/fixtures/" in path


def _is_documentation_path(path: str) -> bool:
    return path.startswith("docs/") or path in {"README.md", "TODO.md"}


def _looks_like_adapter(text: str) -> bool:
    lowered = text.lower()
    adapter_markers = (
        "run_controlled_tesseract_ocr",
        "controlled-tesseract-cli",
        "pytesseract.image_to_string",
        "tesserocr.",
        "easyocr.reader",
        "paddleocr(",
        "keras_ocr.pipeline",
        "ocrmypdf.ocr(",
        "windows.media.ocr",
    )
    return any(marker in lowered for marker in adapter_markers)


def _repository_integration_names(
    repository_capabilities: Sequence[OcrRepositoryCapability],
) -> set[str]:
    names: set[str] = set()
    for capability in repository_capabilities:
        for location in capability.evidence_locations:
            names.update(
                term.lower()
                for term in OCR_SEARCH_TERMS
                if term.lower() in location.lower()
            )
    return names


def _metadata_version(distribution_name: str) -> str:
    return importlib.metadata.version(distribution_name)


def _metadata_mapping(distribution_name: str) -> Mapping[str, str]:
    metadata: Any = importlib.metadata.metadata(distribution_name)
    result: dict[str, str] = {}
    license_value = metadata.get("License")
    if license_value:
        result["License"] = license_value
    classifiers = metadata.get_all("Classifier") or []
    for index, classifier in enumerate(classifiers):
        result[f"Classifier-{index}"] = classifier
    return result


def _metadata_license(metadata: Mapping[str, str]) -> str | None:
    license_value = metadata.get("License")
    if license_value and license_value.strip() and license_value != "UNKNOWN":
        return _sanitize_text(license_value.strip())
    classifier_values = [
        value
        for key, value in metadata.items()
        if key.startswith("Classifier") and value.startswith("License ::")
    ]
    if classifier_values:
        return _sanitize_text(sorted(classifier_values)[0])
    return None


def _resolve_command(name: str) -> str | None:
    return shutil.which(name)


def _run_probe(command: Sequence[str], timeout_seconds: int) -> ProbeCompletedProcess:
    completed = subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )
    return ProbeCompletedProcess(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _probe_executable_version(
    *,
    name: str,
    args: Sequence[str],
    runner: CommandRunner,
    timeout_seconds: int,
) -> tuple[str | None, str]:
    try:
        completed = runner((name, *args), timeout_seconds)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except OSError:
        return None, "failed"
    output = _first_version_line(completed.stdout, completed.stderr)
    if completed.returncode != 0:
        return output, "failed"
    return output, "ok" if output else "no_version_output"


def _probe_tesseract_languages(
    *,
    runner: CommandRunner,
    timeout_seconds: int,
) -> tuple[str, ...]:
    try:
        completed = runner(("tesseract", "--list-langs"), timeout_seconds)
    except (subprocess.TimeoutExpired, OSError):
        return ()
    if completed.returncode != 0:
        return ()
    languages: list[str] = []
    for line in (completed.stdout + "\n" + completed.stderr).splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("list of available"):
            continue
        if re.fullmatch(r"[A-Za-z0-9_+-]+", stripped):
            languages.append(stripped)
    return tuple(sorted(dict.fromkeys(languages)))


def _first_version_line(stdout: str, stderr: str) -> str | None:
    for line in (stdout + "\n" + stderr).splitlines():
        sanitized = _sanitize_text(line.strip())
        if sanitized:
            return sanitized
    return None


def _sanitize_text(value: str) -> str:
    sanitized = re.sub(r"[A-Za-z]:\\[^\s]+", "<path>", value)
    sanitized = re.sub(r"/[^\s:]+(?:/[^\s:]+)+", "<path>", sanitized)
    home = str(Path.home())
    if home:
        sanitized = sanitized.replace(home, "<home>")
    return sanitized[:240]


def _sort_gap_codes(gaps: set[str]) -> tuple[str, ...]:
    return tuple(
        sorted(gaps, key=lambda gap: (CONTROLLED_GAP_CODES + (gap,)).index(gap))
    )


def _build_summary(
    *,
    reference_classes: Mapping[str, tuple[str, ...]],
    python_packages: Sequence[OcrPythonPackageCapability],
    executables: Sequence[OcrExecutableCapability],
    engine_candidates: Sequence[OcrEngineCandidateAssessment],
    rendering: Mapping[str, object],
) -> Mapping[str, Any]:
    repository_counts = {
        key: len(reference_classes[key]) for key in sorted(reference_classes)
    }
    installed_packages = {
        package.distribution_name: package.version
        for package in sorted(python_packages, key=lambda item: item.distribution_name)
        if package.installed
    }
    installed_executables = {
        executable.executable_name: executable.version
        for executable in sorted(executables, key=lambda item: item.executable_name)
        if executable.installed
    }
    languages = tuple(
        sorted(
            {
                language
                for executable in executables
                for language in executable.supported_languages
            }
        )
    )
    return {
        "inventory_schema_name": INVENTORY_SCHEMA_NAME,
        "inventory_schema_version": INVENTORY_SCHEMA_VERSION,
        "repository_reference_counts": repository_counts,
        "installed_ocr_related_packages": installed_packages,
        "installed_executables": installed_executables,
        "available_ocr_language_models": languages,
        "rendering": dict(rendering),
        "engine_candidate_statuses": {
            candidate.engine_id: candidate.candidate_status
            for candidate in engine_candidates
        },
        "d7a_relationship": (
            "D.7a remains blocked until a supported OCR execution path can "
            "record engine identity, processed pages, provenance, and manifest "
            "metadata."
        ),
        "d7a_current_blocking_code": "NO_SUPPORTED_OCR_EXECUTION_PATH",
        "privacy": {
            "absolute_paths_included": False,
            "source_text_included": False,
            "ocr_recognition_executed": False,
            "software_installed": False,
        },
    }


__all__ = [
    "AVAILABLE_NOT_INTEGRATED",
    "BLOCKED",
    "CONTROLLED_GAP_CODES",
    "DETERMINISTIC_OCR_CONFIGURATION_UNDEFINED",
    "ENGINE_INSTALLED_BUT_NOT_INTEGRATED",
    "EXISTING_INTEGRATION_INCOMPLETE",
    "EXISTING_SUPPORTED_ENGINE_AVAILABLE",
    "FORCED_OCR_NOT_SUPPORTED",
    "GREEK_LANGUAGE_MODEL_UNAVAILABLE",
    "GREEK_SUPPORT_UNKNOWN",
    "IMPLEMENT_ADAPTER_FOR_INSTALLED_ENGINE",
    "INTEGRATION_INCOMPLETE",
    "INVENTORY_BLOCKED",
    "INVENTORY_SCHEMA_NAME",
    "INVENTORY_SCHEMA_VERSION",
    "LICENSE_METADATA_UNAVAILABLE",
    "NETWORK_MODEL_DOWNLOAD_REQUIRED",
    "NO_ENGINE_INSTALLED",
    "NO_OCR_ENGINE_AVAILABLE",
    "NOT_AVAILABLE",
    "OCR_ADAPTER_INCOMPLETE",
    "OCR_ENGINE_NOT_INTEGRATED",
    "OCR_ENGINE_VERSION_NOT_RECORDED",
    "OCR_MANIFEST_METADATA_MISSING",
    "OCR_NORMALIZATION_NOT_SEPARATED",
    "OCR_PAGE_PROVENANCE_NOT_RECORDED",
    "OCR_PROCESSED_PAGES_NOT_RECORDED",
    "OCR_WRAPPER_WITHOUT_ENGINE",
    "PDF_RENDERING_UNAVAILABLE",
    "RAW_OCR_OUTPUT_NOT_PRESERVED",
    "REPAIR_EXISTING_INTEGRATION",
    "REQUEST_ENGINE_INSTALLATION_APPROVAL",
    "REQUEST_LANGUAGE_OR_MODEL_APPROVAL",
    "SELECTIVE_PAGE_OCR_NOT_SUPPORTED",
    "SUPPORTED_AND_AVAILABLE",
    "UNKNOWN",
    "UNSUPPORTED_FOR_CURRENT_SCOPE",
    "USE_EXISTING_SUPPORTED_PATH",
    "OcrCapabilityInventoryResult",
    "OcrEngineCandidateAssessment",
    "OcrExecutableCapability",
    "OcrPythonPackageCapability",
    "OcrRepositoryCapability",
    "ProbeCompletedProcess",
    "assess_ocr_engine_candidates",
    "assess_pdf_rendering_capability",
    "classify_repository_ocr_references",
    "determine_overall_outcome",
    "inspect_executable_capabilities",
    "inspect_python_package_capabilities",
    "inspect_repository_ocr_capabilities",
    "inventory_ocr_capabilities",
]
