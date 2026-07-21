# AviationRAG StructuredDocument Contract Gap Analysis

Repository state reflected: Phase 13C working tree after
`9ff79fb` (`feat(contract): add structured document foundation`) on `main`,
aligned with `origin/main` after `git fetch origin --prune`.

This document was created for Phase 13A analysis and documentation only. Phase
13B later added an isolated `techdoc_parser.contracts` foundation for
`techdoc-structured-document / 0.1.0`. Phase 13C adds a pure parser-model mapper
for existing document, page, block, source-location, and bounding-box evidence.
It still does not change parser behavior, change extraction or chunking
behavior, add CLI arguments, modify current output formats, process real
documents, or modify AviationRAG.

## 8.1 Executive Summary

`techdoc-parser` is close to the target contract for native-text page and block
provenance, but it does not currently emit the AviationRAG
`techdoc-structured-document / 0.1.0` root shape. The parser already has
dataclass models for `Document`, `Page`, `SourceLocation`, `BoundingBox`,
`TextBlock`, `HeadingBlock`, `ParagraphBlock`, `TableBlock`,
`TableRegionBlock`, `FigureBlock`, `FormulaBlock`, `Chunk`,
`ValidationIssue`, `ValidationReport`, `ValidationDecision`, and an output
manifest. Current machine-readable exports include `schema_version` plus
parser name/version metadata, but they do not include `schema_name`.

The strongest direct coverage is page extraction, native text blocks, bounding
boxes, source extraction method, source page numbers, raw and normalized text,
candidate headings, candidate paragraphs, candidate tables/table regions,
candidate figure captions, chunk source page/block/text-block references,
validation reports, gate decisions, and output-package manifest metadata.

Important information exists internally but is not exported in the target
shape: zero-based PDF page index can be derived from one-based page number,
page-local and document-global block order can be generated from `Page.blocks`,
block source spans can be mapped from `SourceLocation`, and section context
exists in chunk metadata but not as a durable section tree. Current chunking
can discard page-level detail into chunk-level lists; it preserves block IDs
and page numbers but not exact source-span objects.

Entire target areas remain absent or only placeholders: printed page label
extraction; source checksum; revision, issue, and effective-date metadata; true
table rows/columns/cells; figure assets or figure-region understanding;
equation detection; warning/caution/note classification; cross-reference
extraction and resolution; and real confidence models beyond
`SourceLocation.confidence`. The internal structured-document mapper now
populates `sections`, `tables`, and `figures` only from existing heading,
table-candidate, table-region, and figure-caption evidence.

The contract can start primarily as an additional exporter over the current
core model for a minimum valid record, provided the exporter is truthful about
missing data and does not fabricate metadata. Parser-core changes are required
for high-fidelity sections, admonitions, cross-references, table reconstruction,
figure regions, equations, page labels, source hashes, and confidence scoring.

Recommended sequence: add contract constants and exporter-only mapping first;
then page/block/source-span export; then section hierarchy; then specialized
entities from truthful evidence; then CLI/API optional integration; then
synthetic compatibility validation against the AviationRAG validator.

## 8.2 Current Parser Pipeline

Confirmed current pipeline:

```text
PDF input
  -> techdoc_parser.parser.parse_document()
  -> techdoc_parser.ingestion.PDFLoader.load()
  -> PyMuPDF page and native text block extraction
  -> Document / Page / TextBlock / SourceLocation / BoundingBox
  -> classify_text_block_page_furniture()
  -> extract_heading_blocks_from_text_block()
  -> create_paragraph_blocks_for_page()
  -> create_figure_blocks_for_page()
  -> create_table_blocks_for_page()
  -> create_table_region_blocks_for_page()
  -> get_semantic_blocks_for_page()
  -> create_semantic_chunks()
  -> validate_document_and_chunks_with_decision()
  -> document/chunk/validation/gate/manifest JSON and Markdown outputs
```

`PDFLoader.load()` enumerates PDF pages with `enumerate(pdf_document, start=1)`.
The model therefore stores one-based physical page numbers. PyMuPDF block
coordinates are captured as `BoundingBox`; `SourceLocation.extraction_method`
is `"pymupdf"` and `SourceLocation.confidence` is currently set to `1.0` for
native extracted blocks.

Inferred behavior: because `Page.blocks` is appended in extraction order and
semantic blocks are sorted by bounding-box `y0`, `x0`, and fallback index in
`block_sort_key()`, current reading order is deterministic and geometric for
single-page semantic output, but it is not a declared contract field and is not
validated as multi-column reading order.

