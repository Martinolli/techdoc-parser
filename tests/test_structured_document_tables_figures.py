"""Tests for table and figure-caption structured-document entity mapping."""

import json
from pathlib import Path

from techdoc_parser.contracts import (
    map_document_to_structured_document,
    structured_document_to_dict,
)
from techdoc_parser.core import (
    BoundingBox,
    Document,
    DocumentMetadata,
    FigureBlock,
    HeadingBlock,
    Page,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
    TableRegionBlock,
)

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "structured_document"
    / "mapped_structured_document_with_tables_figures.json"
)


def test_table_and_figure_entities_are_mapped_from_existing_evidence() -> None:
    data = _mapped_data()

    assert [table["table_id"] for table in data["tables"]] == [
        "entity-doc:p0:t0001",
        "entity-doc:p2:t0002",
    ]
    assert [figure["figure_id"] for figure in data["figures"]] == [
        "entity-doc:p1:f0001",
        "entity-doc:p1:f0002",
    ]


def test_table_entities_preserve_text_and_do_not_fabricate_structure() -> None:
    first, second = _mapped_data()["tables"]

    assert first["text"] == (
        "Table 2 -- Inspection Intervals\n" "Component Interval\n" "Pump 10 hours"
    )
    assert first["caption"] == "Table 2 -- Inspection Intervals"
    assert first["columns"] == []
    assert first["rows"] == []
    assert first["cells"] == []
    assert first["header_rows"] == []
    assert first["merged_cells"] == []
    assert "continuation" not in first

    assert second["text"] == "Region evidence line 1\nRegion evidence line 2"
    assert second["extraction_status"] == "region_only"
    assert second["source_table_block_ids"] == ["table-candidate-1"]
    assert second["source_paragraph_block_ids"] == ["para-region-context"]


def test_table_entities_preserve_candidate_status_and_provenance() -> None:
    table = _mapped_data()["tables"][0]

    assert table["is_candidate"] is True
    assert table["extraction_status"] == "candidate"
    assert table["source_block_ids"] == ["table-candidate-1"]
    assert table["source_text_block_ids"] == ["text-table-source"]
    assert table["source_span"]["source_block_ids"] == ["table-candidate-1"]
    assert table["bbox"] == {
        "x0": 72.0,
        "y0": 160.0,
        "x1": 480.0,
        "y1": 222.0,
    }


def test_table_region_without_bbox_is_mapped_without_fabricated_bbox() -> None:
    table = _mapped_data()["tables"][1]

    assert table["page_start"] == 3
    assert table["pdf_page_index_start"] == 2
    assert "bbox" not in table
    assert "bbox" not in table["source_span"]


def test_figure_entities_preserve_caption_text_without_assets_or_numbers() -> None:
    first, second = _mapped_data()["figures"]

    assert first["caption"] == "Figure 3 -- Test Arrangement"
    assert first["source_caption_text"] == "Figure 3 -- Test Arrangement"
    assert first["source_text_block_ids"] == ["text-figure-source"]
    assert first["extraction_status"] == "caption_candidate"
    assert "asset_reference" not in first
    assert "figure_number" not in first
    assert "description" not in first

    assert second["caption"] == "Figure 3 -- Test Arrangement"
    assert second["figure_id"] != first["figure_id"]


def test_section_links_are_reused_for_table_and_figure_entities() -> None:
    data = _mapped_data()
    section_ids = {section["section_id"] for section in data["sections"]}

    for entity in [*data["tables"], *data["figures"]]:
        assert entity["section_id"] in section_ids
        assert entity["section_path"] == ["1 Hydraulic Inspection"]


def test_source_block_references_point_to_existing_blocks() -> None:
    data = _mapped_data()
    block_ids = {block["block_id"] for block in data["blocks"]}

    for entity in [*data["tables"], *data["figures"]]:
        assert set(entity["source_block_ids"]) <= block_ids
        assert set(entity["source_span"]["source_block_ids"]) <= block_ids


def test_mapper_does_not_copy_parser_source_confidence_to_entities() -> None:
    data = _mapped_data()
    encoded = json.dumps({"tables": data["tables"], "figures": data["figures"]})

    assert "confidence" not in encoded
    assert "extraction_confidence" not in encoded
    assert "classification_confidence" not in encoded


