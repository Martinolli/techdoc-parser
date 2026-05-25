"""Tests for grouped table-region candidates."""

from techdoc_parser.core import (
    Block,
    BoundingBox,
    Document,
    DocumentMetadata,
    Page,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
    TableRegionBlock,
)
from techdoc_parser.exporters import document_to_semantic_markdown
from techdoc_parser.structure import (
    create_table_region_blocks_for_page,
    get_semantic_blocks_for_page,
)


def _source(
    *,
    y0: float = 10.0,
    x0: float = 10.0,
) -> SourceLocation:
    return SourceLocation(
        document_path="manual.pdf",
        page_number=1,
        bbox=BoundingBox(x0=x0, y0=y0, x1=x0 + 100.0, y1=y0 + 10.0),
        extraction_method="pymupdf",
        confidence=1.0,
    )


def _table(
    id: str,
    text: str,
    source_text_block_ids: list[str],
    *,
    y0: float = 10.0,
    x0: float = 10.0,
) -> TableBlock:
    return TableBlock(
        id=id,
        source=_source(y0=y0, x0=x0),
        text=text,
        normalized_text=text,
        rows=[[line] for line in text.splitlines() if line.strip()],
        source_text_block_ids=source_text_block_ids,
    )


def _paragraph(
    id: str,
    text: str,
    source_text_block_ids: list[str],
    *,
    y0: float = 10.0,
    x0: float = 10.0,
) -> ParagraphBlock:
    return ParagraphBlock(
        id=id,
        source=_source(y0=y0, x0=x0),
        text=text,
        normalized_text=text,
        source_text_block_ids=source_text_block_ids,
    )


def _table_region(
    *,
    source_text_block_ids: list[str],
    source_table_block_ids: list[str],
    source_paragraph_block_ids: list[str] | None = None,
) -> TableRegionBlock:
    text = "TABLE I. Severity categories\nSEVERITY CATEGORIES"
    return TableRegionBlock(
        id="table-region-1",
        source=_source(),
        text=text,
        normalized_text=text,
        caption="TABLE I. Severity categories",
        rows=[["TABLE I. Severity categories"], ["SEVERITY CATEGORIES"]],
        source_text_block_ids=source_text_block_ids,
        source_table_block_ids=source_table_block_ids,
        source_paragraph_block_ids=source_paragraph_block_ids or [],
        is_candidate=True,
    )


def _document(blocks: list[Block]) -> Document:
    return Document(
        id="manual",
        source_path="manual.pdf",
        metadata=DocumentMetadata(title="Manual"),
        pages=[Page(page_number=1, blocks=blocks, has_native_text=True)],
    )


def test_table_region_block_serialization() -> None:
    """TableRegionBlock should serialize grouped table metadata."""
    block = _table_region(
        source_text_block_ids=["text-1", "text-2"],
        source_table_block_ids=["table-1"],
        source_paragraph_block_ids=["paragraph-1"],
    )

    data = block.to_dict()

    assert data["block_type"] == "table_region"
    assert data["caption"] == "TABLE I. Severity categories"
    assert data["rows"] == [["TABLE I. Severity categories"], ["SEVERITY CATEGORIES"]]
    assert data["source_text_block_ids"] == ["text-1", "text-2"]
    assert data["source_table_block_ids"] == ["table-1"]
    assert data["source_paragraph_block_ids"] == ["paragraph-1"]
    assert data["is_candidate"] is True


def test_table_region_groups_simple_caption_header_and_rows() -> None:
    """A caption followed by table-like blocks should become one region."""
    caption = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    title = _table("table-2", "SEVERITY CATEGORIES", ["text-2"], y0=25.0)
    header = _table(
        "table-3",
        "Description\nSeverity\nCategory\nMishap Result Criteria",
        ["text-3"],
        y0=40.0,
    )
    row = _table(
        "table-4",
        "Catastrophic\n1\nCould result in death",
        ["text-4"],
        y0=60.0,
    )
    page = Page(page_number=1, blocks=[caption, title, header, row])

    regions = create_table_region_blocks_for_page(page)

    assert len(regions) == 1
    assert regions[0].caption == "TABLE I. Severity categories"
    assert regions[0].source_table_block_ids == [
        "table-1",
        "table-2",
        "table-3",
        "table-4",
    ]
    assert "Catastrophic" in (regions[0].normalized_text or "")