```text
Current input
  -> PDFLoader / PyMuPDF
  -> Document, Page, TextBlock, derived candidate Block models
  -> semantic filtered view and Chunk models
  -> validation report and ingestion gate
  -> current JSON, chunk JSON, Markdown, validation, gate, manifest outputs
```

## 8.3 Target Integration Pipeline

The future integration boundary should be:

```text
Source document
  -> techdoc-parser
  -> techdoc-structured-document / 0.1.0 JSON
  -> AviationRAG structured-document validator
  -> AviationRAG ingestion adapter
  -> provenance-rich chunks
```

`techdoc-parser` should not import AviationRAG runtime code or depend on
AviationRAG packages. The integration should occur through a versioned JSON
contract with explicit `schema_name`, `schema_version`, `parser_name`, and
`parser_version`.

## 8.4 Field-By-Field Mapping Matrix

Mapping statuses used: `direct`, `rename`, `derive_safely`,
`available_but_not_exported`, `partial`, `missing`, `not_applicable`,
`must_not_infer`.

| Target entity | Target field | Current source | Current field | Mapping status | Required transformation | Information-loss risk | Recommended owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| root | schema_name | none | none | missing | Add exporter constant `techdoc-structured-document`. | Low if constant is versioned. | techdoc-parser exporter |
| root | schema_version | techdoc_parser.version | `SCHEMA_VERSION` | rename | Reuse current `0.1.0` under target root. | Low. | techdoc-parser exporter |
| root | parser_name | techdoc_parser.version | `PARSER_NAME` | rename | Emit root `parser_name`. | Low. | techdoc-parser exporter |
| root | parser_version | techdoc_parser.version | `PARSER_VERSION` | rename | Emit root `parser_version`. | Low. | techdoc-parser exporter |
| document | document_id | core.Document | `id` | rename | Map to `document.document_id`. | Medium if ID policy changes from path stem. | techdoc-parser exporter |
| document | filename | core.Document | `source_path` | derive_safely | Use basename only. | Low. | techdoc-parser exporter |
| document | canonical_title | core.DocumentMetadata | `title` | rename | Emit title if present, else null only if allowed by policy. | Medium if PDF metadata is poor. | techdoc-parser exporter |
| document | source_hash/source_checksum | none | none | missing | Add file checksum in a future controlled phase. | High if omitted before strict governance. | techdoc-parser parser/exporter |
| document | page_count | core.Document | `len(pages)` | derive_safely | Emit count. | Low. | techdoc-parser exporter |
| document | revision/issue/effective_date | none | none | missing | Do not derive from filename or timestamp. | High if inferred. | caller or future parser metadata |
| pages | page_id | core.Page | `page_number` | derive_safely | Deterministic `page-{page_number}` or zero-padded ID. | Low. | techdoc-parser exporter |
| pages | pdf_page_index | core.Page | `page_number` | derive_safely | `page_number - 1`. | Low if one-based invariant holds. | techdoc-parser exporter |
| pages | page_number | core.Page | `page_number` | direct | Emit as one-based page number. | Low. | techdoc-parser exporter |
| pages | printed_page_label | none | none | missing | New page-label detection needed; do not infer from page number. | Medium. | parser enhancement |
| pages | width/height | core.Page | `width`, `height` | available_but_not_exported | Include if target accepts extension fields. | Low. | techdoc-parser exporter |
| pages | rotation | none | none | missing | Capture from PyMuPDF page metadata. | Low. | parser enhancement |
| pages | requires_ocr/ocr_used | core.Page | `requires_ocr`, `has_native_text` | rename | Emit OCR state fields if allowed. | Low. | techdoc-parser exporter |
| pages | page_role | none | none | missing | Future classifier. | Medium. | parser enhancement |
| pages | ordered_block_refs | core.Page | `blocks` | derive_safely | Emit block IDs in page order. | Medium for multi-column order. | techdoc-parser exporter |
| sections | section_id | none durable | heading context only | partial | Build section tree from headings. | High. | model extension |
| sections | parent_section_id | chunking context | heading levels | partial | Requires durable hierarchy. | High. | model extension |
| sections | section_number | HeadingBlock | `text` | partial | Parse only explicit numbering; preserve unknown. | Medium. | parser/exporter |
| sections | title/raw_heading/path | HeadingBlock/Chunk.metadata | `text`, `section_path` | partial | Convert heading blocks to nodes; preserve raw text. | Medium. | model extension |
| blocks | block_id | core.Block | `id` | rename | Map to `block_id`. | Low. | techdoc-parser exporter |
| blocks | block_type/content_type | core.Block | `block_type` | rename | Map `heading` to `section_heading`; `table_region` policy needed. | Medium. | techdoc-parser exporter |
| blocks | text | core.Block | `text` | direct | Preserve raw text. | Low. | techdoc-parser exporter |
| blocks | normalized_text | core.Block | `normalized_text` | direct | Emit as optional extension. | Low. | techdoc-parser exporter |
| blocks | document_block_index | Page.blocks | list order | derive_safely | Stable traversal index. | Medium for reading-order accuracy. | techdoc-parser exporter |
| blocks | page_block_index | Page.blocks | list order | derive_safely | Stable index per page. | Low. | techdoc-parser exporter |
| blocks | section_id | none durable | chunk metadata only | partial | Requires section model. | High. | model extension |
| blocks | source_span | SourceLocation | page_number, bbox, extraction_method | rename | Build nested span; derive zero-based index. | Medium. | techdoc-parser exporter |
| blocks | char_start/char_end | none | none | missing | Capture offsets during extraction if needed. | Medium. | parser enhancement |
| tables | table_id | TableBlock/TableRegionBlock | `id` | implemented-contract-api | Phase 13E1 emits deterministic root table IDs distinct from block IDs. | Medium. | techdoc-parser contract mapper |
| tables | caption | TableBlock/TableRegionBlock | `caption` | partial-implemented | Phase 13E1 emits parser captions when present and preserves exact table text. | Medium. | techdoc-parser contract mapper |
| tables | columns/rows/cells | TableBlock/TableRegionBlock | `rows` list-of-single-lines | partial | Phase 13E1 leaves root columns/rows/cells empty; true reconstruction is missing. | High. | parser enhancement |
| figures | figure_id | FigureBlock | `id` | implemented-contract-api | Phase 13E1 emits deterministic root figure IDs distinct from block IDs. | Medium. | techdoc-parser contract mapper |
| figures | caption | FigureBlock | `caption` | partial-implemented | Phase 13E1 emits caption candidates only and preserves source caption text. | Medium. | techdoc-parser contract mapper |
| figures | asset reference | FigureBlock | `image_path` | partial | Field exists but loader does not extract images. | Medium. | parser enhancement |
| equations | equation_id | FormulaBlock/ParagraphBlock | `id`, `text` | implemented-contract-api | Phase 13E2 emits deterministic root equation IDs from conservative equation evidence. | Medium. | techdoc-parser contract mapper |
| equations | raw/normalized representation | FormulaBlock/ParagraphBlock | `text`, `latex` | partial-implemented | Phase 13E2 preserves raw source form and emits existing `latex` only when present. | Medium. | techdoc-parser contract mapper |
| admonitions | admonition_id/type/body | ParagraphBlock | `text` | implemented-contract-api | Phase 13E2 emits explicit-label warning/caution/note/important/safety-notice entities only. | High. | techdoc-parser contract mapper |
| cross_references | reference_id/raw_text/status/target | none | none | missing | Add reference extraction and optional resolution. | High. | parser enhancement |
| relationships | containment/cross-links | none | none | missing | Could derive simple contained_by only after sections/entities exist. | Medium. | exporter/model extension |
| confidence | confidence fields | SourceLocation | `confidence` | partial | Map real extraction confidence only; null for missing classifier scores. | High if fabricated. | techdoc-parser exporter |

