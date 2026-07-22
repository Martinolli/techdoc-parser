"""Fixture-only chunk quality evaluation.

The evaluator measures deterministic quality proxies from committed synthetic
fixtures. It does not prove source-page visual accuracy, OCR accuracy, semantic
accuracy, or real aviation-document correctness.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any

from techdoc_parser.chunking.semantic import create_semantic_chunks
from techdoc_parser.core.models import (
    Block,
    BoundingBox,
    Chunk,
    Document,
    DocumentMetadata,
    FigureBlock,
    FormulaBlock,
    HeadingBlock,
    Page,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
)
from techdoc_parser.evaluation.source_block_eligibility import (
    SourceBlockEligibilityPolicy,
    classify_source_block_chunk_eligibility,
    eligible_source_block_ids,
)
from techdoc_parser.structure import get_semantic_blocks_for_page

PASS = "PASS"
REVIEW = "REVIEW"
FAIL = "FAIL"

STATUS_PASS = "pass"
STATUS_REVIEW = "review"
STATUS_FAIL = "fail"
STATUS_NOT_MEASURABLE = "not_measurable"
STATUS_NOT_APPLICABLE = "not_applicable"

PROXY_SCOPE = "fixture_chunk_quality_proxy"
PROXY_NOTICE = (
    "Fixture metrics are quality proxies only; they do not prove source-page "
    "visual accuracy, OCR accuracy, semantic accuracy, or real aviation-document "
    "accuracy."
)

DEFAULT_REGISTRY_PATH = Path("tests/fixtures/chunk_quality/evaluation_cases.json")
STRUCTURED_BLOCK_TYPES = {
    "appendix_heading",
    "caution",
    "definition",
    "equation",
    "figure_caption",
    "note",
    "paragraph",
    "procedure_step",
    "requirement",
    "section_heading",
    "table",
    "table_caption",
    "unknown",
    "warning",
}
HEADING_TYPES = {"appendix_heading", "section_heading"}
TABLE_TYPES = {"table", "table_caption"}
FIGURE_TYPES = {"figure_caption"}
EQUATION_TYPES = {"equation"}
ADMONITION_TYPES = {"warning", "caution", "note"}
CROSS_REFERENCE_PATTERN = re.compile(
    r"\b(?:see|refer to|section|table|figure|appendix)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class ChunkQualityIssue:
    """One deterministic chunk-quality issue."""

    code: str
    severity: str
    message: str
    metric_name: str | None = None
    chunk_id: str | None = None
    source_block_ids: tuple[str, ...] = ()
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkQualityMetricResult:
    """One metric result emitted by the fixture evaluator."""

    name: str
    status: str
    value: object
    threshold: object | None = None
    unit: str | None = None
    message: str = ""
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkQualityEvaluationPolicy:
    """Thresholds for deterministic fixture quality proxies."""

    min_source_block_coverage: float = 1.0
    max_duplicate_text_ratio: float = 0.0
    max_duplicate_source_reference_ratio: float = 0.0
    max_exact_overlap_ratio: float = 0.0
    min_provenance_structured_ratio: float = 1.0
    min_order_consistency_ratio: float = 1.0
    max_chunk_chars: int = 1200
    min_chunk_chars: int = 1
    max_section_crossings_per_chunk: int = 1
    require_source_path_metadata: bool = True
    require_parser_identity_metadata: bool = True
    require_source_checksum_metadata: bool = True
    not_measurable_is_review: bool = True
    require_heading_chunks: bool = True


@dataclass(frozen=True)
class ChunkQualityEvaluationCase:
    """One registry case that points to an existing structured fixture."""

    case_id: str
    fixture_path: str
    description: str
    expected_content_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class StructuredFixtureEvidence:
    """Parser-model document plus explicit fixture evidence used for scoring."""

    document: Document
    fixture_path: str
    parser_name: str | None
    parser_version: str | None
    source_hash: str | None
    block_order: tuple[str, ...]
    block_text_by_id: Mapping[str, str]
    block_type_by_id: Mapping[str, str]
    section_path_by_block_id: Mapping[str, tuple[str, ...]]
    table_source_block_ids: tuple[str, ...]
    figure_source_block_ids: tuple[str, ...]
    equation_source_block_ids: tuple[str, ...]
    admonition_source_block_ids: tuple[str, ...]
    cross_reference_source_block_ids: tuple[str, ...]


@dataclass(frozen=True)
class ChunkQualityEvaluationResult:
    """Complete result for one fixture-only chunk-quality evaluation."""

    outcome: str
    evaluation_scope: str
    fixture_name: str
    document_id: str
    chunk_count: int
    source_block_count: int
    metrics: tuple[ChunkQualityMetricResult, ...]
    issues: tuple[ChunkQualityIssue, ...]
    content_type_counts: Mapping[str, int]
    provenance_status_counts: Mapping[str, int]
    chunk_size_summary: Mapping[str, float | int]
    coverage_summary: Mapping[str, object]
    special_content_summary: Mapping[str, object]
    determinism_checked: bool
    determinism_passed: bool | None
    manual_review_required: bool
    proxy_notice: str = PROXY_NOTICE
    source_accuracy_evaluated: bool = False
    ocr_accuracy_evaluated: bool = False
    visual_layout_accuracy_evaluated: bool = False


def load_chunk_quality_cases(
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
) -> tuple[ChunkQualityEvaluationCase, ...]:
    """Load deterministic fixture cases from a JSON registry."""
    path = Path(registry_path)
    data = _load_json_object(path)
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"Chunk quality registry must contain a cases list: {path}")
    result: list[ChunkQualityEvaluationCase] = []
    for index, item in enumerate(cases):
        if not isinstance(item, Mapping):
            raise ValueError(f"Case at index {index} must be an object.")
        case_id = _required_string(item, "case_id", index)
        fixture_path = _required_string(item, "fixture_path", index)
        description = _required_string(item, "description", index)
        expected = _string_tuple(item.get("expected_content_types"))
        result.append(
            ChunkQualityEvaluationCase(
                case_id=case_id,
                fixture_path=fixture_path,
                description=description,
                expected_content_types=expected,
            )
        )
    return tuple(sorted(result, key=lambda case: case.case_id))


def evaluate_chunk_quality_case(
    case: ChunkQualityEvaluationCase,
    *,
    registry_root: str | Path = ".",
    policy: ChunkQualityEvaluationPolicy | None = None,
    max_chars: int | None = None,
) -> ChunkQualityEvaluationResult:
    """Load one registry case, run current chunking twice, and evaluate it."""
    root = Path(registry_root)
    evidence = load_structured_fixture_document(root / case.fixture_path)
    chunk_limit = policy.max_chunk_chars if max_chars is None and policy else max_chars
    if chunk_limit is None:
        chunk_limit = ChunkQualityEvaluationPolicy().max_chunk_chars
    first_chunks = create_semantic_chunks(evidence.document, max_chars=chunk_limit)
    second_chunks = create_semantic_chunks(evidence.document, max_chars=chunk_limit)
    determinism_passed = [chunk.to_dict() for chunk in first_chunks] == [
        chunk.to_dict() for chunk in second_chunks
    ]
    return evaluate_chunk_quality(
        evidence,
        first_chunks,
        policy=policy,
        fixture_name=case.case_id,
        determinism_checked=True,
        determinism_passed=determinism_passed,
    )


def load_structured_fixture_document(path: str | Path) -> StructuredFixtureEvidence:
    """Load an existing structured-document fixture as in-memory parser objects."""
    fixture_path = Path(path)
    artifact = _load_json_object(fixture_path)
    document_data = _mapping(artifact.get("document"))
    document_id = (
        _first_string(document_data, artifact, "document_id") or fixture_path.stem
    )
    source_filename = _first_string(
        document_data, artifact, "source_filename", "filename"
    )
    source_path = source_filename or fixture_path.name
    title = _first_string(
        document_data, artifact, "document_title", "canonical_title", "title"
    )
    document = Document(
        id=document_id,
        source_path=source_path,
        metadata=DocumentMetadata(title=title),
        pages=[],
    )

    pages_by_number: dict[int, Page] = {}
    for page_data in _sequence(artifact.get("pages")):
        page_mapping = _mapping(page_data)
        page_number = _int_or_none(page_mapping.get("page_number"))
        if page_number is None:
            continue
        pages_by_number[page_number] = Page(
            page_number=page_number,
            width=_float_or_none(page_mapping.get("width")),
            height=_float_or_none(page_mapping.get("height")),
            has_native_text=True,
            requires_ocr=False,
        )

    section_path_by_id = _section_path_by_id(artifact)
    block_order: list[str] = []
    block_text_by_id: dict[str, str] = {}
    block_type_by_id: dict[str, str] = {}
    section_path_by_block_id: dict[str, tuple[str, ...]] = {}

    for block_data in sorted(
        (_mapping(item) for item in _sequence(artifact.get("blocks"))),
        key=_block_sort_key,
    ):
        block_id = _string_or_none(block_data.get("block_id"))
        block_type = _string_or_none(block_data.get("block_type")) or "unknown"
        text = str(block_data.get("text") or "")
        page_number = _int_or_none(block_data.get("page_number"))
        if block_id is None or page_number is None:
            continue
        parser_page = pages_by_number.setdefault(
            page_number,
            Page(page_number=page_number, has_native_text=True, requires_ocr=False),
        )
        block = _block_from_structured_fixture(
            block_id,
            block_type,
            text,
            source_path,
            block_data,
        )
        parser_page.blocks.append(block)
        block_order.append(block_id)
        block_text_by_id[block_id] = text
        block_type_by_id[block_id] = block_type
        section_id = _string_or_none(block_data.get("section_id"))
        section_path_by_block_id[block_id] = section_path_by_id.get(
            section_id or "", ()
        )

    document.pages = [pages_by_number[key] for key in sorted(pages_by_number)]
    semantic_block_order = tuple(
        block.id
        for page in document.pages
        for block in get_semantic_blocks_for_page(page)
        if block.id
    )
    return StructuredFixtureEvidence(
        document=document,
        fixture_path=str(fixture_path),
        parser_name=_string_or_none(artifact.get("parser_name")),
        parser_version=_string_or_none(artifact.get("parser_version")),
        source_hash=_document_source_hash(artifact),
        block_order=semantic_block_order or tuple(block_order),
        block_text_by_id=block_text_by_id,
        block_type_by_id=block_type_by_id,
        section_path_by_block_id=section_path_by_block_id,
        table_source_block_ids=_entity_source_block_ids(artifact, "tables"),
        figure_source_block_ids=_entity_source_block_ids(artifact, "figures"),
        equation_source_block_ids=_entity_source_block_ids(artifact, "equations"),
        admonition_source_block_ids=_entity_source_block_ids(artifact, "admonitions"),
        cross_reference_source_block_ids=_entity_source_block_ids(
            artifact, "cross_references"
        ),
    )


def evaluate_chunk_quality(
    evidence: StructuredFixtureEvidence,
    chunks: Sequence[Chunk],
    *,
    policy: ChunkQualityEvaluationPolicy | None = None,
    fixture_name: str | None = None,
    determinism_checked: bool = False,
    determinism_passed: bool | None = None,
) -> ChunkQualityEvaluationResult:
    """Evaluate current chunks against explicit fixture evidence."""
    active_policy = policy or ChunkQualityEvaluationPolicy()
    block_by_id = _fixture_block_by_id(evidence.document)
    eligibility_policy = SourceBlockEligibilityPolicy(
        require_heading_chunks=active_policy.require_heading_chunks
    )
    eligibilities = tuple(
        classify_source_block_chunk_eligibility(
            block_by_id[block_id],
            chunks,
            policy=eligibility_policy,
        )
        for block_id in evidence.block_order
        if block_id in block_by_id
        and evidence.block_type_by_id.get(block_id) in STRUCTURED_BLOCK_TYPES
    )
    fallback_source_block_ids = tuple(
        block_id
        for block_id in evidence.block_order
        if block_id not in block_by_id
        and evidence.block_type_by_id.get(block_id) in STRUCTURED_BLOCK_TYPES
    )
    source_block_ids = (
        eligible_source_block_ids(eligibilities) + fallback_source_block_ids
    )
    known_block_ids = set(source_block_ids)
    chunk_refs = tuple(
        block_id
        for chunk in chunks
        for block_id in chunk.source_block_ids
        if isinstance(block_id, str)
    )
    ref_counts = Counter(chunk_refs)
    covered = tuple(
        block_id for block_id in source_block_ids if ref_counts[block_id] > 0
    )
    missing = tuple(
        block_id for block_id in source_block_ids if ref_counts[block_id] == 0
    )
    invalid = tuple(
        sorted(
            block_id for block_id in set(chunk_refs) if block_id not in known_block_ids
        )
    )
    duplicate_refs = tuple(
        sorted(block_id for block_id, count in ref_counts.items() if count > 1)
    )
    issues: list[ChunkQualityIssue] = []
    metrics: list[ChunkQualityMetricResult] = []

    metrics.append(
        _coverage_metric(
            "source_block_coverage",
            len(covered),
            len(source_block_ids),
            active_policy.min_source_block_coverage,
            missing,
            issues,
        )
    )
    metrics.append(
        _invalid_references_metric(invalid, issues),
    )
    metrics.append(
        _ordering_metric(evidence.block_order, chunks, active_policy, issues),
    )
    metrics.append(
        _section_metric(
            evidence.section_path_by_block_id, chunks, active_policy, issues
        ),
    )
    metrics.append(_chunk_size_metric(chunks, active_policy, issues))
    metrics.append(_duplicate_text_metric(chunks, active_policy, issues))
    metrics.append(
        _duplicate_source_reference_metric(
            duplicate_refs, chunk_refs, active_policy, issues
        )
    )
    metrics.append(_overlap_metric(chunks, active_policy, issues))
    metrics.append(_provenance_metric(evidence, chunks, active_policy, issues))
    metrics.extend(_special_content_metrics(evidence, chunks, issues))
    metrics.append(
        _determinism_metric(determinism_checked, determinism_passed, issues),
    )

    sorted_metrics = tuple(metrics)
    sorted_issues = tuple(_sort_issues(issues))
    outcome = _overall_outcome(sorted_metrics, sorted_issues, active_policy)
    content_type_counts = dict(
        sorted(Counter(evidence.block_type_by_id.values()).items())
    )
    provenance_counts = _provenance_counts(evidence, chunks)
    chunk_size_summary = _chunk_size_summary(chunks)
    coverage_summary: dict[str, object] = {
        "covered_source_block_count": len(covered),
        "missing_source_block_count": len(missing),
        "invalid_source_block_reference_count": len(invalid),
        "duplicate_source_block_reference_count": len(duplicate_refs),
        "coverage_ratio": _ratio(len(covered), len(source_block_ids)),
        "missing_source_block_ids": missing,
        "invalid_source_block_ids": invalid,
        "duplicate_source_block_ids": duplicate_refs,
    }
    special_summary = _special_content_summary(evidence, chunks)
    return ChunkQualityEvaluationResult(
        outcome=outcome,
        evaluation_scope=PROXY_SCOPE,
        fixture_name=fixture_name or Path(evidence.fixture_path).stem,
        document_id=evidence.document.id,
        chunk_count=len(chunks),
        source_block_count=len(source_block_ids),
        metrics=sorted_metrics,
        issues=sorted_issues,
        content_type_counts=content_type_counts,
        provenance_status_counts=provenance_counts,
        chunk_size_summary=chunk_size_summary,
        coverage_summary=coverage_summary,
        special_content_summary=special_summary,
        determinism_checked=determinism_checked,
        determinism_passed=determinism_passed,
        manual_review_required=outcome == REVIEW,
    )


def _coverage_metric(
    name: str,
    covered: int,
    total: int,
    threshold: float,
    missing: Sequence[str],
    issues: list[ChunkQualityIssue],
) -> ChunkQualityMetricResult:
    ratio = _ratio(covered, total)
    if ratio >= threshold:
        status = STATUS_PASS
        message = "All fixture source blocks are represented by chunk source_block_ids."
    else:
        status = STATUS_FAIL
        message = "One or more fixture source blocks are not represented by chunks."
        _add_issue(
            issues,
            "SOURCE_BLOCK_COVERAGE_INCOMPLETE",
            "error",
            message,
            metric_name=name,
            source_block_ids=tuple(missing),
        )
    return ChunkQualityMetricResult(
        name=name,
        status=status,
        value=ratio,
        threshold=threshold,
        unit="ratio",
        message=message,
        details={
            "covered": covered,
            "total": total,
            "missing_source_block_ids": tuple(missing),
        },
    )


def _invalid_references_metric(
    invalid: Sequence[str],
    issues: list[ChunkQualityIssue],
) -> ChunkQualityMetricResult:
    if invalid:
        _add_issue(
            issues,
            "CHUNK_SOURCE_BLOCK_REFERENCE_UNKNOWN",
            "error",
            "A chunk references source_block_ids not present in the fixture.",
            metric_name="source_block_reference_integrity",
            source_block_ids=tuple(invalid),
        )
        status = STATUS_FAIL
    else:
        status = STATUS_PASS
    return ChunkQualityMetricResult(
        name="source_block_reference_integrity",
        status=status,
        value=len(invalid),
        threshold=0,
        unit="count",
        message="Chunk source_block_ids resolve against the fixture."
        if not invalid
        else "Unknown source block references were found.",
        details={"invalid_source_block_ids": tuple(invalid)},
    )


def _ordering_metric(
    source_order: Sequence[str],
    chunks: Sequence[Chunk],
    policy: ChunkQualityEvaluationPolicy,
    issues: list[ChunkQualityIssue],
) -> ChunkQualityMetricResult:
    order_index = {block_id: index for index, block_id in enumerate(source_order)}
    pairs = [
        (chunk.id, block_id, order_index[block_id])
        for chunk in chunks
        for block_id in chunk.source_block_ids
        if block_id in order_index
    ]
    comparisons = max(len(pairs) - 1, 0)
    if comparisons == 0:
        return ChunkQualityMetricResult(
            name="reading_order_consistency",
            status=STATUS_NOT_APPLICABLE,
            value=None,
            threshold=policy.min_order_consistency_ratio,
            unit="ratio",
            message="Ordering is not applicable with fewer than two referenced blocks.",
        )
    inversions = sum(
        1 for left, right in zip(pairs, pairs[1:], strict=False) if right[2] < left[2]
    )
    ratio = 1.0 - (inversions / comparisons)
    if ratio >= policy.min_order_consistency_ratio:
        status = STATUS_PASS
        message = "Chunk source block order follows fixture document order."
    else:
        status = STATUS_FAIL
        message = "Chunk source block order reverses one or more fixture blocks."
        _add_issue(
            issues,
            "READING_ORDER_INVERSION",
            "error",
            message,
            metric_name="reading_order_consistency",
            details={"inversion_count": inversions},
        )
    return ChunkQualityMetricResult(
        name="reading_order_consistency",
        status=status,
        value=ratio,
        threshold=policy.min_order_consistency_ratio,
        unit="ratio",
        message=message,
        details={"comparison_count": comparisons, "inversion_count": inversions},
    )


def _section_metric(
    section_path_by_block_id: Mapping[str, tuple[str, ...]],
    chunks: Sequence[Chunk],
    policy: ChunkQualityEvaluationPolicy,
    issues: list[ChunkQualityIssue],
) -> ChunkQualityMetricResult:
    chunks_with_sections = 0
    crossing_chunks: list[str] = []
    for chunk in chunks:
        section_paths = {
            section_path_by_block_id.get(block_id, ())
            for block_id in chunk.source_block_ids
            if section_path_by_block_id.get(block_id, ())
        }
        if section_paths:
            chunks_with_sections += 1
        if len(section_paths) > policy.max_section_crossings_per_chunk:
            crossing_chunks.append(chunk.id)
    if not chunks_with_sections:
        return ChunkQualityMetricResult(
            name="section_boundary_coherence",
            status=STATUS_NOT_APPLICABLE,
            value=None,
            threshold=policy.max_section_crossings_per_chunk,
            unit="section_paths_per_chunk",
            message="No explicit section paths are present in this fixture.",
        )
    if crossing_chunks:
        status = STATUS_REVIEW
        message = "One or more chunks combine multiple explicit fixture sections."
        _add_issue(
            issues,
            "SECTION_BOUNDARY_CROSSED",
            "warning",
            message,
            metric_name="section_boundary_coherence",
            details={"chunk_ids": tuple(crossing_chunks)},
        )
    else:
        status = STATUS_PASS
        message = "Chunks remain within explicit fixture section boundaries."
    return ChunkQualityMetricResult(
        name="section_boundary_coherence",
        status=status,
        value=len(crossing_chunks),
        threshold=0,
        unit="chunks",
        message=message,
        details={
            "chunks_with_sections": chunks_with_sections,
            "crossing_chunk_ids": tuple(crossing_chunks),
        },
    )


def _chunk_size_metric(
    chunks: Sequence[Chunk],
    policy: ChunkQualityEvaluationPolicy,
    issues: list[ChunkQualityIssue],
) -> ChunkQualityMetricResult:
    too_small = tuple(
        chunk.id for chunk in chunks if len(chunk.text) < policy.min_chunk_chars
    )
    too_large = tuple(
        chunk.id for chunk in chunks if len(chunk.text) > policy.max_chunk_chars
    )
    if too_small:
        status = STATUS_FAIL
        _add_issue(
            issues,
            "CHUNK_EMPTY_OR_TOO_SMALL",
            "error",
            "One or more chunks are empty or below the minimum fixture threshold.",
            metric_name="chunk_size",
            details={"chunk_ids": too_small},
        )
    elif too_large:
        status = STATUS_REVIEW
        _add_issue(
            issues,
            "CHUNK_EXCEEDS_SIZE_TARGET",
            "warning",
            "One or more chunks exceed the fixture size target.",
            metric_name="chunk_size",
            details={"chunk_ids": too_large},
        )
    else:
        status = STATUS_PASS
    return ChunkQualityMetricResult(
        name="chunk_size",
        status=status,
        value=_chunk_size_summary(chunks),
        threshold={
            "min_chars": policy.min_chunk_chars,
            "max_chars": policy.max_chunk_chars,
        },
        unit="chars",
        message="Chunk sizes are inside fixture thresholds."
        if status == STATUS_PASS
        else "Chunk size thresholds need review.",
        details={"too_small_chunk_ids": too_small, "too_large_chunk_ids": too_large},
    )


def _duplicate_text_metric(
    chunks: Sequence[Chunk],
    policy: ChunkQualityEvaluationPolicy,
    issues: list[ChunkQualityIssue],
) -> ChunkQualityMetricResult:
    normalized_text = [
        _normalize_text(chunk.text) for chunk in chunks if chunk.text.strip()
    ]
    counts = Counter(normalized_text)
    duplicates = tuple(sorted(text for text, count in counts.items() if count > 1))
    ratio = _ratio(
        sum(count - 1 for count in counts.values() if count > 1), len(normalized_text)
    )
    if ratio > policy.max_duplicate_text_ratio:
        status = STATUS_REVIEW
        _add_issue(
            issues,
            "DUPLICATE_CHUNK_TEXT",
            "warning",
            "Duplicate normalized chunk text was found in the fixture run.",
            metric_name="duplicate_text_ratio",
            details={"duplicate_text_count": len(duplicates)},
        )
    else:
        status = STATUS_PASS
    return ChunkQualityMetricResult(
        name="duplicate_text_ratio",
        status=status,
        value=ratio,
        threshold=policy.max_duplicate_text_ratio,
        unit="ratio",
        message="No duplicate normalized chunk text was found."
        if status == STATUS_PASS
        else "Duplicate normalized chunk text requires review.",
        details={"duplicate_text_count": len(duplicates)},
    )


def _duplicate_source_reference_metric(
    duplicate_refs: Sequence[str],
    chunk_refs: Sequence[str],
    policy: ChunkQualityEvaluationPolicy,
    issues: list[ChunkQualityIssue],
) -> ChunkQualityMetricResult:
    ratio = _ratio(len(duplicate_refs), len(set(chunk_refs)))
    if ratio > policy.max_duplicate_source_reference_ratio:
        status = STATUS_REVIEW
        _add_issue(
            issues,
            "DUPLICATE_SOURCE_BLOCK_REFERENCE",
            "warning",
            "One or more source blocks appear in multiple chunks.",
            metric_name="duplicate_source_reference_ratio",
            source_block_ids=tuple(duplicate_refs),
        )
    else:
        status = STATUS_PASS
    return ChunkQualityMetricResult(
        name="duplicate_source_reference_ratio",
        status=status,
        value=ratio,
        threshold=policy.max_duplicate_source_reference_ratio,
        unit="ratio",
        message="No duplicate source block references were found."
        if status == STATUS_PASS
        else "Duplicate source block references require review.",
        details={"duplicate_source_block_ids": tuple(duplicate_refs)},
    )


def _overlap_metric(
    chunks: Sequence[Chunk],
    policy: ChunkQualityEvaluationPolicy,
    issues: list[ChunkQualityIssue],
) -> ChunkQualityMetricResult:
    overlaps = 0
    comparisons = 0
    for index, left in enumerate(chunks):
        left_lines = set(_normalized_lines(left.text))
        for right in chunks[index + 1 :]:
            right_lines = set(_normalized_lines(right.text))
            if not left_lines or not right_lines:
                continue
            comparisons += 1
            if left_lines & right_lines:
                overlaps += 1
    if comparisons == 0:
        return ChunkQualityMetricResult(
            name="exact_text_overlap_ratio",
            status=STATUS_NOT_APPLICABLE,
            value=None,
            threshold=policy.max_exact_overlap_ratio,
            unit="ratio",
            message="Overlap is not applicable with fewer than two comparable chunks.",
            details={"comparison_count": comparisons, "overlap_pair_count": overlaps},
        )
    ratio = _ratio(overlaps, comparisons)
    if ratio > policy.max_exact_overlap_ratio:
        status = STATUS_REVIEW
        _add_issue(
            issues,
            "EXACT_TEXT_OVERLAP",
            "warning",
            "Exact normalized line overlap was found across chunks.",
            metric_name="exact_text_overlap_ratio",
            details={"overlap_pair_count": overlaps},
        )
    else:
        status = STATUS_PASS
    return ChunkQualityMetricResult(
        name="exact_text_overlap_ratio",
        status=status,
        value=ratio,
        threshold=policy.max_exact_overlap_ratio,
        unit="ratio",
        message="No exact normalized line overlap was found."
        if status == STATUS_PASS
        else "Exact text overlap requires review.",
        details={"comparison_count": comparisons, "overlap_pair_count": overlaps},
    )


def _provenance_metric(
    evidence: StructuredFixtureEvidence,
    chunks: Sequence[Chunk],
    policy: ChunkQualityEvaluationPolicy,
    issues: list[ChunkQualityIssue],
) -> ChunkQualityMetricResult:
    counts = Counter(
        _chunk_provenance_status(evidence, chunk, policy) for chunk in chunks
    )
    structured = counts.get("structured", 0)
    ratio = _ratio(structured, len(chunks))
    missing_parser_identity = (
        evidence.parser_name is None or evidence.parser_version is None
    )
    missing_source_hash = evidence.source_hash is None
    if ratio >= policy.min_provenance_structured_ratio:
        status = STATUS_PASS
        message = "Chunks include complete current-model fixture provenance."
    else:
        status = STATUS_REVIEW
        message = "Some chunks have incomplete current-model fixture provenance."
        _add_issue(
            issues,
            "CHUNK_PROVENANCE_INCOMPLETE",
            "warning",
            message,
            metric_name="chunk_provenance_completeness",
            details={"provenance_status_counts": dict(sorted(counts.items()))},
        )
    if policy.require_parser_identity_metadata and missing_parser_identity:
        status = _review_or_fail(status)
        _add_issue(
            issues,
            "PARSER_IDENTITY_NOT_MEASURABLE",
            "warning",
            "Parser identity metadata is unavailable for this fixture "
            "provenance metric.",
            metric_name="chunk_provenance_completeness",
        )
    if policy.require_source_checksum_metadata and missing_source_hash:
        status = _review_or_fail(status)
        _add_issue(
            issues,
            "SOURCE_CHECKSUM_NOT_MEASURABLE",
            "warning",
            "Source checksum provenance is unavailable in this fixture.",
            metric_name="chunk_provenance_completeness",
        )
    return ChunkQualityMetricResult(
        name="chunk_provenance_completeness",
        status=status,
        value=ratio,
        threshold=policy.min_provenance_structured_ratio,
        unit="ratio",
        message=message,
        details={
            "provenance_status_counts": dict(sorted(counts.items())),
            "parser_identity_present": not missing_parser_identity,
            "source_checksum_present": not missing_source_hash,
        },
    )


def _special_content_metrics(
    evidence: StructuredFixtureEvidence,
    chunks: Sequence[Chunk],
    issues: list[ChunkQualityIssue],
) -> list[ChunkQualityMetricResult]:
    return [
        _entity_metric(
            "table_source_preservation",
            "table",
            evidence.table_source_block_ids,
            evidence,
            chunks,
            issues,
        ),
        _entity_metric(
            "figure_caption_source_preservation",
            "figure",
            evidence.figure_source_block_ids,
            evidence,
            chunks,
            issues,
        ),
        _entity_metric(
            "equation_source_preservation",
            "equation",
            evidence.equation_source_block_ids,
            evidence,
            chunks,
            issues,
        ),
        _entity_metric(
            "admonition_source_preservation",
            "admonition",
            evidence.admonition_source_block_ids,
            evidence,
            chunks,
            issues,
        ),
        _entity_metric(
            "cross_reference_source_preservation",
            "cross_reference",
            evidence.cross_reference_source_block_ids,
            evidence,
            chunks,
            issues,
        ),
        ChunkQualityMetricResult(
            name="table_cell_accuracy",
            status=STATUS_NOT_MEASURABLE,
            value=None,
            threshold=None,
            unit=None,
            message=(
                "Fixture chunking does not measure source table-cell visual accuracy."
            ),
        ),
        ChunkQualityMetricResult(
            name="source_page_visual_accuracy",
            status=STATUS_NOT_MEASURABLE,
            value=None,
            threshold=None,
            unit=None,
            message="Fixture chunking does not measure source-page visual accuracy.",
        ),
    ]


def _entity_metric(
    metric_name: str,
    label: str,
    source_block_ids: Sequence[str],
    evidence: StructuredFixtureEvidence,
    chunks: Sequence[Chunk],
    issues: list[ChunkQualityIssue],
) -> ChunkQualityMetricResult:
    if not source_block_ids:
        return ChunkQualityMetricResult(
            name=metric_name,
            status=STATUS_NOT_APPLICABLE,
            value=None,
            threshold=1.0,
            unit="ratio",
            message=f"No explicit {label} fixture entities are present.",
        )
    covered, missing, text_missing = _covered_entity_blocks(
        source_block_ids, evidence, chunks
    )
    ratio = _ratio(len(covered), len(set(source_block_ids)))
    if missing or text_missing:
        status = STATUS_REVIEW
        _add_issue(
            issues,
            f"{label.upper()}_SOURCE_PRESERVATION_INCOMPLETE",
            "warning",
            f"Explicit fixture {label} source evidence is not fully represented "
            "in chunks.",
            metric_name=metric_name,
            source_block_ids=tuple(sorted(set(missing) | set(text_missing))),
        )
    else:
        status = STATUS_PASS
    return ChunkQualityMetricResult(
        name=metric_name,
        status=status,
        value=ratio,
        threshold=1.0,
        unit="ratio",
        message=f"Explicit fixture {label} evidence is preserved by chunk IDs and text."
        if status == STATUS_PASS
        else f"Explicit fixture {label} evidence needs review.",
        details={
            "covered_source_block_ids": tuple(sorted(covered)),
            "missing_source_block_ids": tuple(sorted(missing)),
            "text_missing_source_block_ids": tuple(sorted(text_missing)),
        },
    )


def _determinism_metric(
    checked: bool,
    passed: bool | None,
    issues: list[ChunkQualityIssue],
) -> ChunkQualityMetricResult:
    if not checked:
        return ChunkQualityMetricResult(
            name="determinism",
            status=STATUS_NOT_MEASURABLE,
            value=None,
            threshold=True,
            message="Determinism was not checked by the caller.",
        )
    if passed:
        return ChunkQualityMetricResult(
            name="determinism",
            status=STATUS_PASS,
            value=True,
            threshold=True,
            message="Repeated fixture chunking produced identical chunk dictionaries.",
        )
    _add_issue(
        issues,
        "CHUNKING_NOT_DETERMINISTIC",
        "error",
        "Repeated fixture chunking produced different chunk dictionaries.",
        metric_name="determinism",
    )
    return ChunkQualityMetricResult(
        name="determinism",
        status=STATUS_FAIL,
        value=False,
        threshold=True,
        message="Repeated fixture chunking produced different chunk dictionaries.",
    )


def _block_from_structured_fixture(
    block_id: str,
    block_type: str,
    text: str,
    source_path: str,
    block_data: Mapping[str, Any],
) -> Block:
    source = _source_location(source_path, block_data)
    normalized = _string_or_none(block_data.get("normalized_text"))
    if block_type in HEADING_TYPES:
        return HeadingBlock(
            id=block_id,
            source=source,
            text=text,
            normalized_text=normalized,
            level=_int_or_none(block_data.get("level")) or 1,
        )
    if block_type in TABLE_TYPES:
        return TableBlock(
            id=block_id,
            source=source,
            text=text,
            normalized_text=normalized,
            caption=_string_or_none(block_data.get("caption")),
            rows=[],
            source_text_block_ids=[block_id],
            is_candidate=True,
        )
    if block_type in FIGURE_TYPES:
        return FigureBlock(
            id=block_id,
            source=source,
            text=text,
            normalized_text=normalized,
            caption=text,
            source_text_block_ids=[block_id],
            is_candidate=True,
        )
    if block_type in EQUATION_TYPES:
        return FormulaBlock(
            id=block_id,
            source=source,
            text=text,
            normalized_text=normalized,
            latex=_string_or_none(block_data.get("latex")),
        )
    return ParagraphBlock(
        id=block_id,
        source=source,
        text=text,
        normalized_text=normalized,
        source_text_block_ids=[block_id],
    )


def _source_location(source_path: str, block_data: Mapping[str, Any]) -> SourceLocation:
    span = _mapping(block_data.get("source_span"))
    page_number = _int_or_none(block_data.get("page_number")) or _int_or_none(
        span.get("page_start")
    )
    method = _string_or_none(span.get("extraction_method"))
    bbox_data = _mapping(block_data.get("bbox")) or _mapping(span.get("bbox"))
    bbox = None
    if bbox_data:
        bbox = BoundingBox(
            x0=float(bbox_data.get("x0", 0.0)),
            y0=float(bbox_data.get("y0", 0.0)),
            x1=float(bbox_data.get("x1", 0.0)),
            y1=float(bbox_data.get("y1", 0.0)),
        )
    return SourceLocation(
        document_path=source_path,
        page_number=page_number,
        bbox=bbox,
        extraction_method=method,
    )


def _covered_entity_blocks(
    source_block_ids: Sequence[str],
    evidence: StructuredFixtureEvidence,
    chunks: Sequence[Chunk],
) -> tuple[set[str], set[str], set[str]]:
    covered: set[str] = set()
    missing: set[str] = set()
    text_missing: set[str] = set()
    chunk_text_by_block_id: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        for block_id in chunk.source_block_ids:
            chunk_text_by_block_id[block_id].append(chunk.text)
    for block_id in set(source_block_ids):
        chunk_texts = chunk_text_by_block_id.get(block_id, [])
        if not chunk_texts:
            missing.add(block_id)
            continue
        covered.add(block_id)
        source_text = _normalize_text(evidence.block_text_by_id.get(block_id, ""))
        if source_text and not any(
            source_text in _normalize_text(chunk_text) for chunk_text in chunk_texts
        ):
            text_missing.add(block_id)
    return covered, missing, text_missing


def _fixture_block_by_id(document: Document) -> dict[str, Block]:
    return {
        block.id: block for page in document.pages for block in page.blocks if block.id
    }


def _chunk_provenance_status(
    evidence: StructuredFixtureEvidence,
    chunk: Chunk,
    policy: ChunkQualityEvaluationPolicy,
) -> str:
    required = [
        bool(chunk.id),
        chunk.document_id == evidence.document.id,
        bool(chunk.text.strip()),
        bool(chunk.source_page_numbers),
        bool(chunk.source_block_ids),
        bool(chunk.chunk_type),
    ]
    if policy.require_source_path_metadata:
        required.append(bool(chunk.metadata.get("source_path")))
    if all(required):
        return "structured"
    if any(required):
        return "structured_partial"
    return "missing"


def _provenance_counts(
    evidence: StructuredFixtureEvidence,
    chunks: Sequence[Chunk],
) -> dict[str, int]:
    policy = ChunkQualityEvaluationPolicy()
    counts = Counter(
        _chunk_provenance_status(evidence, chunk, policy) for chunk in chunks
    )
    return dict(sorted(counts.items()))


def _special_content_summary(
    evidence: StructuredFixtureEvidence,
    chunks: Sequence[Chunk],
) -> dict[str, object]:
    return {
        "table_source_block_count": len(set(evidence.table_source_block_ids)),
        "figure_source_block_count": len(set(evidence.figure_source_block_ids)),
        "equation_source_block_count": len(set(evidence.equation_source_block_ids)),
        "admonition_source_block_count": len(set(evidence.admonition_source_block_ids)),
        "cross_reference_source_block_count": len(
            set(evidence.cross_reference_source_block_ids)
        ),
        "chunk_text_mentions_cross_reference_language": any(
            CROSS_REFERENCE_PATTERN.search(chunk.text) for chunk in chunks
        ),
        "table_cell_accuracy_evaluated": False,
        "source_page_visual_accuracy_evaluated": False,
    }


def _chunk_size_summary(chunks: Sequence[Chunk]) -> dict[str, float | int]:
    char_counts = [len(chunk.text) for chunk in chunks]
    word_counts = [len(chunk.text.split()) for chunk in chunks]
    if not char_counts:
        return {
            "min_chars": 0,
            "max_chars": 0,
            "mean_chars": 0.0,
            "min_words": 0,
            "max_words": 0,
            "mean_words": 0.0,
        }
    return {
        "min_chars": min(char_counts),
        "max_chars": max(char_counts),
        "mean_chars": round(mean(char_counts), 3),
        "min_words": min(word_counts),
        "max_words": max(word_counts),
        "mean_words": round(mean(word_counts), 3),
    }


def _overall_outcome(
    metrics: Sequence[ChunkQualityMetricResult],
    issues: Sequence[ChunkQualityIssue],
    policy: ChunkQualityEvaluationPolicy,
) -> str:
    if any(issue.severity == "error" for issue in issues):
        return FAIL
    if any(metric.status == STATUS_FAIL for metric in metrics):
        return FAIL
    review_statuses = {STATUS_REVIEW}
    if policy.not_measurable_is_review:
        review_statuses.add(STATUS_NOT_MEASURABLE)
    if any(issue.severity == "warning" for issue in issues):
        return REVIEW
    if any(metric.status in review_statuses for metric in metrics):
        return REVIEW
    return PASS


def _section_path_by_id(artifact: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for section_data in _sequence(artifact.get("sections")):
        section = _mapping(section_data)
        section_id = _string_or_none(section.get("section_id"))
        if section_id is None:
            continue
        path = section.get("path")
        if isinstance(path, Sequence) and not isinstance(path, str | bytes | bytearray):
            result[section_id] = tuple(str(item) for item in path)
        else:
            title = _string_or_none(section.get("title"))
            number = _string_or_none(section.get("section_number"))
            result[section_id] = (
                f"{number} {title}" if number and title else title or "",
            )
    return result


def _entity_source_block_ids(artifact: Mapping[str, Any], key: str) -> tuple[str, ...]:
    block_ids: list[str] = []
    for entity_data in _sequence(artifact.get(key)):
        entity = _mapping(entity_data)
        block_ids.extend(_string_tuple(entity.get("source_block_ids")))
    return tuple(sorted(set(block_ids)))


def _document_source_hash(artifact: Mapping[str, Any]) -> str | None:
    document = _mapping(artifact.get("document"))
    value = _first_string(
        document, artifact, "source_sha256", "source_hash", "file_hash"
    )
    if value and value.startswith("sha256:"):
        return value.removeprefix("sha256:")
    return value


def _add_issue(
    issues: list[ChunkQualityIssue],
    code: str,
    severity: str,
    message: str,
    *,
    metric_name: str | None = None,
    chunk_id: str | None = None,
    source_block_ids: tuple[str, ...] = (),
    details: Mapping[str, object] | None = None,
) -> None:
    issues.append(
        ChunkQualityIssue(
            code=code,
            severity=severity,
            message=message,
            metric_name=metric_name,
            chunk_id=chunk_id,
            source_block_ids=source_block_ids,
            details=details or {},
        )
    )


def _sort_issues(issues: Iterable[ChunkQualityIssue]) -> list[ChunkQualityIssue]:
    severity_order = {"error": 0, "warning": 1, "info": 2}
    return sorted(
        issues,
        key=lambda issue: (
            severity_order.get(issue.severity, 99),
            issue.metric_name or "",
            issue.code,
            issue.chunk_id or "",
            issue.source_block_ids,
        ),
    )


def _review_or_fail(status: str) -> str:
    return status if status == STATUS_FAIL else STATUS_REVIEW


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 6)


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _normalized_lines(value: str) -> tuple[str, ...]:
    return tuple(
        line for line in (_normalize_text(line) for line in value.splitlines()) if line
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def _required_string(item: Mapping[str, Any], key: str, index: int) -> str:
    value = _string_or_none(item.get(key))
    if value is None:
        raise ValueError(f"Case at index {index} missing string field {key!r}.")
    return value


def _block_sort_key(block: Mapping[str, Any]) -> tuple[int, int, str]:
    page = _int_or_none(block.get("page_number")) or 999999
    index = _int_or_none(block.get("document_block_index")) or 999999
    return page, index, str(block.get("block_id") or "")


def _sequence(value: object) -> tuple[object, ...]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(value)
    return ()


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(str(item) for item in value if _string_or_none(item) is not None)
    return ()


def _string_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _first_string(
    first: Mapping[str, Any],
    second: Mapping[str, Any] | str | None = None,
    *keys: str,
) -> str | None:
    mappings: tuple[Mapping[str, Any], ...]
    key_names: tuple[str, ...]
    if isinstance(second, Mapping):
        mappings = (first, second)
        key_names = keys
    else:
        mappings = (first,)
        key_names = tuple(item for item in (second, *keys) if isinstance(item, str))
    for key in key_names:
        for mapping in mappings:
            value = _string_or_none(mapping.get(key))
            if value is not None:
                return value
    return None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _float_or_none(value: object) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None
