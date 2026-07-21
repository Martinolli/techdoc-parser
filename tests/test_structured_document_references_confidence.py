"""Tests for structured-document references and confidence policy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techdoc_parser.contracts import (
    add_confidence_if_available,
    map_document_to_structured_document,
    map_ocr_confidence,
    map_source_extraction_confidence,
    normalize_confidence,
    resolve_cross_reference_candidates,
    structured_document_to_dict,
)
from techdoc_parser.core import (
    BoundingBox,
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
from techdoc_parser.structure import (
    CrossReferenceCandidate,
    detect_cross_reference_candidates,
)

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "structured_document"
    / "mapped_structured_document_with_references_confidence.json"
)


@pytest.mark.parametrize(
    ("text", "reference_type", "target_identifier"),
    [
        ("See Section 4.2.", "section", "4.2"),
        ("Refer to Table 7-2.", "table", "7-2"),
        ("See Figure 3.", "figure", "3"),
        ("Refer to Eq. A-1.", "equation", "A-1"),
        ("In accordance with Appendix B.", "appendix", "Appendix B"),
        ("Refer to Annex A.", "annex", "Annex A"),
        ("See paragraph 4.3(b).", "paragraph", "4.3(b)"),
        ("Refer to AMC1 145.A.30(e).", "clause", "AMC1 145.A.30(e)"),
        ("According to document ABC-123.", "external_document", "ABC-123"),
    ],
)
def test_reference_detector_accepts_explicit_reference_forms(
    text: str,
    reference_type: str,
    target_identifier: str,
) -> None:
    candidates = detect_cross_reference_candidates([_paragraph("ref", text, 1)])

    assert len(candidates) == 1
    assert candidates[0].raw_reference_text == text
    assert candidates[0].reference_type == reference_type
    assert candidates[0].target_identifier == target_identifier


def test_reference_detector_preserves_order_and_multiple_references() -> None:
    block = _paragraph("multi-ref", "Refer to Section 2.1 and Figure 3.", 1)

    candidates = detect_cross_reference_candidates([block])

    assert [candidate.raw_reference_text for candidate in candidates] == [
        "Refer to Section 2.1",
        "Figure 3.",
    ]
    assert [candidate.reference_type for candidate in candidates] == [
        "section",
        "figure",
    ]


def test_repeated_identical_references_remain_separate_occurrences() -> None:
    block = _paragraph("repeat", "See Section 2.1. See Section 2.1.", 1)

    candidates = detect_cross_reference_candidates([block])

    assert len(candidates) == 2
    assert [candidate.raw_reference_text for candidate in candidates] == [
        "See Section 2.1.",
        "See Section 2.1.",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "The section material is corrosion resistant.",
        "The figure increased during the test.",
        "The table surface was inspected.",
        "Appendix pressure slowly.",
        "Revision C applies.",
        "Part number FIG-123.",
        "Table salt was found.",
        "See-through panel.",
        "The warning system is described below.",
    ],
)
def test_reference_detector_rejects_false_positives(text: str) -> None:
    assert detect_cross_reference_candidates([_paragraph("plain", text, 1)]) == ()


def test_detector_ignores_non_reference_block_types() -> None:
    source = _source("synthetic.pdf", 1, 72.0, 100.0, 420.0, 124.0)
    blocks = [
        HeadingBlock(id="h", source=source, text="See Section 2.1", level=1),
        TableBlock(id="t", source=source, text="See Section 2.1"),
        FigureBlock(id="f", source=source, text="See Section 2.1"),
        FormulaBlock(id="e", source=source, text="E = m c^2"),
    ]

    assert detect_cross_reference_candidates(blocks) == ()


def test_reference_detection_is_deterministic_and_non_mutating() -> None:
    blocks = [_paragraph("ref", "Refer to Section 2.1 and Figure 3.", 1)]
    before = [block.to_dict() for block in blocks]

    first = detect_cross_reference_candidates(blocks)
    second = detect_cross_reference_candidates(blocks)

    assert first == second
    assert [block.to_dict() for block in blocks] == before


def test_resolution_uses_unique_local_targets_only() -> None:
    data = _mapped_data()
    references = data["cross_references"]

    resolved = [ref for ref in references if ref["resolution_status"] == "resolved"]
    assert [ref["target_id"] for ref in resolved] == [
        "ref-doc:s0002",
        "ref-doc:p0:f0001",
        "ref-doc:p0:t0001",
        "ref-doc:e0001",
    ]
    assert all(ref["target_id"] != ref["source_block_ids"][0] for ref in resolved)


def test_resolution_marks_unknown_external_and_ambiguous_targets() -> None:
    data = _mapped_data()
    statuses = {
        ref["raw_text"]: ref["resolution_status"] for ref in data["cross_references"]
    }

    assert statuses["Refer to Appendix C."] == "unresolved"
    assert statuses["In accordance with document SYN-STD-004."] == "external"

    duplicate_sections = [
        _section("doc:s0001", "4.2"),
        _section("doc:s0002", "4.2"),
    ]
    ambiguous = resolve_cross_reference_candidates(
        (
            CrossReferenceCandidate(
                source_block_id="block-1",
                raw_reference_text="See Section 4.2.",
                reference_type="section",
                target_identifier="4.2",
                resolution_status="not_attempted",
            ),
        ),
        sections=duplicate_sections,
    )

    assert ambiguous[0].resolution_status == "ambiguous"
    assert ambiguous[0].resolved_target_id is None


def test_cross_reference_entities_preserve_source_provenance() -> None:
    data = _mapped_data()
    block_ids = {block["block_id"] for block in data["blocks"]}
    local_target_ids = (
        {section["section_id"] for section in data["sections"]}
        | {table["table_id"] for table in data["tables"]}
        | {figure["figure_id"] for figure in data["figures"]}
        | {equation["equation_id"] for equation in data["equations"]}
    )

    for reference in data["cross_references"]:
        assert set(reference["source_block_ids"]) <= block_ids
        assert set(reference["source_span"]["source_block_ids"]) <= block_ids
        assert reference["page_start"] == reference["source_span"]["page_start"]
        assert reference["section_id"] == "ref-doc:s0002"
        if reference["resolution_status"] == "resolved":
            assert reference["target_id"] in local_target_ids
        else:
            assert "target_id" not in reference


def test_root_collections_are_preserved_when_references_are_added() -> None:
    data = _mapped_data()

    assert data["pages"]
    assert data["blocks"]
    assert data["sections"]
    assert data["tables"]
    assert data["figures"]
    assert data["equations"]
    assert data["admonitions"]
    assert len(data["cross_references"]) == 6
    assert [ref["reference_id"] for ref in data["cross_references"]] == [
        "ref-doc:r0001",
        "ref-doc:r0002",
        "ref-doc:r0003",
        "ref-doc:r0004",
        "ref-doc:r0005",
        "ref-doc:r0006",
    ]


def test_confidence_policy_rejects_invalid_and_preserves_valid_values() -> None:
    assert normalize_confidence(None, field_name="structure_confidence") is None
    assert normalize_confidence(0.73, field_name="structure_confidence") == 0.73

    for value in (True, -0.1, 1.1, "0.5"):
        with pytest.raises(ValueError):
            normalize_confidence(value, field_name="structure_confidence")

    data: dict[str, object] = {}
    add_confidence_if_available(data, "classification_confidence", 0.62)
    assert data == {"classification_confidence": 0.62}


def test_current_source_confidence_placeholders_are_not_mapped() -> None:
    native_source = SourceLocation(
        document_path="synthetic.pdf",
        page_number=1,
        extraction_method="pymupdf",
        confidence=1.0,
    )
    ocr_source = SourceLocation(
        document_path="synthetic.pdf",
        page_number=1,
        extraction_method="ocr:tesseract",
        confidence=0.81,
    )

    assert map_source_extraction_confidence(native_source) is None
    assert map_ocr_confidence(native_source) is None
    assert map_ocr_confidence(ocr_source) == 0.81


def test_mapper_emits_no_confidence_fields_without_matching_evidence() -> None:
    encoded = json.dumps(_mapped_data())

    assert "confidence" not in encoded
    assert "ocr_confidence" not in encoded
    assert "extraction_confidence" not in encoded
    assert "structure_confidence" not in encoded
    assert "classification_confidence" not in encoded


def test_reference_confidence_fixture_matches_contract_output() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert fixture == _mapped_data()


def test_reference_confidence_fixture_is_valid_json_object() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert fixture["schema_name"] == "techdoc-structured-document"
    assert fixture["schema_version"] == "0.1.0"
    assert {ref["resolution_status"] for ref in fixture["cross_references"]} == {
        "external",
        "resolved",
        "unresolved",
    }


def _mapped_data(document: Document | None = None) -> dict[str, object]:
    return structured_document_to_dict(
        map_document_to_structured_document(
            document or _reference_document(),
            document_id="ref-doc",
            document_title="Synthetic Reference Guide",
        )
    )


def _reference_document() -> Document:
    source_path = "synthetic-reference-guide.pdf"
    return Document(
        id="synthetic-reference-guide",
        source_path=source_path,
        metadata=DocumentMetadata(title="Synthetic Reference Guide"),
        pages=[
            Page(
                page_number=1,
                blocks=[
                    HeadingBlock(
                        id="heading-1",
                        source=_source(source_path, 1, 72.0, 72.0, 420.0, 96.0),
                        text="1 Reference Overview",
                        normalized_text="1 Reference Overview",
                        level=1,
                    ),
                    FigureBlock(
                        id="figure-caption-3",
                        source=_source(source_path, 1, 72.0, 120.0, 420.0, 144.0),
                        text="Figure 3 -- Synthetic Reference Diagram",
                        caption="Figure 3 -- Synthetic Reference Diagram",
                    ),
                    TableBlock(
                        id="table-2",
                        source=_source(source_path, 1, 72.0, 170.0, 420.0, 220.0),
                        text="Table 2 -- Synthetic Inspection Interval",
                        caption="Table 2 -- Synthetic Inspection Interval",
                    ),
                    FormulaBlock(
                        id="equation-4",
                        source=_source(source_path, 1, 72.0, 250.0, 420.0, 274.0),
                        text="Equation 4: Q = m × c × ΔT",
                    ),
                    ParagraphBlock(
                        id="warning-1",
                        source=_source(source_path, 1, 72.0, 300.0, 420.0, 330.0),
                        text="WARNING: Use synthetic test equipment only.",
                    ),
                ],
            ),
            Page(
                page_number=2,
                blocks=[
                    HeadingBlock(
                        id="heading-2-1",
                        source=_source(source_path, 2, 72.0, 72.0, 420.0, 96.0),
                        text="2.1 Inspection References",
                        normalized_text="2.1 Inspection References",
                        level=2,
                    ),
                    _paragraph(
                        "ref-section-figure",
                        "Refer to Section 2.1 and Figure 3.",
                        2,
                    ),
                    _paragraph(
                        "ref-table",
                        "See Table 2 for the inspection interval.",
                        2,
                    ),
                    _paragraph("ref-equation", "See Equation 4.", 2),
                    _paragraph("ref-unresolved", "Refer to Appendix C.", 2),
                    _paragraph(
                        "ref-external",
                        "In accordance with document SYN-STD-004.",
                        2,
                    ),
                ],
            ),
        ],
    )


def _paragraph(id_: str, text: str, page_number: int) -> ParagraphBlock:
    return ParagraphBlock(
        id=id_,
        text=text,
        source=_source(
            "synthetic.pdf",
            page_number,
            72.0,
            100.0 + page_number,
            420.0,
            124.0 + page_number,
        ),
    )


def _section(section_id: str, section_number: str):
    from techdoc_parser.contracts import StructuredDocumentSection

    return StructuredDocumentSection(
        section_id=section_id,
        level=1,
        title=f"Synthetic {section_number}",
        section_number=section_number,
        path=(section_number,),
    )


def _source(
    document_path: str,
    page_number: int,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> SourceLocation:
    return SourceLocation(
        document_path=document_path,
        page_number=page_number,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
        extraction_method="synthetic",
        confidence=0.91,
    )