## 8.5 Root Schema Identity

Current exports use `schema_version` and nested parser metadata from
`get_export_metadata()`. The target validator requires root `schema_name` and
`schema_version`, and warns when parser version is missing. The fixture emits
flat `parser_name` and `parser_version` fields.

Schema identity should belong to the contract exporter, not the internal core
model. The core model should remain a parser-native representation. Manifest
metadata should record the produced structured-document artifact and schema
identity once the exporter exists. Existing JSON outputs should keep their
current metadata for backward compatibility.

Recommendation: define contract-specific constants and serialization helpers in
Phase 13B. Reuse the parser version source from `techdoc_parser.version`, but
do not replace the current output package schema shape.

## 8.6 Document Metadata Mapping

Current extracted metadata comes from PyMuPDF metadata through
`PDFLoader._extract_metadata()`: title, author, subject, keywords, producer, and
creator. `Document.id` is generated from the source path stem. `Document.source_path`
is stored as provided to the loader.

Document number, revision, issue, effective date, source checksum, source media
type, and authoritative document-control metadata are not currently extracted.
Page count can be generated deterministically from `len(document.pages)`.
Parser name/version are known from `techdoc_parser.version`.

Recommended metadata policy:

- Extracted from source now: PDF metadata fields, page count, source filename/path.
- Supplied by caller later: authoritative document ID, document number, revision,
  issue, effective date, governance metadata, source checksum if managed by an
  upstream manifest.