def test_table_region_splits_two_tables() -> None:
    """A second table caption should start a separate table region."""
    table_one = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    row_one = _table("table-2", "Critical\n2", ["text-2"], y0=30.0)
    body = _paragraph(
        "paragraph-1",
        "b. To determine the appropriate probability level, use Table II.",
        ["text-3"],
        y0=60.0,
    )
    table_two = _table("table-3", "TABLE II. Probability levels", ["text-4"], y0=90.0)
    row_two = _table("table-4", "Frequent\nA", ["text-5"], y0=110.0)
    page = Page(page_number=1, blocks=[table_one, row_one, body, table_two, row_two])

    regions = create_table_region_blocks_for_page(page)

    assert len(regions) == 2
    assert regions[0].caption == "TABLE I. Severity categories"
    assert regions[1].caption == "TABLE II. Probability levels"
    assert "paragraph-1" not in regions[0].source_paragraph_block_ids


def test_table_region_includes_nearby_paragraph_row_fragments() -> None:
    """Paragraph fragments between table candidates should be included."""
    caption = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    row_label = _table("table-2", "Critical\n2", ["text-2"], y0=30.0)
    row_text = _paragraph(
        "paragraph-1",
        "Could result in severe injury or occupational illness.",
        ["text-3"],
        y0=45.0,
    )
    next_row = _table("table-3", "Marginal\n3", ["text-4"], y0=65.0)
    page = Page(page_number=1, blocks=[caption, row_label, row_text, next_row])

    regions = create_table_region_blocks_for_page(page)

    assert len(regions) == 1
    assert regions[0].source_paragraph_block_ids == ["paragraph-1"]
    assert "Could result in severe injury" in (regions[0].normalized_text or "")


def test_table_region_does_not_absorb_normal_paragraph_after_table() -> None:
    """Normal body paragraphs should stop a table region."""
    caption = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    row = _table("table-2", "Critical\n2", ["text-2"], y0=30.0)
    body = _paragraph(
        "paragraph-1",
        "b. To determine the appropriate probability level, use Table II.",
        ["text-3"],
        y0=50.0,
    )
    next_caption = _table(
        "table-3",
        "TABLE II. Probability levels",
        ["text-4"],
        y0=80.0,
    )
    next_row = _table("table-4", "Frequent\nA", ["text-5"], y0=100.0)
    page = Page(page_number=1, blocks=[caption, row, body, next_caption, next_row])

    regions = create_table_region_blocks_for_page(page)

    assert len(regions) == 2
    assert "paragraph-1" not in regions[0].source_paragraph_block_ids
    assert "To determine the appropriate probability" not in (
        regions[0].normalized_text or ""
    )


def test_table_region_does_not_group_unrelated_single_candidate() -> None:
    """A lone table candidate without caption should not be forced into a region."""
    table = _table("table-1", "Critical\n2", ["text-1"], y0=10.0)
    page = Page(page_number=1, blocks=[table])

    assert create_table_region_blocks_for_page(page) == []


def test_table_region_deduplicates_repeated_fragments_and_source_ids() -> None:
    """Repeated table/paragraph fragments should appear once in region text."""
    caption = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    table = _table("table-2", "SEVERITY CATEGORIES", ["text-2"], y0=30.0)
    duplicate_table = _table("table-2", "SEVERITY CATEGORIES", ["text-2"], y0=30.0)
    duplicate_paragraph = _paragraph(
        "paragraph-1",
        "SEVERITY CATEGORIES",
        ["text-2"],
        y0=30.0,
    )
    row = _table("table-3", "Critical\n2", ["text-3"], y0=50.0)
    page = Page(
        page_number=1,
        blocks=[caption, table, duplicate_table, duplicate_paragraph, row],
    )

    regions = create_table_region_blocks_for_page(page)

    assert len(regions) == 1
    assert (regions[0].normalized_text or "").count("SEVERITY CATEGORIES") == 1
    assert regions[0].rows.count(["SEVERITY CATEGORIES"]) == 1
    assert regions[0].source_text_block_ids == ["text-1", "text-2", "text-3"]
    assert regions[0].source_table_block_ids == ["table-1", "table-2", "table-3"]
    assert regions[0].source_paragraph_block_ids == ["paragraph-1"]


