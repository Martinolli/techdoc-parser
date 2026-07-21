# StructuredDocument Parser Model Mapping

Date: 2026-07-21
Status: Phase 13C through Phase 13F implemented as a Python contract API

## 1. Purpose

Phase 13C adds a pure mapper from the current parser core model to the
`techdoc-structured-document / 0.1.0` contract. The mapper produces a truthful
minimum structured-document record from existing `Document`, `Page`, `Block`,
and `SourceLocation` evidence.

Phase 13D adds contract-local section hierarchy enrichment from existing
`HeadingBlock` objects. It creates durable section records, parent-child links,
block `section_id` assignments, and aggregate section source spans without
changing parser extraction, heading detection, chunking, current output files,
or CLI behavior.

Phase 13F adds root cross-reference mapping from explicit textual evidence and
a confidence policy that omits current placeholder confidence values.

The implementation lives in:

```text
src/techdoc_parser/contracts/structured_document_mapper.py
src/techdoc_parser/contracts/structured_document_hierarchy.py
src/techdoc_parser/contracts/structured_document_references.py
src/techdoc_parser/contracts/structured_document_confidence.py
```

It is available through `techdoc_parser.contracts` as:

```text
map_document_to_structured_document()
map_document_with_options()
StructuredDocumentMappingOptions
map_block_type_to_content_type()
```

## 2. Source Parser Models

The mapper uses the public core dataclasses in `techdoc_parser.core.models`:

| Parser model | Confirmed fields used |
| --- | --- |
| `Document` | `id`, `source_path`, `metadata`, `pages` |
| `DocumentMetadata` | `title` |
| `Page` | `page_number`, `blocks` |
| `Block` | `id`, `source`, `block_type`, `text`, `normalized_text` |
| `TextBlock` | page furniture flags |
| `HeadingBlock` | `text`, `normalized_text`, `level` |
| `SourceLocation` | `page_number`, `bbox`, `extraction_method` |
| `BoundingBox` | `x0`, `y0`, `x1`, `y1` |

`Document.pages` contains pages. `Page.blocks` contains raw and derived blocks.
Blocks optionally reference a `SourceLocation`. Page numbers are one-based in
the loader because `PDFLoader.load()` enumerates PDF pages with `start=1`.

## 3. Target Contract

The mapper constructs the existing frozen contract dataclasses from
`techdoc_parser.contracts.structured_document`:

- `StructuredDocumentMetadata`
- `StructuredDocumentPage`
- `StructuredDocumentBlock`
- `StructuredDocumentSection`
- `StructuredSourceSpan`
- `StructuredBoundingBox`
- `StructuredDocument`

The root contract identity remains:

```text
schema_name = techdoc-structured-document
schema_version = 0.1.0
parser_name = techdoc-parser
parser_version = 0.1.0
```

## 4. Mapping Boundary

The mapper does not change extraction, normalization, heading detection,
chunking, validation reports, ingestion gates, current JSON output, current
Markdown output, manifest output, or CLI arguments. It does not read or write
files, generate timestamps, generate random values, import AviationRAG, process
real documents, generate embeddings, use Astra DB, or use FAISS.

## 5. Document Metadata Mapping

| Target field | Source | Decision |
| --- | --- | --- |
| `document_id` | caller option | Required explicit caller value. `Document.id` is not used because it is derived from the source path stem. |
| `source_filename` | `Document.source_path` | Basename only. Absolute machine-specific paths are not serialized. |
| `document_title` | caller option | Preserved only when explicitly supplied. The filename is not used as a title. |
| `canonical_title` | `Document.metadata.title` | Mapped when the parser extracted a PDF metadata title. |
| `page_count` | mapped page records | `len(mapped_pages)`. |
| `source_hash` | caller option `source_checksum` | Preserved only when supplied; no checksum is generated. |
| `revision`, `issue`, `effective_date` | caller options | Preserved only when supplied; file names and timestamps are not used. |

## 6. Page Mapping

`Page.page_number` is one-based. The mapper derives zero-based
`pdf_page_index` as `page_number - 1` and emits deterministic page IDs as
`page-0001`, `page-0002`, and so on.

Printed page labels remain `null`. Rotation, page role, OCR confidence, and
page confidence are not mapped because the current `Page` model does not expose
contract-compatible values for them.

## 7. Block-ID Policy

Existing non-empty parser block IDs are preserved. If a parser block ID is
empty, the mapper creates a deterministic fallback ID from stable structural
inputs:

```text
<document_id>:p<pdf_page_index>:b<page_block_index>
```

This fallback is deterministic and readable. It is not a hash and does not use
timestamps, absolute paths, or random values.

## 8. Block-Order Policy

The mapper traverses `Document.pages` in list order and each `Page.blocks` in
list order. It emits:

- `page_block_index`: zero-based index within `Page.blocks`
- `document_block_index`: zero-based index in flattened traversal order

These are exporter-derived order indexes. The mapper does not sort by geometry,
recalculate reading order, or claim semantic reading-order confidence.

## 9. Content-Type Mapping

The mapper uses a central conservative mapping:

| Parser block type | Target block type |
| --- | --- |
| `text` | `paragraph` |
| page-furniture `TextBlock` | `metadata` |
| `paragraph` | `paragraph` |
| `heading` | `section_heading` |
| `table` | `table` |
| `table_region` | `table` |
| `figure` | `figure_caption` |
| `formula` | `equation` |
| unknown | `unknown` |

Unknown source block types are not discarded. They map to `unknown` when raw
text is present. Blocks without non-empty raw text are rejected instead of
having text fabricated from normalized text, filenames, captions, or labels.

## 10. SourceLocation Mapping

Each mapped block receives a single-page `StructuredSourceSpan`.

| Target field | Source | Decision |
| --- | --- | --- |
| `page_start`, `page_end` | `SourceLocation.page_number`, else owning `Page.page_number` | Single-page span only. |
| `pdf_page_index_start`, `pdf_page_index_end` | page number minus one | Zero-based index for the same page. |
| `bbox` | `SourceLocation.bbox` | Mapped when present. |
| `source_block_ids` | mapped block ID | References the mapped block itself. |
| `extraction_method` | `SourceLocation.extraction_method` | Mapped when present. |
| character offsets | none | Not fabricated. |
| confidence | `SourceLocation.confidence` | Not mapped in Phase 13C because current `1.0` values are extraction placeholders. |

## 11. Bounding-Box Handling

The current `BoundingBox` is a dataclass with numeric `x0`, `y0`, `x1`, and
`y1` fields. The mapper preserves coordinate order and values exactly, including
zero-valued and floating-point coordinates. It does not normalize coordinates,
convert units, infer page dimensions, or repair invalid boxes.

## 12. Unknown-Value Policy

Missing metadata remains absent. Unknown printed page labels remain `null`.
Unknown block types map to `unknown` if raw text exists. Unknown section,
revision, checksum, confidence, and character-offset data is not invented.

## 13. Section Hierarchy Mapping

When `include_sections=True` (the default), the mapper uses only existing
`HeadingBlock` records as section evidence. It does not re-detect headings,
repair heading levels, or inspect layout. If no heading blocks exist, `sections`
remains an empty list and blocks do not receive `section_id`.

Section IDs use deterministic document-local sequence IDs:

```text
<document_id>:s0001
<document_id>:s0002
```

Parent-child hierarchy follows the current `HeadingBlock.level` values:

| Case | Decision |
| --- | --- |
| First heading level is greater than 1 | It becomes a root section; its original level is preserved. |
| Next heading has a deeper level | It becomes a child of the nearest preceding lower-level heading. |
| Next heading has the same level | It becomes a sibling; deeper stack entries are closed. |
| Heading levels skip, such as 1 to 4 | No missing intermediary sections are fabricated. |
| Blocks before the first heading | They remain unassigned. |
| Blocks after a heading | They receive the active section ID until another heading changes context. |

Number and title parsing is narrow. Explicit numeric headings, appendices,
annexes, and AMC/GM-style clause prefixes are preserved when present. Paths use
the validator-compatible display form `section_number + title`; exact source
heading text remains available in `raw_heading`. Unnumbered headings keep their
heading text as the section title and path item. The mapper does not fabricate
section numbers, clause identifiers, confidence values, page labels, character
offsets, or source hashes.

Section source spans are computed from blocks directly assigned to the section.
They include page and PDF-index ranges, ordered source block IDs, and a common
extraction method when all direct blocks agree. Multi-block section spans do not
merge bounding boxes; a section-level `bbox` is emitted only when a section has
one directly assigned block with a real block bbox.

Set `include_sections=False` to preserve the Phase 13C no-section contract
shape for compatibility tests or callers that are not ready for section IDs.

## 14. Table And Figure-Caption Entities

Phase 13E1 maps existing `TableBlock`, `TableRegionBlock`, and `FigureBlock`
candidate evidence into root `tables` and `figures` after block and section
mapping. The root entities reuse mapped block source spans and section IDs so
entity provenance matches the block collection.