- Generated deterministically: local parser block/page IDs and page count.
- Derived from filename: filename only, not revision or effective date.
- Currently unavailable: source checksum, media type, printed labels,
  document-control lifecycle fields.

File timestamps must not be treated as authoritative revision or effective-date
data.

Phase 13C status: `map_document_to_structured_document()` requires an explicit
caller-supplied `document_id`, maps `Document.source_path` to a basename-only
`source_filename`, maps `Document.metadata.title` to `canonical_title`, and
preserves caller-supplied `document_title`, `revision`, `issue`,
`effective_date`, and `source_checksum` only when provided. It does not derive
titles, revisions, dates, or checksums from filenames or file metadata.

## 8.7 Page Model Mapping

Current `Page` supports `page_number`, `width`, `height`, `has_native_text`,
`requires_ocr`, `blocks`, and `text_blocks`. It does not store
`pdf_page_index`, printed page label, rotation, blank-page state as a separate
field, OCR confidence, page confidence, page checksum, or ordered block
references. `requires_ocr` is true when no native text blocks were extracted,
which covers blank/no-text pages but does not distinguish intentionally blank
pages until validation.

Current page identity survives through `document.json` and through chunk
`source_page_numbers`, but chunk output drops page dimensions, OCR flags,
ordered block references, and bounding boxes. Numbering is one-based in the
parser; the target also needs zero-based `pdf_page_index`. That index can be
derived safely as `page_number - 1` while the current invariant holds.

Page labels are not supported. Page-level metadata is partly lost during
chunking because chunks retain page numbers but not page records, dimensions,
labels, OCR state, or per-page source spans.

Phase 13C status: pages are mapped to `StructuredDocumentPage` records in
`Document.pages` order. `page_number` remains one-based, `pdf_page_index` is
derived as `page_number - 1`, `page_id` is deterministic (`page-0001`), and
`printed_page_label` remains `null`.

## 8.8 Block And Reading-Order Mapping

Current block IDs are stable within a parse run by page number and local block
index, such as `page-1-text-1`, `page-1-paragraph-1`, and derived candidate IDs.
Blocks carry raw text, normalized text, block type, and `SourceLocation` with
page number, bounding box, extraction method, and confidence. Paragraph, table,
table-region, and figure blocks carry `source_text_block_ids`.

The target needs `block_id`, page reference, page-local index,
document-global index, raw text, normalized text, content type, bounding box,
character offsets, section reference, extraction method, and confidence.
Character offsets and section references are not currently present on blocks.

Reading order is currently inferred from PDF block order plus geometric sort in
`get_semantic_blocks_for_page()`. It is explicit only in generated chunk order,
not as a target field. Multi-column documents, sidebars, footnotes, headers,
footers, detached captions, and page-spanning content remain risks because no
dedicated reading-order or layout model exists.

Phase 13C status: blocks are flattened from `Page.blocks` in existing page and
block list order. Existing non-empty block IDs are preserved; empty block IDs
receive deterministic fallback IDs based on document ID, PDF page index, and
page-local block index. `page_block_index` and `document_block_index` are
exporter-derived order indexes. Raw text is preserved exactly, normalized text
is separate and optional, unknown block types map to `unknown`, and blocks
without non-empty raw text are rejected rather than repaired.

## 8.9 Section Hierarchy Mapping

Current heading detection creates `HeadingBlock` candidates with `level`, text,
normalized text, and source. Chunking maintains an in-memory heading context and
emits `section_title`, `section_path`, and `section_level` as chunk metadata.
There is no durable `Section` model, no `section_id`, no parent-child section
tree, no block membership list, and no explicit hierarchy confidence.

The current parser therefore has candidate heading blocks and chunk labels, not
a real section tree. Numbered clauses can be partially parsed from heading text
in a future exporter, but unnumbered headings need generated section IDs and
clear confidence/null semantics. A durable section model or contract-specific
section builder is needed before the target `sections` list can be complete.

## 8.10 Source-Span Mapping

Current source support:

- `SourceLocation.document_path`
- `SourceLocation.page_number`
- `SourceLocation.bbox`
- `SourceLocation.extraction_method`
- `SourceLocation.confidence`
- `Chunk.source_page_numbers`
- `Chunk.source_block_ids`
- `Chunk.source_text_block_ids`

The parser can trace current chunks back to source page numbers and block IDs,
and many block IDs can trace to source text block IDs. It cannot currently
trace every chunk to exact character offsets, printed labels, source checksum,
or multi-segment source spans. Bounding boxes exist on source blocks but are
not carried into chunk JSON.

