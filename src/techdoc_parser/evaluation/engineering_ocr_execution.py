"""D.7a-2 engineering OCR execution package helpers.

This module builds local owner-review packages and sanitized summaries from
already-generated native parser artifacts and controlled OCR artifacts. It does
not run OCR, modify source PDFs, import AviationRAG, generate embeddings, or
claim final OCR fidelity.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from techdoc_parser.evaluation.engineering_ocr_fidelity import (
    ENGINEERING_OCR_POLICY_NAME,
    ENGINEERING_OCR_POLICY_VERSION,
    OWNER_REVIEW_REQUIRED,
    EngineeringOcrEvaluationResult,
    EngineeringOcrPageEvidence,
)
from techdoc_parser.ocr.artifact import validate_ocr_artifact
from techdoc_parser.ocr.manifest import validate_ocr_manifest

EXECUTION_SCHEMA_NAME = "techdoc-engineering-ocr-execution-summary"
EXECUTION_SCHEMA_VERSION = "0.1.0"

REVIEW_CHECK_FIELDS = (
    "text_complete",
    "text_exact_enough",
    "reading_order_correct",
    "greek_symbols_preserved",
    "mathematical_operators_preserved",
    "subscripts_preserved",
    "superscripts_preserved",
    "equation_grouping_correct",
    "equation_sequence_correct",
    "figure_caption_correct",
    "figure_text_not_fabricated",
    "table_classification_correct",
    "headings_correct",
    "page_provenance_correct",
    "chunks_coherent",
    "fabricated_content_absent",
)

CRITICAL_CHECK_FIELDS = (
    "greek_symbols_preserved",
    "mathematical_operators_preserved",
    "equation_grouping_correct",
    "page_provenance_correct",
    "fabricated_content_absent",
)

WARNING_GREEK_LANGUAGE = "GREEK_LANGUAGE_MODEL_UNAVAILABLE"
WARNING_GREEK_FIDELITY = "GREEK_FIDELITY_NOT_ESTABLISHED"
WARNING_MATH_FIDELITY = "MATHEMATICAL_FIDELITY_NOT_ESTABLISHED"
WARNING_OWNER_REVIEW = "OWNER_REVIEW_REQUIRED_FOR_FIDELITY_ACCEPTANCE"
OCR_OUTPUT_NONDETERMINISTIC = "OCR_OUTPUT_NONDETERMINISTIC"

PAGE_PROFILES = (
    "native_text",
    "image_only",
    "hybrid",
    "formula_heavy",
    "greek_symbol_heavy",
    "figure_heavy",
    "table_candidate",
    "multi_column",
    "mixed_layout",
    "blank_or_near_blank",
)


def build_engineering_ocr_execution_package(
    *,
    source_path: str | Path,
    native_document_path: str | Path,
    structured_document_path: str | Path,
    native_manifest_path: str | Path,
    ocr_artifact_path: str | Path,
    ocr_manifest_path: str | Path,
    output_root: str | Path,
    evaluation_result: EngineeringOcrEvaluationResult,
    determinism: Mapping[str, object],
    allow_local_write: bool = False,
    overwrite: bool = True,
) -> dict[str, object]:
    """Create the local D.7a-2 package and return a sanitized summary."""
    if not allow_local_write:
        raise PermissionError("D.7a-2 package writing requires allow_local_write.")
    root = Path(output_root)
    source = Path(source_path)
    native_document = _load_json(native_document_path)
    structured_document = _load_json(structured_document_path)
    native_manifest = _load_json(native_manifest_path)
    ocr_artifact = _load_json(ocr_artifact_path)
    ocr_manifest = _load_json(ocr_manifest_path)
    _validate_artifacts(ocr_artifact, ocr_manifest)

    native_pages = _native_pages_from_structured_document(structured_document)
    native_blocks = _native_blocks_from_structured_document(structured_document)
    ocr_pages = _ocr_pages_from_artifact(ocr_artifact)
    ocr_blocks = _ocr_blocks_from_artifact(ocr_artifact)
    source_pages = _source_page_characterization(source)
    structured_counts = _structured_counts(structured_document)
    parser_warnings = _parser_warning_codes(native_document)
    page_evidence = _page_evidence_records(
        evaluation_result=evaluation_result,
        source_pages=source_pages,
        native_pages=native_pages,
        native_blocks=native_blocks,
        ocr_pages=ocr_pages,
        ocr_blocks=ocr_blocks,
        structured_counts=structured_counts,
        parser_warnings=parser_warnings,
        ocr_artifact=ocr_artifact,
    )
    summary = _preliminary_summary(
        source=source,
        native_document=native_document,
        structured_document=structured_document,
        native_manifest=native_manifest,
        ocr_artifact=ocr_artifact,
        ocr_manifest=ocr_manifest,
        evaluation_result=evaluation_result,
        determinism=determinism,
        page_evidence=page_evidence,
    )
    _write_package(
        root=root,
        source=source,
        native_pages=native_pages,
        native_blocks=native_blocks,
        ocr_pages=ocr_pages,
        ocr_blocks=ocr_blocks,
        page_evidence=page_evidence,
        summary=summary,
        overwrite=overwrite,
    )
    return summary


def compare_engineering_ocr_determinism(
    run_1_dir: str | Path,
    run_2_dir: str | Path,
) -> dict[str, object]:
    """Compare deterministic OCR outputs from two identical controlled runs."""
    first = Path(run_1_dir)
    second = Path(run_2_dir)
    relative_files = _deterministic_ocr_files(first)
    second_files = _deterministic_ocr_files(second)
    if relative_files != second_files:
        return {
            "deterministic": False,
            "warning_codes": [OCR_OUTPUT_NONDETERMINISTIC],
            "file_count": len(relative_files),
            "mismatched_files": sorted(set(relative_files) ^ set(second_files)),
            "outputs": [],
        }
    outputs: list[dict[str, object]] = []
    mismatches: list[str] = []
    for relative in relative_files:
        left = first / relative
        right = second / relative
        left_hash = _file_sha256(left)
        right_hash = _file_sha256(right)
        match = left_hash == right_hash
        if not match:
            mismatches.append(relative.as_posix())
        outputs.append(
            {
                "path": relative.as_posix(),
                "run_1_sha256": left_hash,
                "run_2_sha256": right_hash,
                "match": match,
            }
        )
    return {
        "deterministic": not mismatches,
        "warning_codes": [] if not mismatches else [OCR_OUTPUT_NONDETERMINISTIC],
        "file_count": len(outputs),
        "mismatched_files": mismatches,
        "outputs": outputs,
    }


def sanitized_summary_fixture(summary: Mapping[str, object]) -> dict[str, object]:
    """Return the committed, source-text-free D.7a-2 summary fixture."""
    allowed = {
        "schema_name",
        "schema_version",
        "document_key",
        "source_filename",
        "source_sha256",
        "page_count",
        "native_parser_version",
        "structured_document_schema",
        "structured_document_schema_version",
        "ocr_adapter",
        "ocr_adapter_version",
        "tesseract_version",
        "requested_languages",
        "available_languages",
        "render_backend",
        "render_backend_version",
        "dpi",
        "psm",
        "oem",
        "processed_page_count",
        "failed_page_count",
        "timed_out_page_count",
        "profile_counts",
        "review_priority_counts",
        "automated_outcome_counts",
        "warning_code_counts",
        "review_package_page_count",
        "pending_checklist_count",
        "owner_review_status",
        "corpus_outcome",
        "determinism_result",
        "artifact_sha256",
        "manifest_sha256",
    }
    return {key: summary[key] for key in sorted(allowed) if key in summary}


def _page_evidence_records(
    *,
    evaluation_result: EngineeringOcrEvaluationResult,
    source_pages: Mapping[int, Mapping[str, object]],
    native_pages: Mapping[int, str],
    native_blocks: Mapping[int, Sequence[Mapping[str, object]]],
    ocr_pages: Mapping[int, str],
    ocr_blocks: Mapping[int, Sequence[Mapping[str, object]]],
    structured_counts: Mapping[int, Mapping[str, int]],
    parser_warnings: Mapping[int, Sequence[str]],
    ocr_artifact: Mapping[str, object],
) -> list[dict[str, object]]:
    d7a_pages = {page.page_number: page for page in evaluation_result.page_results}
    ocr_page_data: dict[int, Mapping[str, object]] = {}
    for page in _sequence_of_mappings(ocr_artifact.get("pages")):
        page_number_value = page.get("page_number")
        if isinstance(page_number_value, int):
            ocr_page_data[page_number_value] = page
    records: list[dict[str, object]] = []
    for page_number in sorted(source_pages):
        d7a_page = d7a_pages.get(page_number)
        native_text = native_pages.get(page_number, "")
        ocr_text = ocr_pages.get(page_number, "")
        counts = structured_counts.get(page_number, {})
        source = source_pages[page_number]
        ocr_data = ocr_page_data.get(page_number, {})
        ocr_warnings = tuple(_string_list(ocr_data, "warnings"))
        warning_codes = _page_warning_codes(d7a_page, ocr_warnings, native_text)
        profiles = _page_profiles(
            native_text=native_text,
            ocr_text=ocr_text,
            source=source,
            counts=counts,
        )
        priority = _review_priority(
            profiles=profiles,
            native_text=native_text,
            ocr_text=ocr_text,
            d7a_page=d7a_page,
            warning_codes=warning_codes,
        )
        record = {
            "page_number": page_number,
            "pdf_page_index": page_number - 1,
            "profiles": profiles,
            "review_priority": priority,
            "automated_outcome": (
                d7a_page.automated_outcome if d7a_page is not None else "BLOCKED"
            ),
            "final_page_outcome": (
                d7a_page.final_page_outcome if d7a_page is not None else "BLOCKED"
            ),
            "native_character_count": len(native_text),
            "ocr_character_count": len(ocr_text),
            "native_line_count": _line_count(native_text),
            "ocr_line_count": _line_count(ocr_text),
            "native_block_count": len(native_blocks.get(page_number, ())),
            "ocr_block_count": len(ocr_blocks.get(page_number, ())),
            "image_count": _int_value(source.get("image_count"), 0),
            "figure_candidate_count": counts.get("figures", 0),
            "table_candidate_count": counts.get("tables", 0),
            "equation_candidate_count": counts.get("equations", 0),
            "greek_math_symbol_proxy_count": _symbol_proxy_count(native_text),
            "parser_warning_codes": list(parser_warnings.get(page_number, ())),
            "ocr_warning_codes": list(ocr_warnings),
            "warning_codes": warning_codes,
            "suspected_multi_column_layout": "multi_column" in profiles,
            "categories": _category_findings(
                d7a_page=d7a_page,
                profiles=profiles,
                native_text=native_text,
                ocr_text=ocr_text,
                counts=counts,
            ),
            "provenance": ocr_data.get("provenance", {}),
            "checklist_status": "pending",
        }
        records.append(record)
    return records


def _preliminary_summary(
    *,
    source: Path,
    native_document: Mapping[str, object],
    structured_document: Mapping[str, object],
    native_manifest: Mapping[str, object],
    ocr_artifact: Mapping[str, object],
    ocr_manifest: Mapping[str, object],
    evaluation_result: EngineeringOcrEvaluationResult,
    determinism: Mapping[str, object],
    page_evidence: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    del native_manifest
    profile_counts = Counter(
        profile for page in page_evidence for profile in _string_list(page, "profiles")
    )
    priority_counts = Counter(str(page["review_priority"]) for page in page_evidence)
    warning_counts = Counter(
        warning
        for page in page_evidence
        for warning in _string_list(page, "warning_codes")
    )
    warning_counts.update(_string_list(ocr_artifact, "warnings"))
    warning_counts.update((WARNING_OWNER_REVIEW,))
    requested_pages = ocr_artifact.get("requested_pages", ())
    processed_pages = ocr_artifact.get("processed_pages", ())
    failed_pages = ocr_artifact.get("failed_pages", ())
    ocr_pages = _sequence_of_mappings(ocr_artifact.get("pages"))
    timed_out_pages = [
        page.get("page_number")
        for page in ocr_pages
        if page.get("status") == "timed_out"
    ]
    engine = _mapping(ocr_artifact.get("engine"))
    request = _mapping(ocr_artifact.get("request"))
    artifact = _mapping(ocr_manifest.get("artifact"))
    return {
        "schema_name": EXECUTION_SCHEMA_NAME,
        "schema_version": EXECUTION_SCHEMA_VERSION,
        "policy_name": ENGINEERING_OCR_POLICY_NAME,
        "policy_version": ENGINEERING_OCR_POLICY_VERSION,
        "document_key": "wing_design_chapter_7",
        "source_filename": source.name,
        "source_sha256": _file_sha256(source),
        "source_size_bytes": source.stat().st_size,
        "page_count": len(page_evidence),
        "native_extraction_status": "completed",
        "native_parser_version": _parser_version(
            native_document=native_document,
            structured_document=structured_document,
        ),
        "structured_document_schema": str(structured_document.get("schema_name", "")),
        "structured_document_schema_version": str(
            structured_document.get("schema_version", "")
        ),
        "ocr_execution_status": str(ocr_artifact.get("outcome", "")),
        "ocr_adapter": str(_mapping(ocr_artifact.get("adapter")).get("name", "")),
        "ocr_adapter_version": str(
            _mapping(ocr_artifact.get("adapter")).get("version", "")
        ),
        "tesseract_version": str(engine.get("version", "")),
        "requested_languages": _string_list(engine, "requested_languages"),
        "available_languages": _string_list(engine, "available_languages"),
        "render_backend": "PyMuPDF",
        "render_backend_version": fitz.version[0],
        "dpi": request.get("dpi"),
        "psm": request.get("psm"),
        "oem": request.get("oem"),
        "requested_page_count": len(requested_pages)
        if isinstance(requested_pages, Sequence)
        else 0,
        "processed_page_count": len(processed_pages)
        if isinstance(processed_pages, Sequence)
        else 0,
        "failed_page_count": (
            len(failed_pages) if isinstance(failed_pages, Sequence) else 0
        ),
        "timed_out_page_count": len(timed_out_pages),
        "profile_counts": dict(sorted(profile_counts.items())),
        "review_priority_counts": dict(sorted(priority_counts.items())),
        "automated_outcome_counts": dict(evaluation_result.page_outcome_counts),
        "warning_code_counts": dict(sorted(warning_counts.items())),
        "review_package_page_count": len(page_evidence),
        "pending_checklist_count": len(page_evidence),
        "owner_review_status": "pending",
        "owner_review_completion": f"0/{len(page_evidence)}",
        "corpus_outcome": OWNER_REVIEW_REQUIRED,
        "determinism_result": {
            "deterministic": bool(determinism.get("deterministic")),
            "file_count": determinism.get("file_count"),
            "mismatched_files": _string_list(determinism, "mismatched_files"),
        },
        "artifact_sha256": str(artifact.get("sha256", "")),
        "manifest_sha256": _canonical_json_sha256(ocr_manifest),
        "limitations": [
            WARNING_GREEK_LANGUAGE,
            WARNING_GREEK_FIDELITY,
            WARNING_MATH_FIDELITY,
            WARNING_OWNER_REVIEW,
        ],
        "privacy": {
            "source_text_included": False,
            "ocr_text_included": False,
            "page_images_included": False,
            "absolute_paths_included": False,
        },
    }


def _write_package(
    *,
    root: Path,
    source: Path,
    native_pages: Mapping[int, str],
    native_blocks: Mapping[int, Sequence[Mapping[str, object]]],
    ocr_pages: Mapping[int, str],
    ocr_blocks: Mapping[int, Sequence[Mapping[str, object]]],
    page_evidence: Sequence[Mapping[str, object]],
    summary: Mapping[str, object],
    overwrite: bool,
) -> None:
    automated_root = _safe_child(root, "automated")
    review_root = _safe_child(root, "review")
    preliminary_root = _safe_child(root, "preliminary")
    _write_json(
        automated_root / "source_characterization.json",
        {"pages": [_source_page_record(page) for page in page_evidence]},
        overwrite=overwrite,
    )
    _write_json(
        automated_root / "page_evidence.json",
        {"pages": page_evidence},
        overwrite=overwrite,
    )
    _write_json(
        automated_root / "automated_report.json",
        {"summary": sanitized_summary_fixture(summary), "pages": page_evidence},
        overwrite=overwrite,
    )
    _write_text(
        automated_root / "automated_report.md",
        _automated_markdown(summary),
        overwrite=overwrite,
    )
    _write_json(
        preliminary_root / "preliminary_result.json",
        summary,
        overwrite=overwrite,
    )
    _write_text(
        preliminary_root / "preliminary_result.md",
        _preliminary_markdown(summary),
        overwrite=overwrite,
    )
    for page in page_evidence:
        page_number = _int_value(page.get("page_number"), 0)
        page_dir = _safe_child(review_root, f"page_{page_number:03d}")
        page_dir.mkdir(parents=True, exist_ok=True)
        _render_page(
            source,
            page_number - 1,
            page_dir / "page.png",
            overwrite=overwrite,
        )
        _write_text(
            page_dir / "native_text.txt",
            native_pages.get(page_number, ""),
            overwrite=overwrite,
        )
        _write_text(
            page_dir / "ocr_text.txt",
            ocr_pages.get(page_number, ""),
            overwrite=overwrite,
        )
        _write_json(
            page_dir / "native_blocks.json",
            {"blocks": list(native_blocks.get(page_number, ()))},
            overwrite=overwrite,
        )
        _write_json(
            page_dir / "ocr_blocks.json",
            {"blocks": list(ocr_blocks.get(page_number, ()))},
            overwrite=overwrite,
        )
        _write_json(page_dir / "automated_summary.json", page, overwrite=overwrite)
        _write_json(
            page_dir / "review_checklist.json",
            _pending_checklist(page_number),
            overwrite=overwrite,
        )
        _write_text(
            page_dir / "review.html",
            _page_review_html(
                page,
                page_number,
                native_text=native_pages.get(page_number, ""),
                ocr_text=ocr_pages.get(page_number, ""),
            ),
            overwrite=overwrite,
        )
    _write_text(
        review_root / "index.html",
        _index_html(page_evidence),
        overwrite=overwrite,
    )


def _source_page_characterization(source: Path) -> dict[int, dict[str, object]]:
    pages: dict[int, dict[str, object]] = {}
    with fitz.open(source) as document:
        for index, page in enumerate(document):
            text = page.get_text("text") or ""
            pages[index + 1] = {
                "page_number": index + 1,
                "pdf_page_index": index,
                "native_character_count": len(text.strip()),
                "native_line_count": _line_count(text),
                "image_count": len(page.get_images(full=True)),
                "width": page.rect.width,
                "height": page.rect.height,
            }
    return pages


def _native_pages_from_structured_document(
    data: Mapping[str, object],
) -> dict[int, str]:
    grouped: dict[int, list[tuple[int, str]]] = {}
    for block in _sequence_of_mappings(data.get("blocks")):
        page_number = block.get("page_number")
        text = block.get("text")
        if isinstance(page_number, int) and isinstance(text, str):
            index = block.get("document_block_index")
            grouped.setdefault(page_number, []).append(
                (index if isinstance(index, int) else 0, text)
            )
    return {
        page_number: "\n".join(text for _, text in sorted(blocks))
        for page_number, blocks in grouped.items()
    }


def _native_blocks_from_structured_document(
    data: Mapping[str, object],
) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = {}
    for block in _sequence_of_mappings(data.get("blocks")):
        page_number = block.get("page_number")
        if isinstance(page_number, int):
            grouped.setdefault(page_number, []).append(dict(block))
    return grouped


def _ocr_pages_from_artifact(data: Mapping[str, object]) -> dict[int, str]:
    pages: dict[int, str] = {}
    for page in _sequence_of_mappings(data.get("pages")):
        page_number = page.get("page_number")
        text = page.get("normalized_ocr_text")
        if isinstance(page_number, int) and isinstance(text, str):
            pages[page_number] = text
    return pages


def _ocr_blocks_from_artifact(
    data: Mapping[str, object],
) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = {}
    for page in _sequence_of_mappings(data.get("pages")):
        page_number = page.get("page_number")
        text = page.get("normalized_ocr_text")
        if not isinstance(page_number, int) or not isinstance(text, str):
            continue
        grouped[page_number] = [
            {"line_index": index, "text": line}
            for index, line in enumerate(text.splitlines())
            if line.strip()
        ]
    return grouped


def _structured_counts(data: Mapping[str, object]) -> dict[int, dict[str, int]]:
    counts: dict[int, Counter[str]] = {}
    for block in _sequence_of_mappings(data.get("blocks")):
        page_number = block.get("page_number")
        if not isinstance(page_number, int):
            continue
        page_counts = counts.setdefault(page_number, Counter())
        block_type = str(block.get("block_type", ""))
        if block_type == "figure_caption":
            page_counts["figures"] += 1
        if block_type == "table":
            page_counts["tables"] += 1
        if block_type == "equation":
            page_counts["equations"] += 1
    for key in ("tables", "figures", "equations"):
        for entity in _sequence_of_mappings(data.get(key)):
            page_number = _entity_page_number(entity)
            if page_number is not None:
                counts.setdefault(page_number, Counter())[key] += 1
    return {page: dict(values) for page, values in counts.items()}


def _parser_warning_codes(
    native_document: Mapping[str, object],
) -> dict[int, list[str]]:
    warnings: dict[int, list[str]] = {}
    pages = _sequence_of_mappings(native_document.get("pages"))
    for page in pages:
        page_number = page.get("page_number")
        if not isinstance(page_number, int):
            continue
        page_warnings: list[str] = []
        if page.get("requires_ocr") is True:
            page_warnings.append("page.requires_ocr")
        if page.get("has_native_text") is False:
            page_warnings.append("page.no_native_text")
        warnings[page_number] = page_warnings
    return warnings


def _page_profiles(
    *,
    native_text: str,
    ocr_text: str,
    source: Mapping[str, object],
    counts: Mapping[str, int],
) -> list[str]:
    profiles: set[str] = set()
    image_count = _int_value(source.get("image_count"), 0)
    if native_text.strip():
        profiles.add("native_text")
    if image_count and not native_text.strip():
        profiles.add("image_only")
    if image_count and native_text.strip():
        profiles.add("hybrid")
    if counts.get("equations", 0) or _formula_signal_count(native_text):
        profiles.add("formula_heavy")
    if _greek_symbol_count(native_text) or _greek_symbol_count(ocr_text):
        profiles.add("greek_symbol_heavy")
    if counts.get("figures", 0) or image_count:
        profiles.add("figure_heavy")
    if counts.get("tables", 0) or _table_signal_count(native_text):
        profiles.add("table_candidate")
    if _looks_multi_column(native_text):
        profiles.add("multi_column")
    if len(native_text.splitlines()) > 12 or image_count:
        profiles.add("mixed_layout")
    if len(native_text.strip()) < 50 and len(ocr_text.strip()) < 50:
        profiles.add("blank_or_near_blank")
    return [profile for profile in PAGE_PROFILES if profile in profiles]


def _review_priority(
    *,
    profiles: Sequence[str],
    native_text: str,
    ocr_text: str,
    d7a_page: EngineeringOcrPageEvidence | None,
    warning_codes: Sequence[str],
) -> str:
    if (
        not ocr_text.strip()
        or "greek_symbol_heavy" in profiles
        or "formula_heavy" in profiles
        or "PAGE_PROVENANCE_CONTRADICTION" in warning_codes
        or (d7a_page is not None and d7a_page.automated_outcome == "FAIL")
        or _coverage_gap(native_text, ocr_text) >= 0.5
    ):
        return "critical"
    if (
        "multi_column" in profiles
        or "figure_heavy" in profiles
        and "formula_heavy" in profiles
        or "table_candidate" in profiles
        and "figure_heavy" in profiles
        or _coverage_gap(native_text, ocr_text) >= 0.25
    ):
        return "high"
    if "blank_or_near_blank" in profiles:
        return "low"
    return "normal"


def _category_findings(
    *,
    d7a_page: EngineeringOcrPageEvidence | None,
    profiles: Sequence[str],
    native_text: str,
    ocr_text: str,
    counts: Mapping[str, int],
) -> dict[str, object]:
    findings = list(d7a_page.findings if d7a_page is not None else ())
    finding_codes = [finding.code for finding in findings]
    return {
        "TEXT_COMPLETENESS": {
            "native_characters": len(native_text),
            "ocr_characters": len(ocr_text),
            "coverage_gap": round(_coverage_gap(native_text, ocr_text), 4),
        },
        "TEXT_EXACTNESS": {"automated_finding_codes": finding_codes},
        "READING_ORDER": {
            "warning_codes": list(d7a_page.reading_order_warnings)
            if d7a_page is not None
            else []
        },
        "GREEK_SYMBOL_PRESERVATION": {
            "warning_codes": [WARNING_GREEK_FIDELITY]
            if "greek_symbol_heavy" in profiles
            else []
        },
        "MATHEMATICAL_OPERATOR_PRESERVATION": {
            "warning_codes": [WARNING_MATH_FIDELITY]
            if "formula_heavy" in profiles
            else []
        },
        "SUBSCRIPT_PRESERVATION": {"status": "owner_review_required"},
        "SUPERSCRIPT_PRESERVATION": {"status": "owner_review_required"},
        "EQUATION_GROUPING": {"candidate_count": counts.get("equations", 0)},
        "EQUATION_SEQUENCE": {"status": "owner_review_required"},
        "FIGURE_CAPTION_ASSOCIATION": {"candidate_count": counts.get("figures", 0)},
        "FIGURE_TEXT_FABRICATION": {"status": "owner_review_required"},
        "TABLE_CLASSIFICATION": {"candidate_count": counts.get("tables", 0)},
        "HEADING_STRUCTURE": {"status": "owner_review_required"},
        "PAGE_PROVENANCE": {"status": "recorded"},
        "CHUNK_COHERENCE": {"status": "owner_review_required"},
        "FABRICATED_CONTENT": {"status": "owner_review_required"},
    }


def _page_warning_codes(
    d7a_page: EngineeringOcrPageEvidence | None,
    ocr_warnings: Sequence[str],
    native_text: str,
) -> list[str]:
    warnings = set(ocr_warnings)
    warnings.add(WARNING_OWNER_REVIEW)
    if _greek_symbol_count(native_text):
        warnings.add(WARNING_GREEK_FIDELITY)
    if _formula_signal_count(native_text):
        warnings.add(WARNING_MATH_FIDELITY)
    if d7a_page is not None:
        warnings.update(finding.code for finding in d7a_page.findings)
        warnings.update(d7a_page.reading_order_warnings)
        warnings.update(d7a_page.symbol_substitution_warnings)
    return sorted(warnings)


def _pending_checklist(page_number: int) -> dict[str, object]:
    return {
        "page_number": page_number,
        "review_status": "pending",
        "checklist": {field: "pending" for field in REVIEW_CHECK_FIELDS},
        "critical_fields": list(CRITICAL_CHECK_FIELDS),
        "reviewer_notes": "",
        "finding_codes": [],
        "accepted_limitation_codes": [],
        "second_review_reason": "",
    }


def _page_review_html(
    page: Mapping[str, object],
    page_number: int,
    *,
    native_text: str,
    ocr_text: str,
) -> str:
    categories = _mapping(page.get("categories"))
    category_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(name))}</td>"
        f"<td>{html.escape(json.dumps(value, ensure_ascii=False, sort_keys=True))}</td>"
        "</tr>"
        for name, value in sorted(categories.items())
    )
    warnings = ", ".join(_string_list(page, "warning_codes"))
    profiles = ", ".join(_string_list(page, "profiles"))
    return (
        '<!doctype html>\n<html><head><meta charset="utf-8">'
        f"<title>D.7a-2 page {page_number}</title>"
        "<style>body{font-family:Arial,sans-serif;margin:1rem;}"
        ".grid{display:grid;grid-template-columns:minmax(320px,1fr) 1fr 1fr;"
        "gap:1rem;}"
        "img{max-width:100%;border:1px solid #777;}"
        "pre{white-space:pre-wrap;border:1px solid #ccc;padding:.5rem;"
        "max-height:70vh;overflow:auto;}"
        "table{border-collapse:collapse;width:100%;}"
        "td,th{border:1px solid #ccc;padding:.35rem;vertical-align:top;}"
        "</style></head><body>"
        f"<h1>Wing Design OCR Review - Page {page_number}</h1>"
        "<p>Checklist status: pending. Automated evidence is not final truth.</p>"
        f"<p>Priority: {html.escape(str(page.get('review_priority')))}; "
        f"Profiles: {html.escape(profiles)}; Warnings: {html.escape(warnings)}</p>"
        '<div class="grid"><section><h2>Rendered Page</h2>'
        '<img src="page.png" alt="rendered source page"></section>'
        "<section><h2>Native Text</h2><pre>"
        f"{html.escape(native_text)}"
        "</pre></section><section><h2>OCR Text</h2><pre>"
        f"{html.escape(ocr_text)}"
        "</pre></section></div>"
        "<h2>Automated Categories</h2><table>"
        "<tr><th>Category</th><th>Evidence</th></tr>"
        f"{category_rows}</table>"
        "<p>Review checklist guidance is stored in review_checklist.json.</p>"
        "</body></html>\n"
    )


def _index_html(pages: Sequence[Mapping[str, object]]) -> str:
    row_values: list[str] = []
    for page in pages:
        page_number = _int_value(page.get("page_number"), 0)
        row_values.append(
            "<tr>"
            f"<td>{page_number}</td>"
            f"<td>{html.escape(', '.join(_string_list(page, 'profiles')))}</td>"
            f"<td>{html.escape(str(page['review_priority']))}</td>"
            f"<td>{html.escape(str(page['automated_outcome']))}</td>"
            f"<td>{html.escape(', '.join(_string_list(page, 'warning_codes')))}</td>"
            f'<td><a href="page_{page_number:03d}/review.html">review</a></td>'
            f"<td>{html.escape(str(page['checklist_status']))}</td>"
            "</tr>"
        )
    rows = "".join(row_values)
    return (
        '<!doctype html>\n<html><head><meta charset="utf-8">'
        "<title>D.7a-2 Wing Design OCR Review Index</title>"
        "<style>body{font-family:Arial,sans-serif;margin:1rem;}"
        "table{border-collapse:collapse;width:100%;}"
        "td,th{border:1px solid #ccc;padding:.35rem;vertical-align:top;}"
        "</style></head><body><h1>Wing Design OCR Review Index</h1>"
        "<p>All page checklists are pending owner review.</p><table>"
        "<tr><th>Page</th><th>Profiles</th><th>Priority</th><th>Automated Outcome</th>"
        "<th>Warnings</th><th>Review</th><th>Checklist</th></tr>"
        f"{rows}</table></body></html>\n"
    )


def _automated_markdown(summary: Mapping[str, object]) -> str:
    return (
        "# D.7a-2 Automated OCR Evidence\n\n"
        f"Corpus outcome: `{summary['corpus_outcome']}`\n\n"
        f"Pages: `{summary['page_count']}`\n\n"
        f"Owner review completion: `{summary['owner_review_completion']}`\n"
    )


def _preliminary_markdown(summary: Mapping[str, object]) -> str:
    return (
        "# D.7a-2 Preliminary Result\n\n"
        f"Source checksum: `{summary['source_sha256']}`\n\n"
        f"OCR execution status: `{summary['ocr_execution_status']}`\n\n"
        f"Owner review completion: `{summary['owner_review_completion']}`\n\n"
        f"Corpus outcome: `{summary['corpus_outcome']}`\n"
    )


def _source_page_record(page: Mapping[str, object]) -> dict[str, object]:
    return {
        key: page[key]
        for key in (
            "page_number",
            "pdf_page_index",
            "profiles",
            "native_character_count",
            "ocr_character_count",
            "native_line_count",
            "ocr_line_count",
            "native_block_count",
            "image_count",
            "figure_candidate_count",
            "table_candidate_count",
            "equation_candidate_count",
            "greek_math_symbol_proxy_count",
            "suspected_multi_column_layout",
            "review_priority",
        )
    }


def _deterministic_ocr_files(root: Path) -> tuple[Path, ...]:
    files = [
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file()
        and path.name
        in {
            "ocr_document.json",
            "ocr_manifest.json",
            "raw_ocr.txt",
            "normalized_ocr.txt",
            "provenance.json",
            "rendered_page.png",
        }
    ]
    return tuple(sorted(files, key=lambda path: path.as_posix()))


def _render_page(
    source: Path,
    pdf_page_index: int,
    output: Path,
    *,
    overwrite: bool,
) -> None:
    if output.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(source) as document:
        page = document.load_page(pdf_page_index)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        pixmap.save(output)


def _validate_artifacts(
    ocr_artifact: Mapping[str, object],
    ocr_manifest: Mapping[str, object],
) -> None:
    artifact_validation = validate_ocr_artifact(ocr_artifact)
    if not artifact_validation.valid:
        raise ValueError(f"Invalid OCR artifact: {artifact_validation.errors}")
    manifest_validation = validate_ocr_manifest(ocr_manifest)
    if not manifest_validation.valid:
        raise ValueError(f"Invalid OCR manifest: {manifest_validation.errors}")


def _entity_page_number(entity: Mapping[str, object]) -> int | None:
    page_refs = entity.get("page_refs")
    if isinstance(page_refs, Sequence) and not isinstance(page_refs, str | bytes):
        for value in page_refs:
            if isinstance(value, int):
                return value
    source_span = entity.get("source_span")
    if isinstance(source_span, Mapping):
        page_start = source_span.get("page_start")
        if isinstance(page_start, int):
            return page_start
    return None


def _formula_signal_count(text: str) -> int:
    return len(re.findall(r"[A-Za-zα-ωΑ-Ω]\s*=\s*|[∑√∫≤≥±]", text))


def _table_signal_count(text: str) -> int:
    return len(re.findall(r"\b(table|row|column|tabular)\b", text, re.I))


def _greek_symbol_count(text: str) -> int:
    return len(re.findall(r"[α-ωΑ-Ω]", text))


def _symbol_proxy_count(text: str) -> int:
    return len(re.findall(r"[α-ωΑ-Ω±≤≥≈∞∑√∫°×÷−μ=]", text))


def _looks_multi_column(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    return len(lines) >= 8 and max((len(line) for line in lines), default=0) > 90


def _coverage_gap(native_text: str, ocr_text: str) -> float:
    if not native_text:
        return 0.0 if not ocr_text else 1.0
    return abs(len(native_text) - len(ocr_text)) / max(len(native_text), 1)


def _line_count(text: str) -> int:
    return len([line for line in text.splitlines() if line.strip()])


def _write_json(path: Path, data: object, *, overwrite: bool) -> None:
    _write_text(
        path,
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        overwrite=overwrite,
    )


def _write_text(path: Path, text: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_json(path: str | Path) -> Mapping[str, object]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return data


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical_json_sha256(data: Mapping[str, object]) -> str:
    encoded = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).encode(
        "utf-8"
    )
    return sha256(encoded + b"\n").hexdigest()


def _safe_child(root: Path, *parts: str) -> Path:
    base = root.resolve()
    target = base.joinpath(*parts).resolve()
    target.relative_to(base)
    return target


def _sequence_of_mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _parser_version(
    *,
    native_document: Mapping[str, object],
    structured_document: Mapping[str, object],
) -> str:
    parser = native_document.get("parser")
    if isinstance(parser, Mapping):
        parser_version = parser.get("version")
        if isinstance(parser_version, str):
            return parser_version
    version = native_document.get("parser_version")
    if isinstance(version, str) and version:
        return version
    structured_version = structured_document.get("parser_version")
    return structured_version if isinstance(structured_version, str) else ""


def _string_list(data: Mapping[str, object], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return []
    return [str(item) for item in value]


def _int_value(value: object, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def copy_verified_ocr_run(
    source_dir: str | Path,
    canonical_dir: str | Path,
) -> None:
    """Copy one deterministic OCR run into the canonical local OCR directory."""
    source = Path(source_dir)
    target = Path(canonical_dir)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


__all__ = [
    "EXECUTION_SCHEMA_NAME",
    "EXECUTION_SCHEMA_VERSION",
    "OWNER_REVIEW_REQUIRED",
    "OCR_OUTPUT_NONDETERMINISTIC",
    "REVIEW_CHECK_FIELDS",
    "build_engineering_ocr_execution_package",
    "compare_engineering_ocr_determinism",
    "copy_verified_ocr_run",
    "sanitized_summary_fixture",
]