def test_table_region_includes_mil_std_table_i_final_row_fragments() -> None:
    """MIL-STD TABLE I style final rows should stay in the first region."""
    table_i = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    title = _table("table-2", "SEVERITY CATEGORIES", ["text-2"], y0=25.0)
    header = _table(
        "table-3",
        "Description\nSeverity\nCategory\nMishap Result Criteria",
        ["text-3"],
        y0=40.0,
    )
    catastrophic = _table(
        "table-4",
        "Catastrophic\n1\nCould result in death or permanent disability.",
        ["text-4"],
        y0=60.0,
        x0=190.0,
    )
    critical = _table("table-5", "Critical\n2", ["text-5"], y0=90.0, x0=190.0)
    critical_description = _paragraph(
        "paragraph-1",
        "Could result in severe injury, occupational illness, or major damage.",
        ["text-6"],
        y0=105.0,
        x0=250.0,
    )
    marginal = _table("table-6", "Marginal\n3", ["text-7"], y0=125.0, x0=190.0)
    marginal_description = _paragraph(
        "paragraph-2",
        "Could result in minor injury, occupational illness, or minor damage.",
        ["text-8"],
        y0=140.0,
        x0=250.0,
    )
    negligible = _table(
        "table-7",
        "Negligible\n4\nCould result in less than minor injury or damage.",
        ["text-9"],
        y0=160.0,
        x0=190.0,
    )
    body = _paragraph(
        "paragraph-3",
        "b. To determine the appropriate probability level as defined in Table II.",
        ["text-10"],
        y0=190.0,
    )
    table_ii = _table("table-8", "TABLE II. Probability levels", ["text-11"], y0=230.0)
    page = Page(
        page_number=1,
        blocks=[
            table_i,
            title,
            header,
            catastrophic,
            critical,
            critical_description,
            marginal,
            marginal_description,
            negligible,
            body,
            table_ii,
        ],
    )

    regions = create_table_region_blocks_for_page(page)

    assert len(regions) == 1
    assert "Negligible\n4" in (regions[0].normalized_text or "")
    assert "Could result in severe injury" in (regions[0].normalized_text or "")
    assert "Could result in minor injury" in (regions[0].normalized_text or "")
    assert "paragraph-3" not in regions[0].source_paragraph_block_ids
    assert "To determine the appropriate probability" not in (
        regions[0].normalized_text or ""
    )


def test_table_region_includes_mil_std_table_ii_final_row_fragments() -> None:
    """MIL-STD TABLE II style final row fragments should remain grouped."""
    table_ii = _table("table-1", "TABLE II. Probability levels", ["text-1"], y0=10.0)
    title = _table("table-2", "PROBABILITY LEVELS", ["text-2"], y0=25.0)
    header = _table(
        "table-3",
        "Description\nLevel\nSpecific Individual Item\nFleet or Inventory",
        ["text-3"],
        y0=40.0,
    )
    frequent = _table(
        "table-4", "Frequent\nA\nLikely to occur often.", ["text-4"], y0=60.0
    )
    probable = _table(
        "table-5", "Probable\nB\nWill occur several times.", ["text-5"], y0=85.0
    )
    occasional = _table(
        "table-6",
        "Occasional\nC\nLikely to occur sometime.",
        ["text-6"],
        y0=110.0,
    )
    remote = _table(
        "table-7", "Remote\nD\nUnlikely but possible.", ["text-7"], y0=135.0
    )
    improbable = _table(
        "table-8",
        "Improbable\nE\nSo unlikely it can be assumed occurrence may not be "
        "experienced.",
        ["text-8"],
        y0=160.0,
    )
    eliminated = _table("table-9", "Eliminated\nF", ["text-9"], y0=190.0)
    eliminated_description = _paragraph(
        "paragraph-1",
        "Incapable of occurrence. This level is used when potential hazards are "
        "identified and later eliminated.",
        ["text-10"],
        y0=205.0,
    )
    body = _paragraph(
        "paragraph-2",
        "(1) When available, the use of appropriate and representative quantitative "
        "data is preferred.",
        ["text-11"],
        y0=240.0,
    )
    page = Page(
        page_number=1,
        blocks=[
            table_ii,
            title,
            header,
            frequent,
            probable,
            occasional,
            remote,
            improbable,
            eliminated,
            eliminated_description,
            body,
        ],
    )

    regions = create_table_region_blocks_for_page(page)

    assert len(regions) == 1
    assert "Eliminated\nF" in (regions[0].normalized_text or "")
    assert "Incapable of occurrence" in (regions[0].normalized_text or "")
    assert "paragraph-1" in regions[0].source_paragraph_block_ids
    assert "paragraph-2" not in regions[0].source_paragraph_block_ids
    assert "When available" not in (regions[0].normalized_text or "")


