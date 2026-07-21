# Structured-Document Table And Figure-Caption Mapping

Date: 2026-07-21
Status: Phase 13E1 implemented as a Python contract API

## Purpose

Phase 13E1 maps existing `TableBlock`, `TableRegionBlock`, and `FigureBlock`
candidate evidence into the root `tables` and `figures` collections of the
internal `techdoc-structured-document / 0.1.0` contract object.

The implementation is additive and contract-local. It does not alter PDF
extraction, OCR, reading order, block creation, table detection, table region
grouping, figure-caption detection, chunking, current JSON output, Markdown
output, manifests, validation reports, validation gates, or CLI behavior.

## Source Evidence

The mapper uses only parser objects already present in `Document.pages[].blocks`:

| Parser evidence | Contract root collection | Status |
| --- | --- | --- |
| `TableBlock` | `tables` | `extraction_status: "candidate"` |
| `TableRegionBlock` | `tables` | `extraction_status: "region_only"` |
| `FigureBlock` | `figures` | `extraction_status: "caption_candidate"` |

Root entity IDs are deterministic and distinct from block IDs:

```text
<document_id>:p<pdf_page_index>:t<sequence>
<document_id>:p<pdf_page_index>:f<sequence>
```

Existing block IDs remain unchanged and are referenced through
`source_block_ids` and `source_span.source_block_ids`.

## Table Policy

Root table entities preserve:

- exact mapped block text
- optional parser caption when present
- page refs and source span
- optional bounding box when present
- section ID and section path when hierarchy enrichment assigned them
- parser source text/table/paragraph block references when present
- candidate status

Root table entities intentionally emit empty `columns`, `rows`, `cells`,
`header_rows`, and `merged_cells` because current parser table evidence is
candidate-level text or region evidence. Current `TableBlock.rows` and
`TableRegionBlock.rows` are line fragments, not reconstructed table cells.

The mapper does not infer table headers, continuation status, merged cells,
column geometry, row semantics, or multi-page table relationships.

## Figure Policy

Root figure entities preserve:

- exact caption/source-caption text from the mapped figure-caption block
- page refs and source span
- optional bounding box when present
- section ID and section path when hierarchy enrichment assigned them
- parser source text block references
- candidate status

`asset_reference` is emitted only if the parser `FigureBlock.image_path` is a
non-empty value. Current loader behavior does not populate image assets, so the
field is normally absent. The mapper does not infer figure numbers, figure type,
visual content, region boundaries, descriptions, or relationships to nearby
paragraphs.

## Compatibility

The Phase 13E1 fixture is:

```text
tests/fixtures/structured_document/mapped_structured_document_with_tables_figures.json
```

The focused test module is:

```text
tests/test_structured_document_tables_figures.py
```

Existing parser output and manifest tests remain responsible for proving that
current output packages do not gain structured-document root fields unless a
future scoped phase adds explicit CLI/export integration.

## Remaining Gaps

- True table row, column, and cell reconstruction is not implemented.
- Table continuation and merged-cell detection are not implemented.
- Figure asset extraction and image understanding are not implemented.
- Figure numbers and figure relationships are not implemented.
- Cross-reference root entity mapping remains future work.
- Equation and admonition root entity mapping is handled separately by Phase
  13E2.
- Structured-document CLI and manifest output remain future work.
