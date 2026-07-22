"""Read-only inventory for an approved local pilot PDF corpus.

This module records deterministic metadata and planning signals only. It does
not evaluate parser/source accuracy, run OCR, modify PDFs, extract images, call
external APIs, or write reports.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]

PASS = "PASS"
REVIEW = "REVIEW"
FAIL = "FAIL"

INVENTORY_SCOPE = "approved_pilot_corpus_inventory_planning_only"
ACCURACY_DISCLAIMER = (
    "Phase 13I-b1 is inventory and representative-page planning only. Source "
    "accuracy was not evaluated; OCR was not run; PDFs were not modified."
)
APPROVED_EVALUATION_ROLES = (
    "ordinary_text",
    "reading_order",
    "multi_column",
    "section_hierarchy",
    "numbered_clause",
    "table",
    "multi_page_table",
    "figure_caption",
    "equation",
    "admonition",
    "procedure",
    "cross_reference",
    "appendix_or_annex",
    "landscape",
    "rotated_page",
    "blank_or_low_text",
    "dense_text",
    "mixed_layout",
    "header_footer",
    "printed_page_label",
)
EXPECTED_DOCUMENT_PATTERNS = {
    "faa_order_4040_26b": ("faa", "4040", "26b"),
    "flight_test_rm_ag_300": ("flight", "test", "300"),
    "introduction_flight_test_engineering": ("introduction", "flight", "test"),
    "mil_std_882e": ("mil", "std", "882e"),
    "cirrus_sr22_maintenance_manual": ("cirrus", "sr22", "maintenance"),
    "airworthiness_certification_operations": (
        "airworthiness",
        "certification",
        "operations",
    ),
    "aircraft_system_safety": ("aircraft", "system", "safety"),
    "aircraft_stability_control": ("stability", "control", "5070"),
}


@dataclass(frozen=True)
class PilotCorpusIssue:
    """One deterministic inventory issue."""

    code: str
    severity: str
    message: str
    filename: str | None = None


@dataclass(frozen=True)
class RepresentativePageSelection:
    """One proposed representative page for later owner approval."""

    pdf_page_index: int
    page_number: int
    printed_page_label: str | None
    evaluation_roles: tuple[str, ...]
    priority: str
    selection_reason: tuple[str, ...]
    selection_status: str = "proposed"


@dataclass(frozen=True)
class PilotCorpusFile:
    """Filesystem identity for one local PDF."""

    filename: str
    relative_path: str
    normalized_display_title: str
    size_bytes: int
    size_mib: float
    sha256: str
    git_ignored: bool | None
    git_tracked: bool
    expected_document_key: str | None
    duplicate_hash_group: str | None = None


@dataclass(frozen=True)
class PilotDocumentPageProfile:
    """Metadata-only page profile."""

    pdf_page_index: int
    page_number: int
    printed_page_label: str | None
    width: float
    height: float
    rotation: int
    orientation: str
    unusual_page_size: bool
    blank_or_low_text_candidate: bool
    foldout_or_oversized_candidate: bool
    extracted_character_count: int
    word_count: int
    line_count: int
    text_block_count: int
    image_count: int
    text_mode: str
    layout_classification: str
    special_content_indicators: tuple[str, ...] = ()


@dataclass(frozen=True)
class PilotDocumentInventory:
    """Inventory and proposed representative pages for one document."""

    document_key: str
    filename: str
    title: str
    file: PilotCorpusFile
    page_count: int
    access_status: str
    encrypted: bool
    password_required: bool
    extraction_permitted: bool | None
    metadata_summary: Mapping[str, str | None]
    page_profiles: tuple[PilotDocumentPageProfile, ...]
    outline_summary: Mapping[str, object]
    page_label_summary: Mapping[str, object]
    text_mode: str
    orientation_summary: Mapping[str, int]
    layout_summary: Mapping[str, int]
    text_density_summary: Mapping[str, object]
    special_content_summary: Mapping[str, tuple[int, ...]]
    representative_pages: tuple[RepresentativePageSelection, ...]
    pilot_roles: tuple[str, ...]
    likely_parsing_challenges: tuple[str, ...]
    review_burden: str
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class PilotCorpusInventoryResult:
    """Complete read-only pilot corpus inventory result."""

    corpus_path_label: str
    document_count: int
    expected_document_count: int
    outcome: str
    duplicate_hashes: Mapping[str, tuple[str, ...]]
    missing_expected_documents: tuple[str, ...]
    unexpected_documents: tuple[str, ...]
    git_ignore_summary: Mapping[str, int]
    total_pages: int
    total_size_bytes: int
    text_mode_counts: Mapping[str, int]
    orientation_counts: Mapping[str, int]
    proposed_page_count: int
    priority_counts: Mapping[str, int]
    documents: tuple[PilotDocumentInventory, ...]
    issues: tuple[PilotCorpusIssue, ...] = ()
    accuracy_evaluated: bool = False
    ocr_performed: bool = False
    pdfs_modified: bool = False
    aviationrag_modified: bool = False
    owner_approval_required: bool = True
    scope: str = INVENTORY_SCOPE
    disclaimer: str = ACCURACY_DISCLAIMER


def inventory_pilot_corpus(
    input_dir: str | Path,
    *,
    expected_document_count: int = 8,
    max_pages_per_document: int = 10,
) -> PilotCorpusInventoryResult:
    """Inventory local PDFs and propose representative pages without writes."""
    root = Path(input_dir)
    corpus_label = _path_label(root)
    issues: list[PilotCorpusIssue] = []
    if not root.exists() or not root.is_dir():
        issue = PilotCorpusIssue(
            code="INPUT_DIR_MISSING",
            severity="error",
            message="Input directory does not exist or is not a directory.",
        )
        return PilotCorpusInventoryResult(
            corpus_path_label=corpus_label,
            document_count=0,
            expected_document_count=expected_document_count,
            outcome=FAIL,
            duplicate_hashes={},
            missing_expected_documents=tuple(sorted(EXPECTED_DOCUMENT_PATTERNS)),
            unexpected_documents=(),
            git_ignore_summary={"ignored": 0, "not_ignored": 0, "tracked": 0},
            total_pages=0,
            total_size_bytes=0,
            text_mode_counts={},
            orientation_counts={},
            proposed_page_count=0,
            priority_counts={},
            documents=(),
            issues=(issue,),
        )

    pdf_paths = tuple(sorted(root.glob("*.pdf"), key=lambda path: path.name.casefold()))
    files = [_inventory_file(path) for path in pdf_paths]
    duplicate_hashes = _duplicate_hashes(files)
    expected_by_file = {item.filename: item.expected_document_key for item in files}
    matched_keys = {key for key in expected_by_file.values() if key is not None}
    missing_expected = tuple(sorted(set(EXPECTED_DOCUMENT_PATTERNS) - matched_keys))
    unexpected = tuple(
        sorted(item.filename for item in files if item.expected_document_key is None)
    )

    for _hash_group, filenames in duplicate_hashes.items():
        issues.append(
            PilotCorpusIssue(
                code="DUPLICATE_HASH",
                severity="warning",
                message="Two or more PDFs share the same SHA-256.",
                filename=", ".join(filenames),
            )
        )
    if len(files) != expected_document_count:
        issues.append(
            PilotCorpusIssue(
                code="PDF_COUNT_MISMATCH",
                severity="warning",
                message=(
                    f"Expected {expected_document_count} PDFs but found {len(files)}."
                ),
            )
        )
    for filename in unexpected:
        issues.append(
            PilotCorpusIssue(
                code="UNEXPECTED_DOCUMENT",
                severity="warning",
                message="PDF filename does not match the expected pilot corpus.",
                filename=filename,
            )
        )
    for key in missing_expected:
        issues.append(
            PilotCorpusIssue(
                code="EXPECTED_DOCUMENT_MISSING",
                severity="warning",
                message="An expected pilot document pattern was not matched.",
                filename=key,
            )
        )

    documents: list[PilotDocumentInventory] = []
    for file_info in files:
        document = _inspect_pdf_document(
            root / file_info.filename,
            file_info,
            max_pages_per_document=max_pages_per_document,
        )
        documents.append(document)
        if document.access_status == "unreadable":
            issues.append(
                PilotCorpusIssue(
                    code="PDF_UNREADABLE",
                    severity="error",
                    message="PDF could not be opened for metadata inspection.",
                    filename=file_info.filename,
                )
            )
        elif document.access_status != "readable":
            issues.append(
                PilotCorpusIssue(
                    code="PDF_ACCESS_REVIEW",
                    severity="warning",
                    message="PDF access status requires review.",
                    filename=file_info.filename,
                )
            )
        if document.text_mode == "uncertain":
            issues.append(
                PilotCorpusIssue(
                    code="UNCERTAIN_TEXT_MODE",
                    severity="warning",
                    message=(
                        "Document text/scanned classification is uncertain; "
                        "manual owner review is required."
                    ),
                    filename=file_info.filename,
                )
            )
        if document.text_mode == "scanned_image":
            issues.append(
                PilotCorpusIssue(
                    code="SCANNED_IMAGE_LIKELY",
                    severity="warning",
                    message=(
                        "Document appears scan-like; OCR remains out of scope "
                        "without explicit future approval."
                    ),
                    filename=file_info.filename,
                )
            )

    git_ignore_summary = _git_ignore_summary(files)
    for item in files:
        if item.git_tracked:
            issues.append(
                PilotCorpusIssue(
                    code="PDF_TRACKED",
                    severity="error",
                    message="PDF is tracked by Git and must not be committed.",
                    filename=item.filename,
                )
            )
        if item.git_ignored is False:
            issues.append(
                PilotCorpusIssue(
                    code="PDF_NOT_IGNORED",
                    severity="error",
                    message="PDF is not ignored by Git.",
                    filename=item.filename,
                )
            )

    sorted_documents = tuple(sorted(documents, key=lambda doc: doc.filename.casefold()))
    outcome = _overall_outcome(issues)
    return PilotCorpusInventoryResult(
        corpus_path_label=corpus_label,
        document_count=len(files),
        expected_document_count=expected_document_count,
        outcome=outcome,
        duplicate_hashes=duplicate_hashes,
        missing_expected_documents=missing_expected,
        unexpected_documents=unexpected,
        git_ignore_summary=git_ignore_summary,
        total_pages=sum(document.page_count for document in sorted_documents),
        total_size_bytes=sum(item.size_bytes for item in files),
        text_mode_counts=dict(
            sorted(Counter(document.text_mode for document in sorted_documents).items())
        ),
        orientation_counts=_aggregate_orientation_counts(sorted_documents),
        proposed_page_count=sum(
            len(document.representative_pages) for document in sorted_documents
        ),
        priority_counts=_aggregate_priority_counts(sorted_documents),
        documents=sorted_documents,
        issues=tuple(_sort_issues(issues)),
    )


def propose_representative_pages(
    inventory: PilotDocumentInventory,
    *,
    max_pages: int = 10,
) -> tuple[RepresentativePageSelection, ...]:
    """Propose deterministic representative pages for owner review."""
    if max_pages <= 0 or not inventory.page_profiles:
        return ()
    candidates: dict[int, tuple[int, PilotDocumentPageProfile, tuple[str, ...]]] = {}

    def add(
        profile: PilotDocumentPageProfile | None,
        score: int,
        reasons: Sequence[str],
    ) -> None:
        if profile is None:
            return
        existing = candidates.get(profile.pdf_page_index)
        reason_tuple = tuple(dict.fromkeys(reasons))
        if existing is None or score > existing[0]:
            candidates[profile.pdf_page_index] = (score, profile, reason_tuple)
        elif existing[0] == score:
            candidates[profile.pdf_page_index] = (
                score,
                profile,
                tuple(dict.fromkeys((*existing[2], *reason_tuple))),
            )

    profiles = inventory.page_profiles
    ordinary = [page for page in profiles if _is_ordinary_page(page)]
    add(ordinary[0] if ordinary else profiles[0], 100, ("ordinary_baseline",))
    add(
        ordinary[len(ordinary) // 2] if ordinary else profiles[len(profiles) // 2],
        95,
        ("ordinary_middle_coverage",),
    )
    add(profiles[0], 70, ("front_matter_or_start",))
    add(profiles[-1], 70, ("document_end_coverage",))

    for layout in ("two_column_likely", "multi_column_or_complex"):
        add(
            _first_profile(
                profiles,
                lambda page, layout=layout: page.layout_classification == layout,
            ),
            90,
            (layout, "reading_order_review"),
        )
    for orientation in ("landscape", "rotated_page"):
        add(
            _first_profile(
                profiles,
                lambda page, orientation=orientation: (
                    page.orientation == orientation or page.rotation != 0
                ),
            ),
            86,
            (orientation,),
        )
    for indicator in (
        "table",
        "figure_caption",
        "equation",
        "admonition",
        "cross_reference",
        "appendix_or_annex",
        "procedure",
        "numbered_clause",
    ):
        add(
            _first_profile(
                profiles,
                lambda page, indicator=indicator: (
                    indicator in page.special_content_indicators
                ),
            ),
            82,
            (indicator,),
        )
    add(
        _first_profile(profiles, lambda page: page.blank_or_low_text_candidate),
        75,
        ("blank_or_low_text",),
    )
    add(
        max(
            profiles,
            key=lambda page: (page.extracted_character_count, -page.pdf_page_index),
        ),
        72,
        ("dense_text",),
    )

    selected = sorted(
        candidates.values(),
        key=lambda item: (-item[0], item[1].pdf_page_index),
    )[:max_pages]
    selections = [
        _selection_from_profile(profile, reasons, index)
        for index, (_score, profile, reasons) in enumerate(selected)
    ]
    return tuple(sorted(selections, key=lambda item: item.pdf_page_index))


def pilot_corpus_inventory_result_to_dict(
    result: PilotCorpusInventoryResult,
    *,
    include_hashes: bool = True,
) -> dict[str, Any]:
    """Convert inventory result to deterministic JSON-safe data."""
    return {
        "scope": result.scope,
        "disclaimer": result.disclaimer,
        "accuracy_evaluated": result.accuracy_evaluated,
        "ocr_performed": result.ocr_performed,
        "pdfs_modified": result.pdfs_modified,
        "aviationrag_modified": result.aviationrag_modified,
        "owner_approval_required": result.owner_approval_required,
        "corpus_path_label": result.corpus_path_label,
        "document_count": result.document_count,
        "expected_document_count": result.expected_document_count,
        "outcome": result.outcome,
        "duplicate_hashes": {
            key: list(value) for key, value in sorted(result.duplicate_hashes.items())
        }
        if include_hashes
        else {},
        "missing_expected_documents": list(result.missing_expected_documents),
        "unexpected_documents": list(result.unexpected_documents),
        "git_ignore_summary": dict(result.git_ignore_summary),
        "total_pages": result.total_pages,
        "total_size_bytes": result.total_size_bytes,
        "text_mode_counts": dict(result.text_mode_counts),
        "orientation_counts": dict(result.orientation_counts),
        "proposed_page_count": result.proposed_page_count,
        "priority_counts": dict(result.priority_counts),
        "issue_count": len(result.issues),
        "error_count": sum(1 for issue in result.issues if issue.severity == "error"),
        "warning_count": sum(
            1 for issue in result.issues if issue.severity == "warning"
        ),
        "issues": [_issue_to_dict(issue) for issue in result.issues],
        "documents": [
            _document_to_dict(document, include_hashes=include_hashes)
            for document in result.documents
        ],
    }


def pilot_corpus_inventory_result_to_json(
    result: PilotCorpusInventoryResult,
    *,
    include_hashes: bool = True,
) -> str:
    """Serialize inventory result as deterministic JSON with a final newline."""
    return (
        json.dumps(
            pilot_corpus_inventory_result_to_dict(
                result,
                include_hashes=include_hashes,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _inspect_pdf_document(
    path: Path,
    file_info: PilotCorpusFile,
    *,
    max_pages_per_document: int,
) -> PilotDocumentInventory:
    try:
        document = fitz.open(path)
    except Exception:
        return _unreadable_document(file_info)
    with document:
        encrypted = bool(document.is_encrypted)
        password_required = bool(document.needs_pass)
        extraction_permitted = _extraction_permitted(document)
        if password_required:
            return _restricted_document(file_info, encrypted, password_required)
        page_profiles = tuple(
            _profile_page(document, index) for index in range(document.page_count)
        )
        outline_summary = _outline_summary(document)
        page_label_summary = _page_label_summary(page_profiles)
        representative = propose_representative_pages(
            _document_without_representative_pages(
                file_info,
                document,
                page_profiles,
                encrypted,
                password_required,
                extraction_permitted,
                outline_summary,
                page_label_summary,
            ),
            max_pages=max_pages_per_document,
        )
        return _document_with_profiles(
            file_info,
            document,
            page_profiles,
            encrypted,
            password_required,
            extraction_permitted,
            outline_summary,
            page_label_summary,
            representative,
        )


def _profile_page(
    document: fitz.Document, pdf_page_index: int
) -> PilotDocumentPageProfile:
    page = document.load_page(pdf_page_index)
    rect = page.rect
    width = round(float(rect.width), 3)
    height = round(float(rect.height), 3)
    rotation = int(page.rotation or 0)
    text = page.get_text("text") or ""
    words = _word_count(text)
    lines = sum(1 for line in text.splitlines() if line.strip())
    blocks = _text_blocks(page)
    image_count = len(page.get_images(full=False))
    character_count = len(text.strip())
    special = _special_indicators(text)
    orientation = _orientation(width, height, rotation)
    low_text = character_count < 50
    profile = PilotDocumentPageProfile(
        pdf_page_index=pdf_page_index,
        page_number=pdf_page_index + 1,
        printed_page_label=_page_label(page),
        width=width,
        height=height,
        rotation=rotation,
        orientation=orientation,
        unusual_page_size=_unusual_page_size(width, height),
        blank_or_low_text_candidate=low_text,
        foldout_or_oversized_candidate=_foldout_or_oversized(width, height),
        extracted_character_count=character_count,
        word_count=words,
        line_count=lines,
        text_block_count=len(blocks),
        image_count=image_count,
        text_mode=_page_text_mode(character_count, words, image_count),
        layout_classification=_layout_classification(
            width, height, blocks, image_count
        ),
        special_content_indicators=special,
    )
    return profile


def _document_with_profiles(
    file_info: PilotCorpusFile,
    document: fitz.Document,
    page_profiles: tuple[PilotDocumentPageProfile, ...],
    encrypted: bool,
    password_required: bool,
    extraction_permitted: bool | None,
    outline_summary: Mapping[str, object],
    page_label_summary: Mapping[str, object],
    representative_pages: tuple[RepresentativePageSelection, ...],
) -> PilotDocumentInventory:
    text_density = _text_density_summary(page_profiles)
    special_summary = _special_content_summary(page_profiles)
    title = _document_title(file_info, document.metadata)
    roles = tuple(
        sorted(
            {role for page in representative_pages for role in page.evaluation_roles}
        )
    )
    return PilotDocumentInventory(
        document_key=(
            file_info.expected_document_key or _document_key(file_info.filename)
        ),
        filename=file_info.filename,
        title=title,
        file=file_info,
        page_count=document.page_count,
        access_status=_access_status(
            encrypted,
            password_required,
            extraction_permitted,
        ),
        encrypted=encrypted,
        password_required=password_required,
        extraction_permitted=extraction_permitted,
        metadata_summary=_metadata_summary(document.metadata),
        page_profiles=page_profiles,
        outline_summary=outline_summary,
        page_label_summary=page_label_summary,
        text_mode=_document_text_mode(page_profiles),
        orientation_summary=dict(
            sorted(Counter(page.orientation for page in page_profiles).items())
        ),
        layout_summary=dict(
            sorted(
                Counter(page.layout_classification for page in page_profiles).items()
            )
        ),
        text_density_summary=text_density,
        special_content_summary=special_summary,
        representative_pages=representative_pages,
        pilot_roles=roles,
        likely_parsing_challenges=_challenges(
            page_profiles,
            special_summary,
        ),
        review_burden=_review_burden(page_profiles, representative_pages),
        limitations=_limitations(page_profiles, extraction_permitted),
    )


def _document_without_representative_pages(
    file_info: PilotCorpusFile,
    document: fitz.Document,
    page_profiles: tuple[PilotDocumentPageProfile, ...],
    encrypted: bool,
    password_required: bool,
    extraction_permitted: bool | None,
    outline_summary: Mapping[str, object],
    page_label_summary: Mapping[str, object],
) -> PilotDocumentInventory:
    return _document_with_profiles(
        file_info,
        document,
        page_profiles,
        encrypted,
        password_required,
        extraction_permitted,
        outline_summary,
        page_label_summary,
        (),
    )


def _unreadable_document(file_info: PilotCorpusFile) -> PilotDocumentInventory:
    return PilotDocumentInventory(
        document_key=(
            file_info.expected_document_key or _document_key(file_info.filename)
        ),
        filename=file_info.filename,
        title=file_info.normalized_display_title,
        file=file_info,
        page_count=0,
        access_status="unreadable",
        encrypted=False,
        password_required=False,
        extraction_permitted=None,
        metadata_summary={},
        page_profiles=(),
        outline_summary={"outline_present": False, "total_outline_entries": 0},
        page_label_summary={"labels_present": False},
        text_mode="uncertain",
        orientation_summary={},
        layout_summary={},
        text_density_summary={},
        special_content_summary={},
        representative_pages=(),
        pilot_roles=(),
        likely_parsing_challenges=("unreadable_pdf",),
        review_burden="high",
        limitations=("PDF could not be opened for metadata inspection.",),
    )


def _restricted_document(
    file_info: PilotCorpusFile,
    encrypted: bool,
    password_required: bool,
) -> PilotDocumentInventory:
    base = _unreadable_document(file_info)
    return PilotDocumentInventory(
        **{
            **base.__dict__,
            "access_status": "restricted",
            "encrypted": encrypted,
            "password_required": password_required,
            "likely_parsing_challenges": ("password_required",),
            "limitations": (
                "PDF password is required; access controls were not bypassed.",
            ),
        }
    )


def _inventory_file(path: Path) -> PilotCorpusFile:
    stat = path.stat()
    digest = _sha256_file(path)
    expected_key = _match_expected_document(path.name)
    return PilotCorpusFile(
        filename=path.name,
        relative_path=_path_label(path),
        normalized_display_title=_display_title(path.name),
        size_bytes=stat.st_size,
        size_mib=round(stat.st_size / (1024 * 1024), 3),
        sha256=digest,
        git_ignored=_git_check_ignore(path),
        git_tracked=_git_is_tracked(path),
        expected_document_key=expected_key,
    )


def _document_to_dict(
    document: PilotDocumentInventory,
    *,
    include_hashes: bool,
) -> dict[str, Any]:
    file_data = {
        "filename": document.file.filename,
        "relative_path": document.file.relative_path,
        "normalized_display_title": document.file.normalized_display_title,
        "size_bytes": document.file.size_bytes,
        "size_mib": document.file.size_mib,
        "git_ignored": document.file.git_ignored,
        "git_tracked": document.file.git_tracked,
        "expected_document_key": document.file.expected_document_key,
        "duplicate_hash_group": document.file.duplicate_hash_group,
    }
    if include_hashes:
        file_data["sha256"] = document.file.sha256
    return {
        "document_key": document.document_key,
        "filename": document.filename,
        "title": document.title,
        "file": file_data,
        "page_count": document.page_count,
        "access_status": document.access_status,
        "encrypted": document.encrypted,
        "password_required": document.password_required,
        "extraction_permitted": document.extraction_permitted,
        "metadata_summary": dict(document.metadata_summary),
        "outline_summary": _jsonable_mapping(document.outline_summary),
        "page_label_summary": _jsonable_mapping(document.page_label_summary),
        "text_mode": document.text_mode,
        "orientation_summary": dict(document.orientation_summary),
        "layout_summary": dict(document.layout_summary),
        "text_density_summary": _jsonable_mapping(document.text_density_summary),
        "special_content_summary": {
            key: list(value)
            for key, value in sorted(document.special_content_summary.items())
        },
        "representative_pages": [
            _representative_page_to_dict(page) for page in document.representative_pages
        ],
        "pilot_roles": list(document.pilot_roles),
        "likely_parsing_challenges": list(document.likely_parsing_challenges),
        "review_burden": document.review_burden,
        "limitations": list(document.limitations),
        "page_profiles": [
            _page_profile_to_dict(page) for page in document.page_profiles
        ],
    }


def _page_profile_to_dict(page: PilotDocumentPageProfile) -> dict[str, Any]:
    return {
        "pdf_page_index": page.pdf_page_index,
        "page_number": page.page_number,
        "printed_page_label": page.printed_page_label,
        "width": page.width,
        "height": page.height,
        "rotation": page.rotation,
        "orientation": page.orientation,
        "unusual_page_size": page.unusual_page_size,
        "blank_or_low_text_candidate": page.blank_or_low_text_candidate,
        "foldout_or_oversized_candidate": page.foldout_or_oversized_candidate,
        "extracted_character_count": page.extracted_character_count,
        "word_count": page.word_count,
        "line_count": page.line_count,
        "text_block_count": page.text_block_count,
        "image_count": page.image_count,
        "text_mode": page.text_mode,
        "layout_classification": page.layout_classification,
        "special_content_indicators": list(page.special_content_indicators),
    }


def _representative_page_to_dict(page: RepresentativePageSelection) -> dict[str, Any]:
    return {
        "pdf_page_index": page.pdf_page_index,
        "page_number": page.page_number,
        "printed_page_label": page.printed_page_label,
        "evaluation_roles": list(page.evaluation_roles),
        "priority": page.priority,
        "selection_reason": list(page.selection_reason),
        "selection_status": page.selection_status,
    }


def _issue_to_dict(issue: PilotCorpusIssue) -> dict[str, str | None]:
    return {
        "code": issue.code,
        "severity": issue.severity,
        "message": issue.message,
        "filename": issue.filename,
    }


def _selection_from_profile(
    profile: PilotDocumentPageProfile,
    reasons: Sequence[str],
    rank: int,
) -> RepresentativePageSelection:
    roles = _roles_for_profile(profile, reasons)
    priority = "P0" if rank < 4 else "P1" if rank < 8 else "P2"
    return RepresentativePageSelection(
        pdf_page_index=profile.pdf_page_index,
        page_number=profile.page_number,
        printed_page_label=profile.printed_page_label,
        evaluation_roles=roles,
        priority=priority,
        selection_reason=tuple(sorted(set(reasons))),
    )


def _roles_for_profile(
    profile: PilotDocumentPageProfile,
    reasons: Sequence[str],
) -> tuple[str, ...]:
    roles: set[str] = set()
    if _is_ordinary_page(profile):
        roles.add("ordinary_text")
    if profile.layout_classification == "two_column_likely":
        roles.update({"reading_order", "multi_column"})
    if profile.layout_classification == "multi_column_or_complex":
        roles.update({"reading_order", "mixed_layout"})
    if profile.orientation == "landscape":
        roles.add("landscape")
    if profile.rotation != 0:
        roles.add("rotated_page")
    if profile.blank_or_low_text_candidate:
        roles.add("blank_or_low_text")
    if profile.extracted_character_count > 3500:
        roles.add("dense_text")
    if profile.printed_page_label is not None:
        roles.add("printed_page_label")
    roles.update(
        indicator
        for indicator in profile.special_content_indicators
        if indicator in APPROVED_EVALUATION_ROLES
    )
    roles.update(role for role in reasons if role in APPROVED_EVALUATION_ROLES)
    if not roles:
        roles.add("ordinary_text")
    return tuple(sorted(roles))


def _first_profile(
    profiles: Sequence[PilotDocumentPageProfile],
    predicate: Any,
) -> PilotDocumentPageProfile | None:
    for profile in profiles:
        if predicate(profile):
            return profile
    return None


def _is_ordinary_page(page: PilotDocumentPageProfile) -> bool:
    return (
        page.text_mode == "native_like"
        and page.orientation == "portrait"
        and page.layout_classification == "single_column_likely"
        and not page.blank_or_low_text_candidate
        and len(page.special_content_indicators) <= 1
    )


def _access_status(
    encrypted: bool,
    password_required: bool,
    extraction_permitted: bool | None,
) -> str:
    if password_required:
        return "restricted"
    if encrypted:
        return "encrypted_readable"
    if extraction_permitted is False:
        return "restricted"
    return "readable"


def _extraction_permitted(document: fitz.Document) -> bool | None:
    try:
        permissions = int(document.permissions)
    except Exception:
        return None
    copy_permission = int(getattr(fitz, "PDF_PERM_COPY", 16))
    accessibility_permission = int(getattr(fitz, "PDF_PERM_ACCESSIBILITY", 512))
    if permissions in (-1, 0):
        return permissions == -1
    return bool(permissions & (copy_permission | accessibility_permission))


def _metadata_summary(metadata: Mapping[str, Any]) -> dict[str, str | None]:
    return {
        "title_present": "yes" if _string_or_none(metadata.get("title")) else "no",
        "author_present": "yes" if _string_or_none(metadata.get("author")) else "no",
        "subject_present": "yes" if _string_or_none(metadata.get("subject")) else "no",
        "producer_present": (
            "yes" if _string_or_none(metadata.get("producer")) else "no"
        ),
        "creator_present": "yes" if _string_or_none(metadata.get("creator")) else "no",
    }


def _document_title(file_info: PilotCorpusFile, metadata: Mapping[str, Any]) -> str:
    title = _string_or_none(metadata.get("title"))
    if title:
        return title
    return file_info.normalized_display_title


def _outline_summary(document: fitz.Document) -> dict[str, object]:
    try:
        toc = document.get_toc(simple=True)
    except Exception:
        return {
            "outline_present": False,
            "top_level_outline_count": 0,
            "total_outline_entries": 0,
            "max_nesting_depth": 0,
            "invalid_target_count": 0,
        }
    levels = [int(entry[0]) for entry in toc if entry]
    pages = [
        int(entry[2]) for entry in toc if len(entry) >= 3 and isinstance(entry[2], int)
    ]
    return {
        "outline_present": bool(toc),
        "top_level_outline_count": sum(1 for level in levels if level == 1),
        "total_outline_entries": len(toc),
        "max_nesting_depth": max(levels) if levels else 0,
        "invalid_target_count": sum(
            1 for page in pages if page < 1 or page > document.page_count
        ),
    }


def _page_label_summary(
    profiles: Sequence[PilotDocumentPageProfile],
) -> dict[str, object]:
    labels = [
        profile.printed_page_label for profile in profiles if profile.printed_page_label
    ]
    counts = Counter(labels)
    return {
        "labels_present": bool(labels),
        "labeled_page_count": len(labels),
        "duplicate_label_count": sum(1 for count in counts.values() if count > 1),
        "label_styles": tuple(_label_styles(labels)),
        "sample_labels": tuple(labels[:5]),
    }


def _page_label(page: fitz.Page) -> str | None:
    try:
        label = page.get_label()
    except Exception:
        return None
    return _string_or_none(label)


def _label_styles(labels: Sequence[str]) -> list[str]:
    styles: set[str] = set()
    for label in labels:
        if re.fullmatch(r"\d+", label):
            styles.add("arabic")
        elif re.fullmatch(r"[ivxlcdmIVXLCDM]+", label):
            styles.add("roman")
        elif re.fullmatch(r"[A-Za-z]+-\d+", label):
            styles.add("appendix-style")
        elif re.fullmatch(r"\d+-\d+", label):
            styles.add("chapter-page")
        else:
            styles.add("mixed")
    return sorted(styles)


def _text_density_summary(
    profiles: Sequence[PilotDocumentPageProfile],
) -> dict[str, object]:
    char_counts = [page.extracted_character_count for page in profiles]
    if not char_counts:
        return {
            "median_characters_per_page": 0,
            "min_characters_per_page": 0,
            "max_characters_per_page": 0,
            "low_text_pages": (),
            "high_text_pages": (),
        }
    sorted_counts = sorted(char_counts)
    median = sorted_counts[len(sorted_counts) // 2]
    high_threshold = max(3500, int(median * 1.75))
    return {
        "median_characters_per_page": median,
        "min_characters_per_page": min(char_counts),
        "max_characters_per_page": max(char_counts),
        "low_text_pages": tuple(
            page.page_number for page in profiles if page.extracted_character_count < 50
        )[:20],
        "high_text_pages": tuple(
            page.page_number
            for page in profiles
            if page.extracted_character_count >= high_threshold
        )[:20],
    }


def _special_content_summary(
    profiles: Sequence[PilotDocumentPageProfile],
) -> dict[str, tuple[int, ...]]:
    summary: dict[str, tuple[int, ...]] = {}
    indicators = sorted(
        {
            indicator
            for page in profiles
            for indicator in page.special_content_indicators
        }
    )
    for indicator in indicators:
        summary[f"{indicator}_candidate_pages"] = tuple(
            page.page_number
            for page in profiles
            if indicator in page.special_content_indicators
        )[:20]
    return summary


def _challenges(
    profiles: Sequence[PilotDocumentPageProfile],
    special_summary: Mapping[str, Sequence[int]],
) -> tuple[str, ...]:
    challenges: set[str] = set()
    layout_counts = Counter(page.layout_classification for page in profiles)
    if layout_counts.get("two_column_likely", 0):
        challenges.add("two_column_reading_order")
    if layout_counts.get("multi_column_or_complex", 0):
        challenges.add("complex_layout")
    if any(page.orientation == "landscape" for page in profiles):
        challenges.add("landscape_pages")
    if any(page.rotation != 0 for page in profiles):
        challenges.add("rotated_pages")
    if any(page.text_mode == "scan_like" for page in profiles):
        challenges.add("scan_like_pages_without_ocr")
    for key in special_summary:
        challenges.add(key.removesuffix("_candidate_pages"))
    return tuple(sorted(challenges))


def _limitations(
    profiles: Sequence[PilotDocumentPageProfile],
    extraction_permitted: bool | None,
) -> tuple[str, ...]:
    limitations = [
        "Metrics are metadata and planning signals, not source-accuracy evidence.",
        "No OCR was run.",
        "No full extracted text is serialized.",
    ]
    if extraction_permitted is False:
        limitations.append("PDF extraction permission requires review.")
    if any(page.text_mode == "scan_like" for page in profiles):
        limitations.append("Scan-like pages require owner approval before OCR work.")
    return tuple(limitations)


def _review_burden(
    profiles: Sequence[PilotDocumentPageProfile],
    representative_pages: Sequence[RepresentativePageSelection],
) -> str:
    score = len(representative_pages)
    non_single_column = sum(
        1 for page in profiles if page.layout_classification != "single_column_likely"
    )
    score += non_single_column // 10
    score += (
        sum(1 for page in profiles if "equation" in page.special_content_indicators)
        // 10
    )
    table_pages = sum(
        1 for page in profiles if "table" in page.special_content_indicators
    )
    score += table_pages // 12
    score += sum(1 for page in profiles if page.text_mode != "native_like") // 8
    if score >= 18:
        return "high"
    if score >= 9:
        return "medium"
    return "low"


def _document_text_mode(profiles: Sequence[PilotDocumentPageProfile]) -> str:
    if not profiles:
        return "uncertain"
    counts = Counter(page.text_mode for page in profiles)
    substantive = len(profiles) - counts.get("blank_or_low_text", 0)
    if substantive <= 0:
        return "uncertain"
    native = counts.get("native_like", 0)
    scan = counts.get("scan_like", 0)
    if native / len(profiles) >= 0.7:
        return "native_text"
    if scan / len(profiles) >= 0.7:
        return "scanned_image"
    if native and scan:
        return "mixed"
    return "uncertain"


def _page_text_mode(characters: int, words: int, image_count: int) -> str:
    if characters < 15 and image_count == 0:
        return "blank_or_low_text"
    if characters < 50 and image_count > 0:
        return "scan_like"
    if characters >= 100 or words >= 20:
        return "native_like"
    return "uncertain"


def _layout_classification(
    width: float,
    height: float,
    blocks: Sequence[tuple[float, float, float, float]],
    image_count: int,
) -> str:
    if not blocks:
        return "full_page_table_or_figure" if image_count else "uncertain"
    if width > height and len(blocks) <= 3 and image_count:
        return "full_page_table_or_figure"
    centers = [((x0 + x1) / 2.0) / max(width, 1.0) for x0, _y0, x1, _y1 in blocks]
    left = sum(1 for center in centers if center < 0.45)
    right = sum(1 for center in centers if center > 0.55)
    wide = sum(1 for x0, _y0, x1, _y1 in blocks if (x1 - x0) / max(width, 1.0) > 0.72)
    if left >= 2 and right >= 2 and wide <= max(1, len(blocks) // 4):
        return "two_column_likely"
    if len(blocks) >= 18 or (width > height and len(blocks) >= 6):
        return "multi_column_or_complex"
    return "single_column_likely"


def _text_blocks(page: fitz.Page) -> tuple[tuple[float, float, float, float], ...]:
    try:
        raw_blocks = page.get_text("blocks") or []
    except Exception:
        return ()
    result: list[tuple[float, float, float, float]] = []
    for block in raw_blocks:
        if not isinstance(block, Sequence) or len(block) < 5:
            continue
        text = str(block[4] or "")
        if text.strip():
            result.append(
                (
                    float(block[0]),
                    float(block[1]),
                    float(block[2]),
                    float(block[3]),
                )
            )
    return tuple(result)


def _special_indicators(text: str) -> tuple[str, ...]:
    compact = " ".join(text.split())
    lower = compact.casefold()
    indicators: set[str] = set()
    if re.search(r"\btable\s+\w+", lower) or re.search(r"\S\s{2,}\S", text):
        indicators.add("table")
    if re.search(r"\b(fig\.?|figure)\s+\w+", lower):
        indicators.add("figure_caption")
    if re.search(r"[=∑√≤≥±≈≠]|\b(alpha|beta|gamma|theta|omega)\b", lower):
        indicators.add("equation")
    if re.search(r"\b(warning|caution|note|important|safety notice)\b", lower):
        indicators.add("admonition")
    if re.search(r"\b(appendix|annex)\b", lower):
        indicators.add("appendix_or_annex")
    if re.search(r"\b(see|refer to|in accordance with|section|paragraph)\b", lower):
        indicators.add("cross_reference")
    if re.search(r"\b(step|procedure|task|remove|install|inspect)\b", lower):
        indicators.add("procedure")
    if re.search(r"\b(shall|must|required|requirement)\b", lower):
        indicators.add("numbered_clause")
    return tuple(sorted(indicators))


def _orientation(width: float, height: float, rotation: int) -> str:
    if rotation % 180 != 0:
        return "rotated_page"
    tolerance = 0.03
    if width > height * (1 + tolerance):
        return "landscape"
    if height > width * (1 + tolerance):
        return "portrait"
    return "square_or_other"


def _unusual_page_size(width: float, height: float) -> bool:
    short, long = sorted((width, height))
    return short < 450 or short > 700 or long < 650 or long > 950


def _foldout_or_oversized(width: float, height: float) -> bool:
    return max(width, height) > 1000 or (width > height and width > 850)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _duplicate_hashes(files: Sequence[PilotCorpusFile]) -> dict[str, tuple[str, ...]]:
    by_hash: dict[str, list[str]] = defaultdict(list)
    for item in files:
        by_hash[item.sha256].append(item.filename)
    return {
        digest: tuple(sorted(names))
        for digest, names in sorted(by_hash.items())
        if len(names) > 1
    }


def _git_ignore_summary(files: Sequence[PilotCorpusFile]) -> dict[str, int]:
    return {
        "ignored": sum(1 for item in files if item.git_ignored is True),
        "not_ignored": sum(1 for item in files if item.git_ignored is False),
        "unknown": sum(1 for item in files if item.git_ignored is None),
        "tracked": sum(1 for item in files if item.git_tracked),
    }


def _git_check_ignore(path: Path) -> bool | None:
    rel = _path_label(path)
    try:
        completed = subprocess.run(
            ["git", "check-ignore", rel],
            check=False,
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
    except OSError:
        return None
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    return None


def _git_is_tracked(path: Path) -> bool:
    rel = _path_label(path)
    try:
        completed = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            check=False,
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
    except OSError:
        return False
    return completed.returncode == 0


def _aggregate_orientation_counts(
    documents: Sequence[PilotDocumentInventory],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for document in documents:
        counts.update(document.orientation_summary)
    return dict(sorted(counts.items()))


def _aggregate_priority_counts(
    documents: Sequence[PilotDocumentInventory],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for document in documents:
        counts.update(page.priority for page in document.representative_pages)
    return dict(sorted(counts.items()))


def _overall_outcome(issues: Sequence[PilotCorpusIssue]) -> str:
    if any(issue.severity == "error" for issue in issues):
        return FAIL
    if any(issue.severity == "warning" for issue in issues):
        return REVIEW
    return PASS


def _sort_issues(issues: Iterable[PilotCorpusIssue]) -> list[PilotCorpusIssue]:
    severity_order = {"error": 0, "warning": 1, "info": 2}
    return sorted(
        issues,
        key=lambda issue: (
            severity_order.get(issue.severity, 99),
            issue.code,
            issue.filename or "",
            issue.message,
        ),
    )


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        if path.parent.name:
            return f"{path.parent.name}/{path.name}"
        return path.name


def _display_title(filename: str) -> str:
    stem = Path(filename).stem.replace("_", " ").replace("-", " ")
    return " ".join(stem.split())


def _document_key(filename: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", Path(filename).stem.casefold()).strip("_")


def _match_expected_document(filename: str) -> str | None:
    normalized = _document_key(filename)
    matches = [
        key
        for key, parts in EXPECTED_DOCUMENT_PATTERNS.items()
        if all(part in normalized for part in parts)
    ]
    if len(matches) == 1:
        return matches[0]
    if {
        "flight_test_rm_ag_300",
        "introduction_flight_test_engineering",
    }.issubset(matches):
        return "introduction_flight_test_engineering"
    return matches[0] if matches else None


def _jsonable_mapping(mapping: Mapping[str, object]) -> dict[str, object]:
    return {key: _jsonable(value) for key, value in mapping.items()}


def _jsonable(value: object) -> object:
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _string_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


__all__ = [
    "ACCURACY_DISCLAIMER",
    "APPROVED_EVALUATION_ROLES",
    "FAIL",
    "INVENTORY_SCOPE",
    "PASS",
    "REVIEW",
    "PilotCorpusFile",
    "PilotCorpusInventoryResult",
    "PilotCorpusIssue",
    "PilotDocumentInventory",
    "PilotDocumentPageProfile",
    "RepresentativePageSelection",
    "inventory_pilot_corpus",
    "pilot_corpus_inventory_result_to_dict",
    "pilot_corpus_inventory_result_to_json",
    "propose_representative_pages",
]