def test_table_region_includes_mil_std_table_iii_matrix_fragments() -> None:
    """MIL-STD TABLE III matrix row fragments should stay in one region."""
    caption = _table(
        "table-1", "TABLE III. Risk assessment matrix", ["text-1"], y0=10.0
    )
    title = _table("table-2", "RISK ASSESSMENT MATRIX", ["text-2"], y0=25.0)
    severity = _table("table-3", "SEVERITY", ["text-3"], y0=40.0)
    severity_values = _table(
        "table-4",
        "Catastrophic\nCritical\nMarginal\nNegligible",
        ["text-4"],
        y0=55.0,
        x0=150.0,
    )
    severity_numbers = _table("table-5", "(1)\n(2)\n(3)\n(4)", ["text-5"], y0=70.0)
    probability = _table("table-6", "PROBABILITY", ["text-6"], y0=85.0)
    frequent = _table("table-7", "Frequent", ["text-7"], y0=100.0, x0=20.0)
    frequent_values = _table(
        "table-8",
        "(A)\nHigh\nHigh\nSerious\nMedium",
        ["text-8"],
        y0=115.0,
        x0=150.0,
    )
    probable = _table("table-9", "Probable", ["text-9"], y0=135.0, x0=20.0)
    probable_values = _table(
        "table-10",
        "(B)\nHigh\nHigh\nSerious\nMedium",
        ["text-10"],
        y0=150.0,
        x0=150.0,
    )
    occasional = _table("table-11", "Occasional", ["text-11"], y0=170.0, x0=20.0)
    occasional_values = _table(
        "table-12",
        "(C)\nHigh\nSerious\nMedium\nLow",
        ["text-12"],
        y0=185.0,
        x0=150.0,
    )
    remote = _table("table-13", "Remote", ["text-13"], y0=205.0, x0=20.0)
    remote_values = _table(
        "table-14",
        "(D)\nSerious\nMedium\nMedium\nLow",
        ["text-14"],
        y0=220.0,
        x0=150.0,
    )
    improbable = _table("table-15", "Improbable", ["text-15"], y0=240.0, x0=20.0)
    improbable_values = _table(
        "table-16",
        "(E)\nMedium\nMedium\nMedium\nLow",
        ["text-16"],
        y0=255.0,
        x0=150.0,
    )
    eliminated = _table("table-17", "Eliminated", ["text-17"], y0=275.0, x0=20.0)
    eliminated_values = _table(
        "table-18",
        "(F)\nEliminated",
        ["text-18"],
        y0=290.0,
        x0=150.0,
    )
    body = _paragraph(
        "paragraph-1",
        "d. The definitions in Tables I and II, and the RACs in Table III shall "
        "be used to assess risk.",
        ["text-19"],
        y0=330.0,
    )
    page = Page(
        page_number=1,
        blocks=[
            caption,
            title,
            severity,
            severity_values,
            severity_numbers,
            probability,
            frequent,
            frequent_values,
            probable,
            probable_values,
            occasional,
            occasional_values,
            remote,
            remote_values,
            improbable,
            improbable_values,
            eliminated,
            eliminated_values,
            body,
        ],
    )

    regions = create_table_region_blocks_for_page(page)

    assert len(regions) == 1
    assert "Frequent" in (regions[0].normalized_text or "")
    assert "(A)\nHigh\nHigh\nSerious\nMedium" in (regions[0].normalized_text or "")
    assert "Improbable" in (regions[0].normalized_text or "")
    assert "(F)\nEliminated" in (regions[0].normalized_text or "")
    assert "paragraph-1" not in regions[0].source_paragraph_block_ids
    assert "The definitions in Tables" not in (regions[0].normalized_text or "")


