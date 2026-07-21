# StructuredDocument Contract Foundation

Date: 2026-07-21
Status: Foundation, parser-model mapping, and section hierarchy implemented as Python API
Phase: 13B foundation; 13C mapper; 13D section hierarchy

This document describes the internal foundation for emitting
`techdoc-structured-document / 0.1.0` records, the Phase 13C parser-model
mapper, and the Phase 13D section hierarchy enrichment. The foundation and
mapper are additive and isolated. They do not change parser extraction, reading
order, heading detection, chunking, validation gates, existing JSON outputs,
Markdown outputs, manifest outputs, or CLI behavior.

## 1. Scope

Phase 13B adds contract constants, contract dataclasses, deterministic
serialization helpers, a synthetic minimum fixture, and regression tests. The
module lives under `techdoc_parser.contracts` and is not imported by the parser
runtime or CLI.

## 2. Non-Scope

Phase 13B through Phase 13E1 does not:

- Add CLI flags or output files.
- Modify the current output manifest.
- Import or modify AviationRAG.
- Parse real or proprietary documents.
- Generate embeddings, use Astra, use FAISS, or perform ingestion.
- Infer checksums, revisions, issue numbers, dates, page labels, confidence
  scores, table cells, figure assets, figure regions, equations, admonitions,
  or cross-references.
- Detect new headings or repair parser heading levels.

## 2.1 Phase 13C Parser Mapping

Phase 13C adds a pure mapper in:

```text
src/techdoc_parser/contracts/structured_document_mapper.py
```

The mapper converts existing parser `Document`, `Page`, `Block`, and
`SourceLocation` objects into the contract dataclasses. It maps document
metadata, pages, blocks, source spans, bounding boxes, raw text, normalized
text, deterministic page/block indexes, and conservative block content types.

Advanced entity root collections remained empty in Phase 13C. No CLI
integration exists, current outputs remain unchanged, and no provenance is
fabricated.

## 2.2 Phase 13D Section Hierarchy

Phase 13D adds a pure hierarchy builder in:

```text
src/techdoc_parser/contracts/structured_document_hierarchy.py
```

The mapper uses current `HeadingBlock` objects to create
`StructuredDocumentSection` records, parent-child relationships, block
`section_id` assignments, and section source spans. The builder preserves raw
heading text, optional normalized heading text, existing heading levels,
explicit section numbers, appendix/annex labels, and AMC/GM-style clause
identifiers when present. Section paths use validator-compatible display text
while `raw_heading` preserves the exact source heading. It does not create
missing headings, missing parent levels, confidence scores, page labels,
character offsets, checksums, or advanced entity records.

## 2.3 Phase 13E1 Table And Figure-Caption Mapping

Phase 13E1 adds pure root entity mapping in:

```text
src/techdoc_parser/contracts/structured_document_entities.py
```

The mapper reads existing `TableBlock`, `TableRegionBlock`, and `FigureBlock`
candidate evidence that is already present in `Document.pages[].blocks`. It
populates root `tables` and `figures` with deterministic IDs, exact source text
or caption text, page refs, source spans, source block references, optional
bounding boxes, optional section IDs, and candidate status.

Table structure remains unclaimed: `columns`, `rows`, `cells`, `header_rows`,
and `merged_cells` are emitted as empty lists because current parser rows are
line fragments. Figure assets and visual-region understanding remain absent
unless a future parser phase supplies real `image_path` evidence.

## 3. Module

The foundation is implemented in:

```text
src/techdoc_parser/contracts/structured_document.py
```

The package namespace re-exports the contract API from:

```text
src/techdoc_parser/contracts/__init__.py
```

The top-level `techdoc_parser` package is unchanged.

## 4. Schema Identity

The contract identity is:

```text
schema_name: techdoc-structured-document
schema_version: 0.1.0
parser_name: techdoc-parser
parser_version: 0.1.0
```

Unsupported structured-document schema versions are rejected by
`require_supported_structured_document_version()` and by
`build_structured_document()`.

## 5. Root Object