Discarded or weakened provenance includes page dimensions/OCR state in chunks,
block bounding boxes in chunks, exact page-label provenance, and any confidence
distinction between extraction, structure, classification, OCR, and provenance.

Phase 13C status: each mapped block receives a single-page `StructuredSourceSpan`
from `SourceLocation.page_number` or the owning page number, the corresponding
zero-based PDF page index, the mapped bounding box when present, the mapped
block ID as a source block reference, and `extraction_method` when present.
Character offsets, source hashes, printed page labels, multi-page spans, and
confidence values are not fabricated.

## 8.11 Table Mapping

Current table support is partially structured and candidate-level. `TableBlock`
stores `caption`, `rows`, `source_text_block_ids`, and `is_candidate`.
`TableRegionBlock` groups nearby table-related fragments and stores source
text/table/paragraph block IDs. `create_table_blocks_for_page()` creates row
lists by wrapping each non-empty line as a one-cell row. `create_table_region_blocks_for_page()`
improves grouping for some simple cases but does not infer true columns, cells,
merged cells, table continuations, or semantic row/column identities.

Current Markdown and current output JSON render candidate table text, not
Markdown table syntax or target root table entities. The internal
structured-document mapper now creates root `tables` from `TableBlock` and
`TableRegionBlock` evidence only, with empty structural row/column/cell
collections. Do not claim semantic table accuracy without additional parser
capabilities, fixtures, and real validation evidence.

## 8.12 Figures And Captions

Current figure support is caption-level. `create_figure_blocks_for_page()`
detects obvious figure captions and creates `FigureBlock` candidates with
caption text, source location, source text block IDs, and `is_candidate`.
`FigureBlock.image_path` exists, but the loader does not extract image assets or
figure regions.

Figure understanding does not exist. The parser preserves caption/reference-like
text as candidate figures and uses figure-caption context to suppress some
table false positives inside diagrams. It does not identify machine-readable
visual content, figure type, region boundaries, or nearby explanatory blocks as
relationships. The internal structured-document mapper now creates root
`figures` from caption candidates only and omits `asset_reference` unless a
real parser `image_path` value exists.

## 8.13 Equations

`FormulaBlock` exists with `latex` and `variables`, but no current detector
creates formula/equation blocks in `PDFLoader`. The target can only be served
truthfully once detection exists or caller-supplied formula blocks exist.
Future equation export should preserve raw source representation and optional
normalized representation; equations should not be converted into prose when
the source form can be retained.

## 8.14 Warnings, Cautions, And Notes

The parser does not currently distinguish `WARNING`, `CAUTION`, `NOTE`,
`IMPORTANT`, `SAFETY_NOTICE`, or unknown admonitions as structured entities.
Those labels may survive as ordinary `TextBlock` or `ParagraphBlock` text, and
possibly as chunk text, but there is no admonition model, exact raw label field,
normalized admonition type, atomic block behavior, or root `admonitions` list.

Implementing the target contract requires classification logic, model/export
representation, tests and fixtures, and clear confidence/null handling. It is
not exporter-only unless the current parser treats admonitions as ordinary
blocks and maps them only as `unknown`, which would fail to preserve the
semantics requested by AviationRAG.

## 8.15 Cross-References

There is no `Reference` model or cross-reference extractor. References such as
"see Section", "refer to Table", or figure references are preserved only as
ordinary text when they appear in source blocks. The target requires
`reference_id`, raw reference text, resolution status, and optional target ID.
Resolution should not be fabricated. Initial support can emit no
`cross_references` or only `not_attempted` records when actual extraction logic
exists.

## 8.16 Confidence Model

The target validator allows confidence-like fields when numeric from 0.0 to
1.0 or null, and rejects booleans/out-of-range values. Current parser support
is limited to `SourceLocation.confidence`, currently set to `1.0` for native
PyMuPDF extraction. There is no dedicated model for OCR confidence, extraction
confidence, structure confidence, classification confidence, or provenance
confidence.

Real parser outputs:

- `SourceLocation.confidence`: present, but currently hard-coded to `1.0` for
  PyMuPDF native text blocks.
- OCR confidence: absent; OCR is not implemented.
- Structure confidence: absent; heading/table/figure candidates do not carry
  confidence.
- Classification confidence: absent.
- Provenance confidence: absent beyond source location presence.

Phase 13A recommendation: map only factual source-location confidence if the
project accepts its current semantics, and leave other confidence fields null or
absent. Do not fabricate confidence scores to satisfy downstream preference.

## 8.17 Validation Compatibility

