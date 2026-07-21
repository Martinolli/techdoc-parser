"""Tests for equation and admonition structured-document entity mapping."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from techdoc_parser.contracts import (
    map_document_to_structured_document,
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
    detect_admonition_candidates,
    detect_equation_candidate,
)

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "structured_document"
    / "mapped_structured_document_with_equations_admonitions.json"
)


@pytest.mark.parametrize(
    ("text", "expected_label"),
    [
        ("P = F / A", None),
        ("Equation 4: Q = m × c × ΔT", "Equation 4"),
        ("V ≈ I × R", None),
        ("σ = F / A (A-1)", "(A-1)"),
    ],
)
def test_equation_detector_accepts_conservative_math_evidence(
    text: str,
    expected_label: str | None,
) -> None:
    candidate = detect_equation_candidate(_paragraph("eq", text, page_number=1))

    assert candidate is not None
    assert candidate.raw_text == text
    assert candidate.label == expected_label
    assert candidate.normalized_representation is None
    assert candidate.page_number == 1


def test_formula_block_latex_is_mapped_without_normalizing_plain_text() -> None:
    block = FormulaBlock(
        id="formula-block",
        text="E = m c^2",
        source=_source("synthetic.pdf", 1, 72.0, 112.0, 300.0, 132.0),
        latex="E = mc^2",
    )

    candidate = detect_equation_candidate(block)

    assert candidate is not None
    assert candidate.raw_text == "E = m c^2"
    assert candidate.normalized_representation == "E = mc^2"


@pytest.mark.parametrize(
    "text",
    [
        "Revision = C",
        "Page 1 of 2",
        "Temperature range is 10 to 20 °C",
        "The pressure = value shall be recorded.",
        "WARNING: Release stored pressure.",
        "Figure 1 = overview.",
    ],
)
def test_equation_detector_rejects_prose_metadata_and_admonitions(text: str) -> None:
    assert detect_equation_candidate(_paragraph("not-eq", text, page_number=1)) is None


def test_equation_detector_ignores_raw_text_heading_table_and_figure_blocks() -> None:
    source = _source("synthetic.pdf", 1, 72.0, 112.0, 300.0, 132.0)

    blocks = [
        HeadingBlock(id="heading", source=source, text="1 P = F / A", level=1),
        TableBlock(id="table", source=source, text="P = F / A"),
        FigureBlock(id="figure", source=source, text="Figure 1 -- P = F / A"),
    ]

    assert [detect_equation_candidate(block) for block in blocks] == [None] * 3


def test_admonition_detector_accepts_explicit_labels_only() -> None:
    blocks = [
        _paragraph("warning", "WARNING: Release stored hydraulic pressure.", 1),
        _paragraph("important", "Important: Record the calibrated gauge ID.", 1),
        _paragraph("safety", "Safety Notice: Wear eye protection.", 1),
    ]

    candidates = detect_admonition_candidates(blocks)

    assert [candidate.normalized_type for candidate in candidates] == [
        "WARNING",
        "IMPORTANT",
        "SAFETY_NOTICE",
    ]
    assert [candidate.raw_label for candidate in candidates] == [
        "WARNING:",
        "Important:",
        "Safety Notice:",
    ]
    assert [candidate.body_text for candidate in candidates] == [
        "Release stored hydraulic pressure.",
        "Record the calibrated gauge ID.",
        "Wear eye protection.",
    ]


def test_admonition_detector_collects_bounded_following_body_blocks() -> None:
    blocks = [
        _paragraph("label", "CAUTION", 1),
        _paragraph("body-1", "Do not exceed the synthetic test pressure.", 1),
        _paragraph("body-2", "Stop the test if leakage is observed.", 1),
        _paragraph("body-3", "This paragraph remains outside the caution.", 1),
    ]

    candidates = detect_admonition_candidates(blocks)

    assert len(candidates) == 1
    assert candidates[0].source_block_ids == ("label", "body-1", "body-2")
    assert candidates[0].body_text == (
        "Do not exceed the synthetic test pressure.\n"
        "Stop the test if leakage is observed."
    )


def test_admonition_detector_stops_at_page_and_structure_boundaries() -> None:
    blocks = [
        _paragraph("note", "NOTE:", 1),
        _paragraph("next-page", "This page should not be collected.", 2),
        _paragraph("warning", "WARNING:", 2),
        HeadingBlock(
            id="heading",
            source=_source("synthetic.pdf", 2, 72.0, 100.0, 300.0, 120.0),
            text="2 Next Section",
            level=1,
        ),
    ]

    assert detect_admonition_candidates(blocks) == ()


@pytest.mark.parametrize(
    "text",
    [
        "Warnings and limitations",
        "Important dimensions are listed below.",
        "See note 4 for the torque sequence.",
        "CAUTION signs are installed near the pump.",
    ],
)
def test_admonition_detector_rejects_non_label_prose(text: str) -> None:
    assert detect_admonition_candidates([_paragraph("plain", text, 1)]) == ()


def test_equation_and_admonition_entities_are_mapped_from_existing_evidence() -> None:
    data = _mapped_data()

    assert [equation["equation_id"] for equation in data["equations"]] == [
        "eq-adm-doc:e0001",
        "eq-adm-doc:e0002",
        "eq-adm-doc:e0003",
    ]
    assert [admonition["admonition_id"] for admonition in data["admonitions"]] == [
        "eq-adm-doc:a0001",
        "eq-adm-doc:a0002",
        "eq-adm-doc:a0003",
    ]


def test_equation_entities_preserve_raw_text_labels_and_formula_notation() -> None:
    first, second, third = _mapped_data()["equations"]

    assert first["raw_text"] == "P = F / A"
    assert "equation_label" not in first
    assert "normalized_representation" not in first

    assert second["raw_text"] == "Equation 4: Q = m × c × ΔT"
    assert second["equation_label"] == "Equation 4"

    assert third["raw_text"] == "E = m c^2"
    assert third["normalized_representation"] == "E = mc^2"


def test_admonition_entities_preserve_labels_types_and_body_text() -> None:
    warning, note, caution = _mapped_data()["admonitions"]

    assert warning["admonition_type"] == "WARNING"
    assert warning["normalized_type"] == "WARNING"
    assert warning["raw_label"] == "WARNING:"
    assert warning["body_text"] == "Release stored hydraulic pressure first."

    assert note["raw_label"] == "NOTE:"
    assert note["body_text"] == "Record the ambient temperature before the test."

    assert caution["source_block_ids"] == [
        "caution-label",
        "caution-body-1",
        "caution-body-2",
    ]
    assert caution["body_text"] == (
        "Do not exceed the synthetic test pressure.\n"
        "Stop the test if leakage is observed."
    )


def test_entities_preserve_provenance_and_reuse_section_links() -> None:
    data = _mapped_data()
    block_ids = {block["block_id"] for block in data["blocks"]}
    section_id = data["sections"][0]["section_id"]

    for entity in [*data["equations"], *data["admonitions"]]:
        assert set(entity["source_block_ids"]) <= block_ids
        assert set(entity["source_span"]["source_block_ids"]) <= block_ids
        assert entity["section_id"] == section_id
        assert entity["section_path"] == ["1 Hydraulic Test Setup"]

    assert data["admonitions"][2]["page_start"] == 2
    assert data["admonitions"][2]["page_end"] == 2
    assert "bbox" not in data["admonitions"][2]
    assert "bbox" not in data["admonitions"][2]["source_span"]


def test_mapper_does_not_copy_parser_source_confidence_to_new_entities() -> None:
    data = _mapped_data()
    encoded = json.dumps(
        {"equations": data["equations"], "admonitions": data["admonitions"]}
    )

    assert "confidence" not in encoded
    assert "extraction_confidence" not in encoded
    assert "classification_confidence" not in encoded


def test_empty_evidence_maps_to_empty_new_entity_collections() -> None:
    document = Document(
        id="plain",
        source_path="plain.pdf",
        metadata=DocumentMetadata(title="Plain"),
        pages=[
            Page(
                page_number=1,
                blocks=[
                    ParagraphBlock(
                        id="plain-para",
                        text="Plain paragraph only.",
                        source=SourceLocation("plain.pdf", page_number=1),
                    )
                ],
            )
        ],
    )

    mapped = structured_document_to_dict(
        map_document_to_structured_document(document, document_id="plain")
    )

    assert mapped["equations"] == []
    assert mapped["admonitions"] == []


def test_mapping_is_deterministic_and_non_mutating() -> None:
    document = _evidence_document()
    before = document.to_dict()

    first = _mapped_data(document=document)
    second = _mapped_data(document=document)

    assert first == second
    assert document.to_dict() == before


def test_equations_admonitions_fixture_matches_contract_output() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert fixture == _mapped_data()


def _mapped_data(document: Document | None = None) -> dict[str, object]:
    return structured_document_to_dict(
        map_document_to_structured_document(
            document or _evidence_document(),
            document_id="eq-adm-doc",
            document_title="Synthetic Equation and Admonition Guide",
        )
    )


def _evidence_document() -> Document:
    source_path = "synthetic-equation-admonition-guide.pdf"
    return Document(
        id="synthetic-equation-admonition-guide",
        source_path=source_path,
        metadata=DocumentMetadata(title="Synthetic Equation and Admonition Guide"),
        pages=[
            Page(
                page_number=1,
                blocks=[
                    HeadingBlock(
                        id="heading-1",
                        source=_source(source_path, 1, 72.0, 72.0, 420.0, 96.0),
                        text="1 Hydraulic Test Setup",
                        normalized_text="1 Hydraulic Test Setup",
                        level=1,
                    ),
                    _paragraph("equation-pressure", "P = F / A", 1),
                    _paragraph("equation-heat", "Equation 4: Q = m × c × ΔT", 1),
                    _paragraph(
                        "warning-single",
                        "WARNING: Release stored hydraulic pressure first.",
                        1,
                    ),
                    _paragraph("note-label", "NOTE:", 1),
                    _paragraph(
                        "note-body",
                        "Record the ambient temperature before the test.",
                        1,
                    ),
                    _paragraph("revision", "Revision = C", 1),
                    TableBlock(
                        id="table-boundary",
                        source=_source(source_path, 1, 72.0, 330.0, 420.0, 370.0),
                        text="Table 1 -- Non equation P = F / A",
                    ),
                ],
            ),
            Page(
                page_number=2,
                blocks=[
                    FormulaBlock(
                        id="formula-energy",
                        source=_source(source_path, 2, 72.0, 112.0, 300.0, 132.0),
                        text="E = m c^2",
                        latex="E = mc^2",
                    ),
                    _paragraph("caution-label", "CAUTION", 2),
                    _paragraph(
                        "caution-body-1",
                        "Do not exceed the synthetic test pressure.",
                        2,
                    ),
                    _paragraph(
                        "caution-body-2",
                        "Stop the test if leakage is observed.",
                        2,
                    ),
                    _paragraph(
                        "caution-outside",
                        "This paragraph remains outside the caution.",
                        2,
                    ),
                    FigureBlock(
                        id="figure-boundary",
                        source=_source(source_path, 2, 72.0, 350.0, 420.0, 370.0),
                        text="Figure 1 -- Safety Notice: not an admonition body",
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