def test_empty_evidence_maps_to_empty_entity_collections() -> None:
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

    assert mapped["tables"] == []
    assert mapped["figures"] == []


def test_mapping_is_deterministic_and_non_mutating() -> None:
    document = _evidence_document()
    before = document.to_dict()

    first = structured_document_to_dict(
        map_document_to_structured_document(
            document,
            document_id="entity-doc",
            document_title="Synthetic Entity Guide",
        )
    )
    second = structured_document_to_dict(
        map_document_to_structured_document(
            document,
            document_id="entity-doc",
            document_title="Synthetic Entity Guide",
        )
    )

    assert first == second
    assert document.to_dict() == before


def test_tables_figures_fixture_matches_contract_output() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert fixture == _mapped_data()


def _mapped_data() -> dict[str, object]:
    return structured_document_to_dict(
        map_document_to_structured_document(
            _evidence_document(),
            document_id="entity-doc",
            document_title="Synthetic Entity Guide",
        )
    )


def _evidence_document() -> Document:
    source_path = "synthetic-entity-guide.pdf"
    return Document(
        id="synthetic-entity-guide",
        source_path=source_path,
        metadata=DocumentMetadata(title="Synthetic Entity Guide"),
        pages=[
            Page(
                page_number=1,
                blocks=[
                    HeadingBlock(
                        id="heading-1",
                        source=_source(source_path, 1, 72.0, 72.0, 420.0, 96.0),
                        text="1 Hydraulic Inspection",
                        normalized_text="1 Hydraulic Inspection",
                        level=1,
                    ),
                    TableBlock(
                        id="table-candidate-1",
                        source=_source(source_path, 1, 72.0, 160.0, 480.0, 222.0),
                        text=(
                            "Table 2 -- Inspection Intervals\n"
                            "Component Interval\n"
                            "Pump 10 hours"
                        ),
                        normalized_text=(
                            "Table 2 -- Inspection Intervals Component Interval "
                            "Pump 10 hours"
                        ),
                        caption="Table 2 -- Inspection Intervals",
                        rows=[
                            ["Table 2 -- Inspection Intervals"],
                            ["Component Interval"],
                            ["Pump 10 hours"],
                        ],
                        source_text_block_ids=["text-table-source"],
                        is_candidate=True,
                    ),
                ],
            ),
            Page(
                page_number=2,
                blocks=[
                    FigureBlock(
                        id="figure-caption-1",
                        source=_source(source_path, 2, 80.0, 250.0, 430.0, 274.0),
                        text="Figure 3 -- Test Arrangement",
                        normalized_text="Figure 3 -- Test Arrangement",
                        caption="Figure 3 -- Test Arrangement",
                        source_text_block_ids=["text-figure-source"],
                        is_candidate=True,
                    ),
                    FigureBlock(
                        id="figure-caption-2",
                        source=_source(source_path, 2, 82.0, 305.0, 432.0, 329.0),
                        text="Figure 3 -- Test Arrangement",
                        normalized_text="Figure 3 -- Test Arrangement",
                        caption="Figure 3 -- Test Arrangement",
                        source_text_block_ids=["text-figure-source-duplicate"],
                        is_candidate=True,
                    ),
                ],
            ),
            Page(
                page_number=3,
                blocks=[
                    TableRegionBlock(
                        id="table-region-1",
                        source=SourceLocation(
                            document_path=source_path,
                            page_number=3,
                            extraction_method="synthetic",
                            confidence=0.91,
                        ),
                        text="Region evidence line 1\nRegion evidence line 2",
                        normalized_text="Region evidence line 1 Region evidence line 2",
                        caption=None,
                        rows=[
                            ["Region evidence line 1"],
                            ["Region evidence line 2"],
                        ],
                        source_text_block_ids=["text-region-source"],
                        source_table_block_ids=["table-candidate-1"],
                        source_paragraph_block_ids=["para-region-context"],
                        is_candidate=True,
                    )
                ],
            ),
        ],
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