Current `document.json` would not pass `structured_document_validator.py` as a
structured-document record. Expected failures include:

| Category | Current compatibility |
| --- | --- |
| Schema identity | Fails: no root `schema_name`; `schema_version` exists but is not paired with target name. |
| Document metadata | Fails/ warns: current root fields are `id` and `source_path`, not nested `document.document_id` and `filename`; source checksum missing warning. |
| Pages | Fails: current pages lack required `pdf_page_index`; page numbers are valid one-based values. |
| Blocks | Fails if current nested page blocks are not flattened to root `blocks`; current key is `id`, not `block_id`; `heading` is not an allowed target type. |
| Sections | Current absence is allowed as an empty optional list, but blocks with section IDs would need known sections. |
| Source spans | Current `source` object is not target `source_span`; can be mapped. |
| Tables | Phase 13E1 root table entities carry deterministic `table_id`, known page refs, and source block refs; true root table rows/cells are intentionally empty. |
| Figures | Phase 13E1 root figure entities carry deterministic `figure_id`, known page refs, source block refs, and caption text only. |
| Equations | Empty list can pass; emitted equation records would need raw representation. |
| Admonitions | Empty list can pass; emitted records need allowed type and body text. |
| Cross-references | Empty list can pass; emitted records need ID, raw text, status, and valid target policy. |
| Confidence | Current `1.0` values are in range; missing specialized confidence fields should remain null/absent. |

The validator is a coherence validator, not an extraction-accuracy validator.
Passing it would not prove heading, table, page-label, or admonition accuracy.

## 8.18 Existing Output Compatibility

The new structured-document output should be an additional optional output, not
a replacement for current JSON, Markdown, chunk JSON, manifest, validation
report, validation summary, gate decision, CLI behavior, or Python API.

Recommended future integration:

- Add exporter API first.
- Add CLI flag later only after exporter tests and compatibility validation.
- Add manifest entry only when the structured output is requested.
- Keep current `--output` document JSON shape unchanged.
- Keep validation report and ingestion-gate behavior report-only.

Backward compatibility should be preserved unless a later phase documents and
versions a breaking contract change.

## 8.19 Retention Decision

Structured parser output should be retained as a durable artifact for controlled
ingestion workflows, not treated only as a temporary intermediate.

Rationale:

- Auditability: the structured record explains what the parser observed before
  AviationRAG chunking.
- Reproducibility: downstream chunks can be regenerated from the same artifact
  without reparsing the source file.
- Migration traceability: validator reports can be tied to a specific parser
  output and source hash.
- Parser upgrades: old and new structured outputs can be diffed.
- Debugging: chunk or citation errors can be traced back to parser blocks.
- Controlled-document governance: durable artifacts help prevent AviationRAG
  from silently inventing parser provenance.

Storage cost is acceptable for JSON records compared with source PDFs and
embeddings. Retention behavior should not be implemented in Phase 13A.

## 8.20 Ownership Boundaries

`techdoc-parser` should own:

- Source extraction from supported formats.
- Pages, block observations, source locations, bounding boxes, and reading order.
- Observed headings and future section tree construction.
- Paragraph, table, figure-caption, equation, admonition, and cross-reference
  extraction when implemented.
- Raw and normalized text preservation.
- Extraction method and truthful confidence/provenance fields.
- Parser and structured-document schema identity.
- Optional structured-document export.

AviationRAG should own:

- Contract acceptance policy and validator execution.
- Manifest ingestion status and downstream validation policy.
- Chunk construction, chunk IDs, embedding preparation, vector metadata limits,
  retrieval ranking, citations, answer policy, and runtime ingestion adapters.
- Warning acceptance policy and reset/rebuild gates.

AviationRAG must not silently invent parser provenance. Missing parser evidence
must remain null, empty, unknown, or explicitly not attempted where the target
contract permits it.

## 8.21 Gap Classification

