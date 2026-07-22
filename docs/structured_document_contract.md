# StructuredDocument Contract Foundation

Date: 2026-07-22
Status: Foundation, mapper, entity mapping, references, confidence policy, optional file export, and offline compatibility gate implemented
Phase: 13B foundation; 13C mapper; 13D section hierarchy; 13E1 tables/figures; 13E2 equations/admonitions; 13F references/confidence policy; 13G optional API/CLI/manifest export; 13H AviationRAG compatibility gate

This document describes the internal foundation for emitting
`techdoc-structured-document / 0.1.0` records, the Phase 13C parser-model
mapper, Phase 13D section hierarchy enrichment, Phase 13E entity mapping, and
Phase 13F cross-reference plus confidence-policy mapping, and Phase 13G
optional file export.
The foundation and mapper are additive and isolated. They do not change parser
extraction, reading order, heading detection, chunking, validation gates,
existing JSON outputs, Markdown outputs, or default CLI behavior.

## 1. Scope

Phase 13B adds contract constants, contract dataclasses, deterministic
serialization helpers, a synthetic minimum fixture, and regression tests. The
module lives under `techdoc_parser.contracts` and is not imported by the parser
runtime or CLI.

## 2. Non-Scope

Phase 13B through Phase 13H does not:

- Create structured-document files unless explicitly requested.
- Replace current CLI output files or manifest behavior.
- Import or modify AviationRAG.
- Parse real or proprietary documents.
- Generate embeddings, use Astra, use FAISS, or perform ingestion.
- Infer checksums, revisions, issue numbers, dates, page labels, confidence
  scores, table cells, figure assets, figure regions, mathematical meaning,
  safety severity, or false cross-reference targets.
- Detect new headings or repair parser heading levels.

## 2.7 Phase 13H AviationRAG Compatibility Gate

Phase 13H adds an isolated compatibility package and standalone CLI:

```text
src/techdoc_parser/compatibility/aviationrag_gate.py
tools/compatibility/run-aviationrag-compatibility-gate.py
```

The gate validates an already written structured-document artifact and manifest
against source bytes, manifest checksum records, metadata consistency,
cross-reference status rules, confidence field policy, deterministic output
evidence, and the external AviationRAG structured-document validator. The
AviationRAG validator is called only through `subprocess`; normal parser
modules do not import AviationRAG and no files are written inside the
AviationRAG repository.

## 2.6 Phase 13G Optional File Export

Phase 13G adds public construction and file APIs plus optional CLI output in:

```text
src/techdoc_parser/contracts/structured_document_mapper.py
src/techdoc_parser/exporters/structured_document.py
```

`build_structured_document_artifact()` is a pure provisional construction API
that reuses the existing mapper. `export_structured_document()` computes a
source SHA-256 from the exact source file bytes, maps the parsed document,
writes deterministic UTF-8 JSON, and returns artifact metadata. The CLI writes
this file only when `--structured-document-output` and
`--structured-document-id` are supplied. Manifest registration is additive and
occurs only when both structured-document output and manifest output are
requested.

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

## 2.4 Phase 13E2 Equation And Admonition Mapping

Phase 13E2 adds pure root entity mapping in:

```text
src/techdoc_parser/contracts/structured_document_equations_admonitions.py
```

The mapper reads existing `FormulaBlock` evidence, conservative paragraph
equation evidence, and explicit-label admonition text that is already present in
`Document.pages[].blocks`. It populates root `equations` and `admonitions` with
deterministic IDs, exact raw text, page refs, source spans, source block
references, optional bounding boxes, optional section IDs, and label/type fields
where truthful.

Equation semantics, formula discovery from PDF layout, safety severity
classification, typography-only admonition detection, and confidence scores
remain absent.

## 2.5 Phase 13F Cross-References And Confidence Policy

Phase 13F adds explicit textual cross-reference detection in:

```text
src/techdoc_parser/structure/cross_references.py
```

and contract-local mapping in:

```text
src/techdoc_parser/contracts/structured_document_references.py
src/techdoc_parser/contracts/structured_document_confidence.py
```