Table root entities preserve current text, optional captions, candidate status,
source text/table/paragraph block references, page refs, source spans, optional
bounding boxes, and section paths. `TableBlock` maps with
`extraction_status: "candidate"`; `TableRegionBlock` maps with
`extraction_status: "region_only"`.

Figure root entities preserve exact caption text, source caption text, candidate
status, source text block references, page refs, source spans, optional bounding
boxes, and section paths. `FigureBlock` maps with
`extraction_status: "caption_candidate"`.

The mapper does not turn current table line fragments into semantic rows,
columns, or cells. It does not infer table continuation, figure numbers, figure
assets, figure regions, descriptions, or nearby explanatory relationships.
`asset_reference` is emitted only when `FigureBlock.image_path` is a non-empty
value.

## 15. Equation And Admonition Entities

Phase 13E2 maps conservative equation evidence and explicit-label admonition
evidence into root `equations` and `admonitions` after block and section
mapping. The root entities reuse mapped block source spans and section IDs so
entity provenance matches the block collection.

Equation root entities preserve exact `raw_text`, optional explicit equation
labels, optional `FormulaBlock.latex` notation as `normalized_representation`,
page refs, source spans, optional bounding boxes, and section paths. Plain
paragraph equations are not normalized, interpreted, or converted into prose.

Admonition root entities preserve exact labels, validator-compatible normalized
types, body text, page refs, source spans, optional bounding boxes, and section
paths. Detection requires explicit starting labels such as `WARNING`, `CAUTION`,
`NOTE`, `IMPORTANT`, or `SAFETY NOTICE`; the mapper does not infer safety
severity from wording or typography.

## 16. Cross-Reference Entities

Phase 13F maps explicit textual references into root `cross_references` after
sections and entity roots exist. The mapper detects only paragraph/unknown block
references introduced by explicit phrases such as `see`, `refer to`,
`in accordance with`, `as specified in`, `as described in`, and `according to`.

Each reference preserves exact raw reference text, target identifier, reference
type, source block IDs, source span, page refs, optional section refs, and a
validator-compatible resolution status. Resolution is exact only against known
sections, tables, figures, and equations. Unmatched local references remain
`unresolved`, duplicate matches become `ambiguous`, external document IDs become
`external`, and unsupported cases remain `not_attempted`.

The mapper does not use fuzzy matching, PDF link metadata, external lookup,
semantic similarity, or fabricated target IDs.

## 17. Confidence Policy

The mapper omits confidence fields unless a meaningful numeric evidence source
exists. Current `SourceLocation.confidence` values are not promoted because
native PyMuPDF extraction currently uses placeholder `1.0` values. Confidence
helpers reject booleans, non-numeric values, and out-of-range numbers.

## 18. Unsupported Entities

Formula discovery from PDF layout and broad admonition classification remain
future parser work.

## 19. Guarantees

The mapper is deterministic, import-safe, filesystem-independent, and
non-mutating. Repeated mapping of the same parser object with the same options
produces identical contract JSON. The mapper does not invoke current exporters
or depend on CLI orchestration.

## 20. Backward Compatibility

Existing parser public models, constructors, JSON exporters, Markdown exporters,
validation report exports, gate exports, output manifests, and CLI arguments
remain unchanged. The structured-document mapper is a Python API only.

## 21. Known Gaps

- No true table row, column, cell, merged-cell, or continuation mapping.
- No figure asset extraction, figure number extraction, or figure-region
  understanding.
- No formula discovery from PDF layout, mathematical semantics, or variable
  extraction.
- No inferred admonition safety severity or typography-only admonition
  detection.
- Cross-reference detection is explicit-text only; no PDF links, bookmarks,
  fuzzy matching, external lookup, or fabricated target IDs.
- No source checksum ownership beyond explicit caller-supplied values.
- No printed page-label extraction.
- No character offsets.
- No confidence semantics beyond omission of placeholder values and validation
  of future real numeric confidence values.
- No CLI structured-document output.
- No manifest integration for structured-document artifacts.
- Heading hierarchy accuracy remains bounded by the current `HeadingBlock`
  evidence.

## 22. Next Phase

Phase 13F is implemented as contract-local cross-reference mapping and
confidence policy. Next work should keep CLI/manifest integration separate from
entity mapping and should not add true table structure, figure assets, broad
formula discovery, or confidence fields until the parser has truthful evidence
for them.