| Gap | Class | Priority | Risk | Backward-compat risk | Recommended phase |
| --- | --- | --- | --- | --- | --- |
| Root `schema_name` and flat parser identity | export-only | P0 | low | low | 13B |
| Optional contract exporter API | export-only | P0 | low | low | 13B |
| Current document/page/block flattening | export-only | P0 | medium | low | 13C |
| Source-span object mapping | export-only | P0 | medium | low | 13C |
| Deterministic page/block indexes | export-only | P0 | medium | low | 13C |
| Source checksum | model-extension | P0 | medium | low | 13B/13C policy |
| Durable section tree | model-extension | P1 | high | medium | 13D |
| Heading number/title parsing | parser-enhancement | P1 | medium | low | 13D |
| Exact block membership in sections | model-extension | P1 | high | medium | 13D |
| Candidate table root mapping | contract mapper | P1 | medium | low | 13E1 completed |
| True table cells/merged cells | parser-enhancement | P2 | high | low | post-13E |
| Figure caption root mapping | contract mapper | P1 | medium | low | 13E1 completed |
| Figure asset/region extraction | parser-enhancement | P3 | high | low | later |
| Equation detection | parser-enhancement | P2 | high | low | 13E/later |
| Warning/caution/note classification | parser-enhancement | P1 | high | low | 13E |
| Cross-reference extraction | parser-enhancement | P2 | high | low | 13F |
| Confidence model | model-extension | P1 | medium | low | 13F |
| Validator fixture alignment | fixture/test requirement | P0 | low | low | 13H |
| CLI optional output flag | export-only | P1 | medium | medium | 13G |
| Retention policy | policy decision | P1 | medium | low | 13G/13H |
| Real-document accuracy pilot | fixture/test requirement | P2 | high | low | 13I |
| Embeddings/Astra/FAISS | out of scope | P3 | high | high | AviationRAG later |

## 8.22 Proposed Implementation Phases

### 13B - StructuredDocument Contract Foundation

Goal: add contract constants and serialization scaffolding only.
Likely files: `src/techdoc_parser/version.py` or new exporter-local constants,
new exporter module, focused tests. Constraints: no CLI integration, no parser
behavior changes, no AviationRAG import. Acceptance: synthetic in-memory export
has root identity and deterministic JSON.

### 13C - Document, Page, Block, And Source-Span Mapping

Goal: map current `Document`, `Page`, and `Block` data into the target root
shape truthfully. Likely files: structured exporter and tests. Constraints:
current JSON unchanged; no page-label or checksum fabrication. Acceptance:
minimal native-text synthetic document validates except for accepted warnings.

### 13D - Section Hierarchy And Source-Span Enrichment

Goal: create durable section records from heading candidates or a contract-local
section builder. Likely files: structure or exporter helper plus tests.
Constraints: preserve `HeadingBlock`; do not overclaim hierarchy. Acceptance:
numbered/unnumbered synthetic heading cases produce stable `sections` and block
section references.

Phase 13D status: completed as a contract-local hierarchy builder. It derives
section IDs, parent-child links, paths, block `section_id` values, and section
source spans from existing `HeadingBlock` evidence only. It does not change
heading detection, chunking, current outputs, CLI behavior, or AviationRAG.

### 13E - Tables, Figures, Equations, And Admonitions

Goal: export candidate tables/figures truthfully and add initial admonition or
equation support only if parser evidence exists. Likely files: structure/model
extensions and tests. Constraints: no semantic table accuracy claims; no prose
conversion of equations. Acceptance: target entity records validate with nulls
or candidate status where permitted.

Phase 13E1 status: completed for table and figure-caption mapping only. The
contract mapper now emits root `tables` and `figures` from existing
`TableBlock`, `TableRegionBlock`, and `FigureBlock` evidence. It leaves table
rows/columns/cells empty, emits no figure assets unless a real `image_path`
exists, and does not implement equation, admonition, or cross-reference entity
mapping.

Phase 13E2 status: completed for conservative equation and explicit-label
admonition mapping only. The contract mapper now emits root `equations` from
existing `FormulaBlock` evidence and narrow paragraph equation evidence, and
root `admonitions` from explicit labels such as `WARNING`, `CAUTION`, `NOTE`,
`IMPORTANT`, and `SAFETY NOTICE`. It does not implement formula discovery from
PDF layout, mathematical semantics, safety severity inference, typography-only
admonition detection, confidence fields, or cross-reference mapping.

### 13F - Cross-References And Confidence Mapping

Goal: add explicit reference extraction/status policy and confidence mapping.
Likely files: new structure helpers or exporter policy module plus tests.
Constraints: unresolved/not-attempted references must stay explicit; no false
resolution. Acceptance: cross-reference records validate and confidence fields
are numeric or null.

### 13G - Optional CLI/API Structured-Document Output

Goal: expose the exporter as optional output. Likely files: CLI, exporters,
README. Constraints: no replacement of current `--output`; manifest entry only
when output exists. Acceptance: CLI regression proves existing flags unchanged.

### 13H - Synthetic Compatibility Validation Against AviationRAG

Goal: validate parser-generated synthetic structured-document output against a
local copy or documented fixture-compatible expectations. Constraints: do not
import AviationRAG as runtime dependency; do not modify AviationRAG. Acceptance:
synthetic validation command or equivalent test passes in a controlled way.