Serialized records use this deterministic top-level order:

```text
schema_name
schema_version
parser_name
parser_version
document
pages
sections
blocks
tables
figures
equations
admonitions
cross_references
```

Unsupported or not-yet-populated entity collections are emitted as empty lists.
As of Phase 13E1, `tables` and `figures` may be populated from current
candidate evidence by the parser-model mapper; `equations`, `admonitions`, and
`cross_references` remain empty unless callers supply records explicitly.

## 6. Document Metadata Policy

`StructuredDocumentMetadata` requires `document_id` and `source_filename`.
Optional fields are emitted only when supplied:

- `document_title`
- `canonical_title`
- `page_count`
- `source_hash`
- `revision`
- `issue`
- `effective_date`

The filename is not used as a title. File timestamps are not used as revision
or effective-date metadata. Source hashes are not generated by this foundation.

## 7. Page Policy

`StructuredDocumentPage` requires:

- `page_id`
- `pdf_page_index`
- `page_number`

`pdf_page_index` is zero-based. `page_number` is one-based. `printed_page_label`
is emitted as `null` when unknown for explicit compatibility with the target
validator.

## 8. Section Policy

Sections are optional in the foundation. Empty `sections` remains valid when no
truthful section tree is available or when section enrichment is disabled. When
supplied, `StructuredDocumentSection` preserves hierarchy fields plus optional
source evidence:

- `section_id`
- `level`
- `title`
- `parent_section_id`
- `section_number`
- `path`
- `source_span`
- `raw_heading`
- `normalized_heading`
- `clause_identifier`

No confidence value is emitted unless a future phase adds a truthful confidence
model.

## 9. Block Policy

`StructuredDocumentBlock` requires:

- `block_id`
- `block_type`
- `text`
- `source_span`

Optional indexes and page references are emitted only when supplied. The
foundation preserves caller order and does not sort, repair, renumber, or infer
reading order.

## 10. Source Span Policy

`StructuredSourceSpan` supports page ranges, PDF page-index ranges, printed
page-label ranges, bounding boxes, source block references, extraction method,
and character offsets. Missing source-span details remain absent. The
foundation does not fabricate character offsets, source hashes, page labels, or
confidence values.

## 11. Advanced Entity Policy

Root collections for `tables`, `figures`, `equations`, `admonitions`, and
`cross_references` exist so phases can populate them without changing the root
shape. Phase 13E1 populates `tables` and `figures` only from existing
candidate-level parser evidence. It does not reconstruct table cells, infer
table continuation, extract figure assets, infer figure numbers, or create
equation, admonition, or cross-reference records.

## 12. Determinism And Side Effects

Serialization uses `json.dumps(..., ensure_ascii=False)` and does not write
files. Importing the module performs no filesystem, environment, timestamp, or
network operations.

## 13. Backward Compatibility

The current parser model, JSON exporters, Markdown exporters, validation
exports, gate exports, output manifest, and CLI behavior remain unchanged.
Existing `document.json` and `manifest.json` do not gain `schema_name` or
structured-document root fields in Phase 13B through Phase 13E1.

## 14. Fixture

The synthetic fixture is:

```text
tests/fixtures/structured_document/minimal_structured_document.json
tests/fixtures/structured_document/mapped_structured_document_with_sections.json
tests/fixtures/structured_document/mapped_structured_document_with_tables_figures.json
```

It is intentionally not derived from real source material. It contains no
source checksum because Phase 13B does not compute or fabricate checksums.

## 15. Future Phases

Phase 13C completed contract-local mapping from the current `Document`, `Page`,
`Block`, `SourceLocation`, and `BoundingBox` objects into this root shape, with
explicit tests that existing outputs remain unchanged.

Phase 13D completed contract-local section hierarchy and source-span enrichment.

Phase 13E1 completed contract-local table and figure-caption root mapping from
existing candidate evidence only. Recommended next work is either equation,
admonition, or cross-reference mapping from truthful parser evidence, true table
structure/parser enhancements, or optional CLI/manifest integration as a
separate scoped phase.
