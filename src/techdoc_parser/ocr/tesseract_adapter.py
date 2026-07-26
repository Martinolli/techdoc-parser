"""Explicit Tesseract CLI OCR adapter."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from techdoc_parser.ocr.models import (
    AUTO_OCR_POLICY_UNDEFINED,
    AUTO_WHEN_NATIVE_TEXT_MISSING,
    FAIL,
    FAILED,
    GREEK_FIDELITY_NOT_ESTABLISHED,
    GREEK_LANGUAGE_MODEL_UNAVAILABLE,
    INVALID_PAGE_SELECTION,
    MATHEMATICAL_FIDELITY_NOT_ESTABLISHED,
    OCR_ALL_PAGES,
    OCR_EMPTY_OUTPUT,
    OCR_ENGINE_NOT_AVAILABLE,
    OCR_PAGE_FAILED,
    OCR_PAGE_TIMED_OUT,
    OCR_RENDERING_FAILED,
    OCR_SELECTED_PAGES,
    OCR_STDERR_REPORTED,
    PASS,
    PASS_WITH_WARNINGS,
    PROCESSED,
    REQUESTED_OCR_LANGUAGE_UNAVAILABLE,
    SOURCE_DOCUMENT_NOT_FOUND,
    TIMED_OUT,
    ControlledOcrDocumentResult,
    ControlledOcrPageResult,
    ControlledOcrRequest,
    OcrPageProvenance,
)


@dataclass(frozen=True)
class TesseractProcessResult:
    """Minimal subprocess result used by the adapter and tests."""

    returncode: int
    stdout: str
    stderr: str


CommandResolver = Callable[[str], str | None]
CommandRunner = Callable[[Sequence[str], int], TesseractProcessResult]


def run_controlled_tesseract_ocr(
    request: ControlledOcrRequest,
    *,
    command_resolver: CommandResolver | None = None,
    command_runner: CommandRunner | None = None,
) -> ControlledOcrDocumentResult:
    """Run explicit controlled OCR for a synthetic or approved source only."""
    resolver = shutil.which if command_resolver is None else command_resolver
    runner = _run_subprocess if command_runner is None else command_runner
    executable = resolver("tesseract")
    source = Path(request.source_path)
    source_bytes = source.read_bytes() if source.exists() else b""
    source_sha = sha256(source_bytes).hexdigest() if source_bytes else None
    source_size = len(source_bytes) if source_bytes else None

    version: str | None = None
    available_languages: tuple[str, ...] = ()
    warnings = _default_limitations_and_warnings(available_languages)[0]
    limitations = _default_limitations_and_warnings(available_languages)[1]
    errors: list[str] = []

    if executable is None:
        errors.append(OCR_ENGINE_NOT_AVAILABLE)
        return _document_failure(
            request=request,
            source=source,
            source_sha=source_sha,
            source_size=source_size,
            observed_page_count=0,
            version=None,
            available_languages=available_languages,
            warnings=warnings,
            errors=tuple(errors),
            limitations=limitations,
        )

    version = _probe_version(executable, runner)
    available_languages = _probe_languages(executable, runner)
    warnings, limitations = _default_limitations_and_warnings(available_languages)
    missing_languages = tuple(
        language
        for language in request.languages
        if language not in set(available_languages)
    )
    if missing_languages:
        errors.append(REQUESTED_OCR_LANGUAGE_UNAVAILABLE)
        return _document_failure(
            request=request,
            source=source,
            source_sha=source_sha,
            source_size=source_size,
            observed_page_count=0,
            version=version,
            available_languages=available_languages,
            warnings=warnings,
            errors=tuple(errors),
            limitations=limitations
            + (
                (
                    "Requested OCR languages are unavailable locally; "
                    "no fallback was used."
                ),
            ),
        )

    if request.mode == AUTO_WHEN_NATIVE_TEXT_MISSING:
        errors.append(AUTO_OCR_POLICY_UNDEFINED)
        return _document_failure(
            request=request,
            source=source,
            source_sha=source_sha,
            source_size=source_size,
            observed_page_count=0,
            version=version,
            available_languages=available_languages,
            warnings=warnings,
            errors=tuple(errors),
            limitations=limitations,
        )

    if not source.exists():
        errors.append(SOURCE_DOCUMENT_NOT_FOUND)
        return _document_failure(
            request=request,
            source=source,
            source_sha=source_sha,
            source_size=source_size,
            observed_page_count=0,
            version=version,
            available_languages=available_languages,
            warnings=warnings,
            errors=tuple(errors),
            limitations=limitations,
        )

    try:
        with fitz.open(source) as document:
            observed_page_count = document.page_count
            requested_pages = _resolve_requested_pages(request, observed_page_count)
            page_results = _run_pages(
                document=document,
                request=request,
                executable=executable,
                runner=runner,
                source_sha=source_sha or "",
                source_size=source_size or 0,
                engine_version=version,
                requested_pages=requested_pages,
            )
    except ValueError:
        errors.append(INVALID_PAGE_SELECTION)
        return _document_failure(
            request=request,
            source=source,
            source_sha=source_sha,
            source_size=source_size,
            observed_page_count=0,
            version=version,
            available_languages=available_languages,
            warnings=warnings,
            errors=tuple(errors),
            limitations=limitations,
        )
    except (OSError, RuntimeError) as exc:
        errors.extend((OCR_RENDERING_FAILED, _sanitize_excerpt(str(exc))))
        return _document_failure(
            request=request,
            source=source,
            source_sha=source_sha,
            source_size=source_size,
            observed_page_count=0,
            version=version,
            available_languages=available_languages,
            warnings=warnings,
            errors=tuple(errors),
            limitations=limitations,
        )

    failed_pages = tuple(
        page.page_number
        for page in page_results
        if page.status in {FAILED, TIMED_OUT} or page.errors
    )
    processed_pages = tuple(
        page.page_number for page in page_results if page.status == PROCESSED
    )
    requested_pages = tuple(page.page_number for page in page_results)
    page_warnings = tuple(
        sorted({warning for page in page_results for warning in page.warnings})
    )
    if failed_pages:
        outcome = FAIL
    elif warnings or page_warnings:
        outcome = PASS_WITH_WARNINGS
    else:
        outcome = PASS
    return ControlledOcrDocumentResult(
        request=request,
        outcome=outcome,
        source_filename=source.name,
        source_sha256=source_sha,
        source_size_bytes=source_size,
        observed_page_count=observed_page_count,
        requested_pages=requested_pages,
        processed_pages=processed_pages,
        skipped_pages=(),
        failed_pages=failed_pages,
        page_results=tuple(page_results),
        engine_version=version,
        available_languages=available_languages,
        warnings=tuple(sorted(set(warnings + page_warnings))),
        errors=(),
        limitations=limitations,
    )


def _run_pages(
    *,
    document: fitz.Document,
    request: ControlledOcrRequest,
    executable: str,
    runner: CommandRunner,
    source_sha: str,
    source_size: int,
    engine_version: str | None,
    requested_pages: tuple[int, ...],
) -> tuple[ControlledOcrPageResult, ...]:
    results: list[ControlledOcrPageResult] = []
    with tempfile.TemporaryDirectory(prefix="techdoc_controlled_ocr_") as temp_dir:
        root = Path(temp_dir)
        for page_number in requested_pages:
            pdf_page_index = page_number - 1
            page = document.load_page(pdf_page_index)
            matrix = fitz.Matrix(request.dpi / 72, request.dpi / 72)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False, colorspace=fitz.csRGB)
            image_bytes = pixmap.tobytes("png")
            image_path = root / f"page_{page_number:03d}.png"
            image_path.write_bytes(image_bytes)
            command = (
                executable,
                str(image_path),
                "stdout",
                "-l",
                "+".join(request.languages),
                "--oem",
                str(request.oem),
                "--psm",
                str(request.psm),
            )
            try:
                completed = runner(command, request.timeout_seconds)
                status = PROCESSED if completed.returncode == 0 else FAILED
                raw_text = completed.stdout
                normalized_text = _normalize_ocr_text(raw_text)
                page_warnings = list(_page_warnings(completed.stderr, normalized_text))
                page_errors = () if status == PROCESSED else (OCR_PAGE_FAILED,)
                stderr_excerpt = (
                    _sanitize_excerpt(completed.stderr) if completed.stderr else None
                )
                exit_code = completed.returncode
            except subprocess.TimeoutExpired:
                status = TIMED_OUT
                raw_text = ""
                normalized_text = ""
                page_warnings = []
                page_errors = (OCR_PAGE_TIMED_OUT,)
                stderr_excerpt = None
                exit_code = None
            provenance = OcrPageProvenance(
                page_number=page_number,
                pdf_page_index=pdf_page_index,
                source_sha256=source_sha,
                source_size_bytes=source_size,
                rendered_image_sha256=sha256(image_bytes).hexdigest(),
                raw_ocr_sha256=sha256(raw_text.encode("utf-8")).hexdigest(),
                normalized_ocr_sha256=sha256(
                    normalized_text.encode("utf-8")
                ).hexdigest(),
                rendering_engine="PyMuPDF",
                rendering_dpi=request.dpi,
                ocr_engine="tesseract",
                ocr_engine_version=engine_version,
                ocr_languages=request.languages,
                ocr_mode=request.mode,
                psm=request.psm,
                oem=request.oem,
            )
            results.append(
                ControlledOcrPageResult(
                    page_number=page_number,
                    pdf_page_index=pdf_page_index,
                    status=status,
                    raw_ocr_text=raw_text,
                    normalized_ocr_text=normalized_text,
                    provenance=provenance,
                    warnings=tuple(sorted(set(page_warnings))),
                    errors=page_errors,
                    stderr_excerpt=stderr_excerpt,
                    exit_code=exit_code,
                    rendered_image_png=(
                        image_bytes if request.preserve_rendered_pages else None
                    ),
                )
            )
    return tuple(results)


def _resolve_requested_pages(
    request: ControlledOcrRequest,
    observed_page_count: int,
) -> tuple[int, ...]:
    if request.mode == OCR_ALL_PAGES:
        return tuple(range(1, observed_page_count + 1))
    if request.mode == OCR_SELECTED_PAGES:
        pages = request.selected_pages or ()
        if any(page > observed_page_count for page in pages):
            raise ValueError("Selected page is outside the document page count.")
        return pages
    raise ValueError("Unsupported request mode for page resolution.")


def _run_subprocess(
    command: Sequence[str],
    timeout_seconds: int,
) -> TesseractProcessResult:
    completed = subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )
    return TesseractProcessResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _probe_version(executable: str, runner: CommandRunner) -> str | None:
    try:
        completed = runner((executable, "--version"), 5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in (completed.stdout + "\n" + completed.stderr).splitlines():
        stripped = _sanitize_excerpt(line.strip())
        if stripped:
            return stripped
    return None


def _probe_languages(executable: str, runner: CommandRunner) -> tuple[str, ...]:
    try:
        completed = runner((executable, "--list-langs"), 5)
    except (OSError, subprocess.TimeoutExpired):
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


def _normalize_ocr_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.endswith("\f"):
        normalized = normalized[:-1]
    lines = [line.rstrip() for line in normalized.split("\n")]
    normalized = "\n".join(lines).strip()
    return f"{normalized}\n" if normalized else ""


def _page_warnings(stderr: str, normalized_text: str) -> tuple[str, ...]:
    warnings: list[str] = []
    if stderr.strip():
        warnings.append(OCR_STDERR_REPORTED)
    if not normalized_text:
        warnings.append(OCR_EMPTY_OUTPUT)
    return tuple(warnings)


def _default_limitations_and_warnings(
    available_languages: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    warnings = [GREEK_FIDELITY_NOT_ESTABLISHED, MATHEMATICAL_FIDELITY_NOT_ESTABLISHED]
    limitations = [
        "OCR fidelity is not established by adapter execution alone.",
        "Greek symbol fidelity requires owner review.",
        "Mathematical expression fidelity requires owner review.",
    ]
    if "ell" not in available_languages:
        warnings.append(GREEK_LANGUAGE_MODEL_UNAVAILABLE)
        limitations.append(
            "The Tesseract ell language model is unavailable in the local environment."
        )
    return tuple(sorted(set(warnings))), tuple(limitations)


def _document_failure(
    *,
    request: ControlledOcrRequest,
    source: Path,
    source_sha: str | None,
    source_size: int | None,
    observed_page_count: int,
    version: str | None,
    available_languages: tuple[str, ...],
    warnings: tuple[str, ...],
    errors: tuple[str, ...],
    limitations: tuple[str, ...],
) -> ControlledOcrDocumentResult:
    return ControlledOcrDocumentResult(
        request=request,
        outcome=FAIL,
        source_filename=source.name,
        source_sha256=source_sha,
        source_size_bytes=source_size,
        observed_page_count=observed_page_count,
        requested_pages=(),
        processed_pages=(),
        skipped_pages=(),
        failed_pages=(),
        page_results=(),
        engine_version=version,
        available_languages=available_languages,
        warnings=warnings,
        errors=errors,
        limitations=limitations,
    )


def _sanitize_excerpt(value: str) -> str:
    sanitized = re.sub(r"[A-Za-z]:\\[^\s]+", "<path>", value)
    sanitized = re.sub(r"/[^\s:]+(?:/[^\s:]+)+", "<path>", sanitized)
    return sanitized[:240]


__all__ = [
    "TesseractProcessResult",
    "run_controlled_tesseract_ocr",
]