### 13I - Controlled Approved-Document Accuracy Pilot

Goal: manually review accuracy on approved non-proprietary or explicitly
authorized source documents. Constraints: no full corpus parsing; no embeddings;
no Astra/FAISS work. Acceptance: documented extraction findings and go/no-go
for downstream AviationRAG ingestion.

## 8.23 Minimum Viable Contract

Required for first valid export:

- Root `schema_name`, `schema_version`, `parser_name`, `parser_version`.
- `document.document_id`, `document.filename`, `document.page_count`.
- `pages[]` with `page_id`, `pdf_page_index`, `page_number`, optional/null
  `printed_page_label`.
- Flattened `blocks[]` with `block_id`, target-compatible `block_type`, text
  when textual, `document_block_index`, `page_block_index`, and `source_span`.
- Empty `sections` where no truthful heading evidence is emitted or section
  enrichment is disabled.
- Empty `tables` and `figures` where no truthful candidate records are emitted;
  otherwise Phase 13E1 may populate them from current candidate evidence.
- Empty `equations` and `admonitions` where no truthful candidate records are
  emitted; otherwise Phase 13E2 may populate them from conservative or explicit
  evidence.
- Empty `cross_references` until truthful records exist.

Required before AviationRAG D.4c:

- Source checksum or manifest-provided source hash.
- Stable section records for heading-derived chunk provenance.
- Block-to-section references where confidence is acceptable.
- Explicit provenance status and missing-metadata policy.
- Validator compatibility evidence.

Optional parser-enhanced fields:

- Page labels, page roles, rotation, page confidence.
- Table root records and cell structures.
- Figure regions/assets.
- Equation raw/normalized records.
- Admonition and cross-reference records.
- Specialized confidence fields.

Deferred advanced fields:

- OCR confidence and OCR text.
- Multi-column reading-order confidence.
- Merged table cells, table footnotes, and table continuations.
- Resolved cross-reference graph.
- Controlled-document revision/effective-date extraction.

The minimum contract must remain truthful. Use nulls, empty lists, or explicit
unknown/not-attempted status only where the target validator and policy permit.

## 8.24 Risks

- Schema drift between design docs, fixture, and validator.
- Duplicate internal and export models diverging.
- Loss of page provenance during chunking.
- Unstable IDs if IDs depend on incidental extraction order.
- Inaccurate heading hierarchy from heuristic candidates.
- Table flattening mistaken for structured table extraction.
- False confidence values, especially current hard-coded `1.0`.
- Destructive changes to existing JSON output or CLI behavior.
- Coupling `techdoc-parser` to AviationRAG internals.
- Confusion between parser version and contract schema version.
- Test-fixture overfitting to synthetic records.
- Treating structural validity as extraction accuracy.

## 8.25 Recommended Next Phase

Phase 13B status: **completed as an isolated contract foundation**.

Phase 13C status: **completed as a pure parser-model mapper**.

Phase 13D status: **completed as pure section hierarchy and source-span
enrichment**.

Phase 13E1 status: **completed for table and figure-caption mapping from
existing candidate evidence only**.

Phase 13E2 status: **completed for conservative equation and explicit-label
admonition mapping from truthful parser evidence only**.

Phase 13C maps current `Document`, `Page`, `Block`, `SourceLocation`, and
`BoundingBox` evidence into the Phase 13B contract model while preserving all
existing output formats. It added `structured_document_mapper.py`, focused
mapper tests, a deterministic mapped fixture, and mapping documentation. It did
not add CLI integration, manifest integration, real-document processing,
AviationRAG imports, AviationRAG modifications, embeddings, Astra, FAISS,
section hierarchy, advanced entity root records, confidence mapping, or changes
to parser extraction, chunking, validation, current JSON, Markdown, or manifest
behavior.

Phase 13D adds durable section records, section IDs, parent-child relationships,
block-to-section membership, and enriched section source spans without replacing
current parser models or changing current output behavior.

Phase 13E1 adds root `tables` and `figures` from current `TableBlock`,
`TableRegionBlock`, and `FigureBlock` evidence without claiming table
reconstruction, figure assets, figure-region understanding, or changes to
current output behavior.

Phase 13E2 adds root `equations` and `admonitions` from conservative equation
evidence and explicit admonition labels without claiming mathematical
understanding, safety severity inference, confidence fields, or changes to
current output behavior.

Recommended next phase: **Phase 13F - Cross-Reference/Confidence Policy**,
**Phase 13G - Optional CLI/API Structured-Document Output**, or formula
discovery/table-structure parser enhancement, depending on which downstream
contract gap matters first.