The mapper reads paragraph and unknown blocks only, extracts explicit
references introduced by phrases such as `see`, `refer to`,
`in accordance with`, `as specified in`, `as described in`, and
`according to`, then resolves only by exact local identifiers already present in
sections, tables, figures, or equations. Supported statuses are `resolved`,
`unresolved`, `external`, `ambiguous`, and `not_attempted`.

Confidence policy is intentionally conservative. Current
`SourceLocation.confidence` values are not promoted into structured-document
confidence fields because native PyMuPDF values are placeholders. Confidence
fields are emitted only when a real numeric value in the inclusive range
`0.0..1.0` exists; booleans and out-of-range values are rejected.

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
As of Phase 13F, `tables`, `figures`, `equations`, `admonitions`, and
`cross_references` may be populated from current candidate evidence by the
parser-model mapper.

## 6. Document Metadata Policy

`StructuredDocumentMetadata` requires `document_id` and `source_filename`.
Optional fields are emitted only when supplied:

- `document_title`
- `document_number`
- `canonical_title`
- `page_count`
- `source_hash`
- `revision`
- `issue`
- `effective_date`

The filename is not used as a title. File timestamps are not used as revision
or effective-date metadata. Phase 13G computes source hashes only in the
file-oriented API from exact source bytes; the pure construction API preserves
caller-supplied checksums only.

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
candidate-level parser evidence. Phase 13E2 populates `equations` and
`admonitions` only from conservative or explicit evidence. Phase 13F populates
`cross_references` only from explicit textual reference phrases and exact
target evidence. These phases do not reconstruct table cells, infer table
continuation, extract figure assets, infer figure numbers, parse mathematical
meaning, infer safety severity, fabricate reference targets, or emit
placeholder confidence values.

## 12. Determinism And Side Effects

Serialization uses `json.dumps(..., ensure_ascii=False)`. The pure contract
module does not write files. The Phase 13G writer adds a final newline, writes
UTF-8, creates parent directories, rejects existing destinations unless
overwrite is explicit, and uses a sibling temporary file plus atomic replacement
where supported. Importing the module performs no filesystem, environment,
timestamp, checksum, or network operations.

## 13. Backward Compatibility

The current parser model, JSON exporters, Markdown exporters, validation
exports, gate exports, and default CLI behavior remain unchanged. Existing
`document.json` does not gain `schema_name` or structured-document root fields.
`manifest.json` shape is unchanged unless a structured-document artifact is
explicitly requested and successfully written. The Phase 13H compatibility
report is a separate optional report and is not added to the normal output
package by default.

## 14. Fixture

The synthetic fixture is:

```text
tests/fixtures/structured_document/minimal_structured_document.json
tests/fixtures/structured_document/mapped_structured_document_with_sections.json
tests/fixtures/structured_document/mapped_structured_document_with_tables_figures.json
tests/fixtures/structured_document/mapped_structured_document_with_equations_admonitions.json
tests/fixtures/structured_document/mapped_structured_document_with_references_confidence.json
tests/fixtures/compatibility/aviationrag_validator_pass.json
tests/fixtures/compatibility/aviationrag_validator_warning.json
tests/fixtures/compatibility/aviationrag_validator_fail.json
```

It is intentionally not derived from real source material. Legacy fixtures
without file-oriented export do not contain source checksums because pure
mapping does not compute or fabricate them.

## 15. Future Phases

Phase 13C completed contract-local mapping from the current `Document`, `Page`,
`Block`, `SourceLocation`, and `BoundingBox` objects into this root shape, with
explicit tests that existing outputs remain unchanged.

Phase 13D completed contract-local section hierarchy and source-span enrichment.

Phase 13E1 completed contract-local table and figure-caption root mapping from
existing candidate evidence only.

Phase 13E2 completed contract-local equation and admonition root mapping from
truthful parser evidence only.

Phase 13F completed contract-local cross-reference mapping and confidence
policy.

Phase 13G completed optional API, deterministic file output, checksum ownership,
and manifest registration without creating output by default.

Phase 13H completed formal offline AviationRAG compatibility gating without
adding a runtime dependency, changing parser defaults, modifying AviationRAG, or
performing ingestion. Recommended next work is a controlled approved-document
accuracy pilot, true table structure/parser enhancements, or formula discovery
as a separate scoped phase.
