"""Tests for structured-document section hierarchy enrichment."""

from __future__ import annotations

from techdoc_parser.contracts import (
    map_document_to_structured_document,
    structured_document_to_dict,
)
from techdoc_parser.core import (
    BoundingBox,
    Document,
    DocumentMetadata,
    HeadingBlock,
    Page,
    ParagraphBlock,
    SourceLocation,
)


def test_mapper_builds_nested_sections_from_existing_heading_levels() -> None:
    data = structured_document_to_dict(
        map_document_to_structured_document(
            _hierarchy_document(),
            document_id="hierarchy-doc",
        )
    )

    assert data["sections"] == [
        {
            "section_id": "hierarchy-doc:s0001",
            "level": 1,
            "title": "Systems Description",
            "section_number": "5",
            "raw_heading": "5 Systems Description",
            "normalized_heading": "5 Systems Description",
            "path": ["5 Systems Description"],
            "source_span": {
                "page_start": 1,
                "page_end": 1,
                "pdf_page_index_start": 0,
                "pdf_page_index_end": 0,
                "source_block_ids": ["h-5", "p-5"],
                "extraction_method": "pymupdf",
            },
        },
        {
            "section_id": "hierarchy-doc:s0002",
            "level": 2,
            "title": "Hydraulic System",
            "parent_section_id": "hierarchy-doc:s0001",
            "section_number": "5.1",
            "raw_heading": "5.1 Hydraulic System",
            "path": ["5 Systems Description", "5.1 Hydraulic System"],
            "source_span": {
                "page_start": 1,
                "page_end": 1,
                "pdf_page_index_start": 0,
                "pdf_page_index_end": 0,
                "source_block_ids": ["h-5-1", "p-5-1"],
                "extraction_method": "pymupdf",
            },
        },
        {
            "section_id": "hierarchy-doc:s0003",
            "level": 4,
            "title": "Reservoir Check",
            "parent_section_id": "hierarchy-doc:s0002",
            "section_number": "5.1.1(a)",
            "raw_heading": "5.1.1(a) Reservoir Check",
            "path": [
                "5 Systems Description",
                "5.1 Hydraulic System",
                "5.1.1(a) Reservoir Check",
            ],
            "source_span": {
                "page_start": 1,
                "page_end": 2,
                "pdf_page_index_start": 0,
                "pdf_page_index_end": 1,
                "source_block_ids": ["h-5-1-1-a", "p-5-1-1-a"],
                "extraction_method": "pymupdf",
            },
        },
        {
            "section_id": "hierarchy-doc:s0004",
            "level": 1,
            "title": "Supplemental Data",
            "section_number": "APPENDIX A",
            "raw_heading": "APPENDIX A Supplemental Data",
            "path": ["APPENDIX A Supplemental Data"],
            "source_span": {
                "page_start": 2,
                "page_end": 2,
                "pdf_page_index_start": 1,
                "pdf_page_index_end": 1,
                "source_block_ids": ["h-appendix-a", "p-appendix-a"],
                "extraction_method": "pymupdf",
            },
        },
        {
            "section_id": "hierarchy-doc:s0005",
            "level": 2,
            "title": "Personnel requirements",
            "parent_section_id": "hierarchy-doc:s0004",
            "section_number": "AMC1 145.A.30(e)",
            "raw_heading": "AMC1 145.A.30(e) Personnel requirements",
            "clause_identifier": "AMC1 145.A.30(e)",
            "path": [
                "APPENDIX A Supplemental Data",
                "AMC1 145.A.30(e) Personnel requirements",
            ],
            "source_span": {
                "page_start": 2,
                "page_end": 2,
                "pdf_page_index_start": 1,
                "pdf_page_index_end": 1,
                "source_block_ids": ["h-amc", "p-amc"],
                "extraction_method": "pymupdf",
            },
        },
    ]