def test_semantic_blocks_table_region_suppresses_low_level_duplicates() -> None:
    """TableRegionBlock should win over low-level table and paragraph fragments."""
    table = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    duplicate_table = _table("table-2", "Critical\n2", ["text-2"], y0=30.0)
    fragment = _paragraph(
        "paragraph-1",
        "Could result in severe injury.",
        ["text-3"],
        y0=45.0,
    )
    body = _paragraph("paragraph-2", "Ordinary body paragraph.", ["text-4"], y0=90.0)
    region = _table_region(
        source_text_block_ids=["text-1", "text-2", "text-3"],
        source_table_block_ids=["table-1", "table-2"],
        source_paragraph_block_ids=["paragraph-1"],
    )
    page = Page(
        page_number=1,
        blocks=[table, duplicate_table, fragment, body, region],
    )

    semantic_blocks = get_semantic_blocks_for_page(page)

    assert region in semantic_blocks
    assert table not in semantic_blocks
    assert duplicate_table not in semantic_blocks
    assert fragment not in semantic_blocks
    assert body in semantic_blocks


def test_semantic_markdown_renders_table_region_without_low_level_duplicates() -> None:
    """Semantic Markdown should prefer table regions over low-level table blocks."""
    table = _table("table-1", "TABLE I. Severity categories", ["text-1"], y0=10.0)
    row = _table("table-2", "Critical\n2", ["text-2"], y0=30.0)
    body = _paragraph("paragraph-1", "Ordinary body paragraph.", ["text-3"], y0=90.0)
    region = _table_region(
        source_text_block_ids=["text-1", "text-2"],
        source_table_block_ids=["table-1", "table-2"],
    )
    document = _document([table, row, body, region])

    markdown = document_to_semantic_markdown(document)

    assert "**Table region candidate**" in markdown
    assert "TABLE I. Severity categories\nSEVERITY CATEGORIES" in markdown
    assert "**Table candidate**" not in markdown
    assert "Ordinary body paragraph." in markdown


def test_semantic_markdown_keeps_table_ii_as_one_region() -> None:
    """Semantic Markdown should not show a second region for continuation rows."""
    caption = _table("table-1", "TABLE II. Probability levels", ["text-1"], y0=10.0)
    header = _table("table-2", "PROBABILITY LEVELS", ["text-2"], y0=25.0)
    remote = _table("table-3", "Remote\nD\nUnlikely but possible.", ["text-3"], y0=45.0)
    improbable = _table(
        "table-4",
        "Improbable\nE\nSo unlikely it can be assumed occurrence may not be "
        "experienced.",
        ["text-4"],
        y0=140.0,
    )
    eliminated = _table("table-5", "Eliminated\nF", ["text-5"], y0=160.0)
    body = _paragraph(
        "paragraph-1",
        "(1) When available, the use of appropriate and representative quantitative "
        "data is preferred.",
        ["text-6"],
        y0=195.0,
    )
    page = Page(
        page_number=1, blocks=[caption, header, remote, improbable, eliminated, body]
    )
    regions = create_table_region_blocks_for_page(page)
    page.blocks.extend(regions)
    document = _document(page.blocks)

    markdown = document_to_semantic_markdown(document)

    assert len(regions) == 1
    assert markdown.count("**Table region candidate**") == 1
    assert "Improbable\nE" in markdown
    assert "Eliminated\nF" in markdown
    assert "**Table candidate**" not in markdown
    assert "When available" in markdown