def test_mapper_assigns_blocks_to_active_section_without_fabricating_preface() -> None:
    data = structured_document_to_dict(
        map_document_to_structured_document(
            _hierarchy_document(),
            document_id="hierarchy-doc",
        )
    )
    blocks_by_id = {block["block_id"]: block for block in data["blocks"]}

    assert "section_id" not in blocks_by_id["preface"]
    assert blocks_by_id["h-5"]["section_id"] == "hierarchy-doc:s0001"
    assert blocks_by_id["p-5"]["section_id"] == "hierarchy-doc:s0001"
    assert blocks_by_id["h-5-1"]["section_id"] == "hierarchy-doc:s0002"
    assert blocks_by_id["p-5-1"]["section_id"] == "hierarchy-doc:s0002"
    assert blocks_by_id["h-5-1-1-a"]["section_id"] == "hierarchy-doc:s0003"
    assert blocks_by_id["p-5-1-1-a"]["section_id"] == "hierarchy-doc:s0003"
    assert blocks_by_id["h-appendix-a"]["section_id"] == "hierarchy-doc:s0004"
    assert blocks_by_id["p-amc"]["section_id"] == "hierarchy-doc:s0005"


def test_section_source_spans_do_not_merge_multiple_block_bounding_boxes() -> None:
    data = structured_document_to_dict(
        map_document_to_structured_document(
            _hierarchy_document(),
            document_id="hierarchy-doc",
        )
    )

    assert "bbox" not in data["sections"][0]["source_span"]
    assert data["blocks"][1]["source_span"]["bbox"] == {
        "x0": 72.0,
        "y0": 96.0,
        "x1": 420.0,
        "y1": 116.0,
    }


def test_no_heading_document_leaves_sections_and_block_links_empty() -> None:
    document = Document(
        id="no-heading",
        source_path="no-heading.pdf",
        metadata=DocumentMetadata(),
        pages=[
            Page(
                page_number=1,
                blocks=[
                    ParagraphBlock(
                        id="p-1",
                        text="Synthetic paragraph without a heading.",
                        source=_source(1),
                    )
                ],
            )
        ],
    )

    data = structured_document_to_dict(
        map_document_to_structured_document(document, document_id="no-heading")
    )

    assert data["sections"] == []
    assert "section_id" not in data["blocks"][0]


def _hierarchy_document() -> Document:
    return Document(
        id="hierarchy-doc",
        source_path="synthetic-hierarchy.pdf",
        metadata=DocumentMetadata(title="Synthetic Hierarchy"),
        pages=[
            Page(
                page_number=1,
                blocks=[
                    ParagraphBlock(
                        id="preface",
                        text="Synthetic preface without heading.",
                        source=_source(1),
                    ),
                    _heading("h-5", "5 Systems Description", 1, 1),
                    _paragraph("p-5", "System overview text.", 1),
                    _heading("h-5-1", "5.1 Hydraulic System", 2, 1),
                    _paragraph("p-5-1", "Hydraulic system text.", 1),
                    _heading("h-5-1-1-a", "5.1.1(a) Reservoir Check", 4, 1),
                ],
            ),
            Page(
                page_number=2,
                blocks=[
                    _paragraph("p-5-1-1-a", "Reservoir check continues.", 2),
                    _heading("h-appendix-a", "APPENDIX A Supplemental Data", 1, 2),
                    _paragraph("p-appendix-a", "Appendix text.", 2),
                    _heading(
                        "h-amc",
                        "AMC1 145.A.30(e) Personnel requirements",
                        2,
                        2,
                    ),
                    _paragraph("p-amc", "Personnel requirements text.", 2),
                ],
            ),
        ],
    )


def _heading(block_id: str, text: str, level: int, page_number: int) -> HeadingBlock:
    return HeadingBlock(
        id=block_id,
        text=text,
        normalized_text=text if block_id == "h-5" else None,
        level=level,
        source=_source(page_number),
    )


def _paragraph(block_id: str, text: str, page_number: int) -> ParagraphBlock:
    return ParagraphBlock(
        id=block_id,
        text=text,
        source=_source(page_number),
    )


def _source(page_number: int) -> SourceLocation:
    return SourceLocation(
        document_path="synthetic-hierarchy.pdf",
        page_number=page_number,
        bbox=BoundingBox(x0=72.0, y0=96.0, x1=420.0, y1=116.0),
        extraction_method="pymupdf",
    )
