# techdoc-parser Architecture and Pipeline Overview

## 1. Purpose

This document describes the current MVP architecture, processing stages, major
modules, output artifacts, and known limitations for `techdoc-parser`. It is a
maintenance and integration overview, not a full design specification.

## 2. Architecture Summary

```text
PDF input
  ↓
PDFLoader / PyMuPDF ingestion
  ↓
Document / Page / TextBlock model
  ↓
Page furniture detection
  ↓
Candidate semantic structures
- HeadingBlock
- ParagraphBlock
- TableBlock
- TableRegionBlock
- FigureBlock
- FormulaBlock placeholder
  ↓
Semantic block view
  ↓
Semantic chunking
  ↓
Validation report
  ↓
Ingestion gate decision
  ↓
Output package and manifest
```

Optional structured-document output follows this additive path:

```text
Source document
        ↓
Current parser pipeline
        ↓
StructuredDocument mapper
        ↓
StructuredDocument file exporter
        ↓
optional manifest registration
        ↓
external contract consumer
```

## 3. Main Packages and Responsibilities

| Package / Module | Responsibility |
| --- | --- |
| `techdoc_parser.core` | Dataclass models for documents, pages, blocks, source locations, bounding boxes, metadata, and chunks. |
| `techdoc_parser.loaders` | Conceptual loader layer; currently implemented by `techdoc_parser.ingestion`. |
| `techdoc_parser.ingestion` | PDF ingestion through `PDFLoader` and PyMuPDF. |
| `techdoc_parser.structure` | Heuristic structure detection for page furniture, headings, paragraphs, tables, table regions, figures, conservative equation evidence, explicit-label admonitions, explicit textual cross-references, and semantic block views. |
| `techdoc_parser.normalization` | Text normalization helpers that preserve raw text while storing normalized text separately. |
| `techdoc_parser.chunking` | Semantic chunk creation, chunk text cleanup, source reference preservation, and section metadata assignment. |
| `techdoc_parser.validation` | Quality report generation and ingestion gate decision mapping. |
| `techdoc_parser.exporters` | JSON, Markdown, validation, gate, chunk, manifest, semantic Markdown, and optional structured-document export helpers. |
| `techdoc_parser.contracts` | Isolated versioned contract models, parser-model mapper, table/figure-caption entity mapper, equation/admonition entity mapper, cross-reference mapper, confidence policy helpers, and deterministic serializers for future external structured-document artifacts. |
| `techdoc_parser.cli` | `techdoc-parse` command-line interface for producing parser output packages. |
| `techdoc_parser.version` | Export contract metadata including schema version, parser name, and parser version. |

## 4. Processing Stages

1. PDF ingestion: `PDFLoader` opens native-text PDFs with PyMuPDF and creates the initial `Document`.
2. Raw text block extraction: page text blocks, source locations, bounding boxes, and metadata are captured.
3. Page furniture classification: headers, footers, page numbers, document identifiers, and intentionally blank content are flagged conservatively.
4. Heading detection: candidate `HeadingBlock` objects are derived from likely heading text while filtering common false positives.
5. Paragraph grouping: meaningful text blocks are represented as `ParagraphBlock` objects for semantic output.
6. Table candidate detection: table-like text is marked as candidate `TableBlock` content without claiming full table reconstruction.
7. Figure caption detection: obvious figure captions are represented as candidate `FigureBlock` objects.
8. Table region grouping: nearby table fragments may be grouped into candidate `TableRegionBlock` objects.
9. Structured-document entity mapping: the internal contract API can map existing table/figure evidence, conservative equation evidence, explicit-label admonitions, explicit textual cross-references, and confidence policy without changing parser outputs.
10. Semantic block filtering: raw text blocks and duplicate derived blocks are filtered from semantic views without modifying the source model.
11. Semantic chunk creation: semantic blocks are aggregated into RAG-oriented chunks with source references.
12. Chunk cleanup and section metadata: emitted chunk text is cleaned of furniture lines, and available heading context is stored as section metadata.
13. Validation report: document and chunk quality findings are reported with info, warning, and error severity.
14. Ingestion gate decision: validation findings are mapped to `pass`, `review`, or `fail`.
15. Output package generation: document, chunk, validation, gate, Markdown summary, semantic Markdown, optional structured-document, and manifest artifacts can be exported.

## 5. Data Flow and Preservation Principle

The parser preserves raw extracted data and adds derived structure alongside it.
Raw `TextBlock` objects remain available in `page.text_blocks` and `page.blocks`.
Derived structures such as headings, paragraphs, tables, table regions, and
figures are added to `page.blocks`.

Semantic exports use filtered views to suppress raw text or duplicate derived
blocks where a cleaner downstream representation is useful. These filters do not
delete raw extraction data. Chunk cleanup affects emitted chunk text only; it
does not mutate the original `Document`, `Page`, or `Block` objects. Validation
reports findings and gate decisions but does not modify parser output.

## 6. Output Artifacts

| Artifact | Summary |
| --- | --- |
| `document.json` | Full structured parser output with pages, raw text blocks, derived blocks, metadata, and source references. |
| `chunks.json` | RAG-oriented semantic chunks with source page, block, text-block, and section metadata. |
| `validation.json` | Machine-readable validation report with issue counts, summary metrics, and issue details. |
| `gate.json` | Combined validation decision and report for ingestion planning. |
| `validation_summary.md` | Human-readable validation and gate summary for review workflows. |
| `manifest.json` | Package manifest that records source document, output paths, schema/parser metadata, gate decision, and basic metrics. |
| Semantic Markdown output | Human-readable semantic view that omits raw text-block duplicates where possible. |
| StructuredDocument output | Optional `techdoc-structured-document / 0.1.0` JSON artifact with exact source-byte SHA-256 and deterministic bytes. |

Machine-readable JSON outputs include `schema_version` and parser metadata with
parser name and parser version.

## 7. Validation and Gate Philosophy

Validation reports quality findings; it is not a mutation or repair step.
Findings use three severities:

- `info`: informational finding; info-only reports do not block ingestion.
- `warning`: human review is recommended before ingestion.
- `error`: automated ingestion should fail.

The ingestion gate maps reports to:

- `pass`: no blocking validation findings are present.
- `review`: warnings are present and should be reviewed.
- `fail`: errors are present and should not be ingested automatically.

The CLI does not currently change its process exit code based on validation
results. Validation status is emitted in the validation and gate artifacts.

## 8. Current MVP Scope

- Native-text PDFs are supported.
- Scanned/OCR documents are detected, but OCR is not performed.
- Table extraction is candidate-level and partial.
- Figure support is caption-level.
- Formula discovery from PDF layout is not implemented; the internal structured-document mapper can expose existing `FormulaBlock` records and conservative paragraph equation evidence.
- Admonition mapping is explicit-label only in the internal structured-document mapper; safety severity inference is not implemented.
- Cross-reference mapping is explicit-text only in the internal
  structured-document mapper; unresolved, external, ambiguous, and
  not-attempted statuses are preserved rather than repaired.
- Section-aware chunk metadata exists in current chunk outputs. A heading-derived
  section tree exists only in the internal structured-document contract API; it
  is not emitted by the current CLI output package.
- Confidence scoring is not implemented as a dedicated model. The internal
  structured-document mapper omits current placeholder confidence values.

## 9. AviationRAG Integration Position

AviationRAG integration should start from `manifest.json`. The manifest provides
the source document identity, generated artifact paths, parser/schema metadata,
gate decision, and basic metrics in one place.

An integration should check `schema_version` and parser metadata before reading
other artifacts. It should check the gate decision and ingest `chunks.json` only
when the decision allows the intended workflow. `document.json` remains
available for traceability and debugging, and `validation_summary.md` remains
available for human review.

### Structured-Document Contract Boundary

Future AviationRAG integration may use the dedicated structured-document export.
The current implementation is an internal contract layer, pure parser-model
mapper, and optional file exporter:

```text
Current parser models
        ↓
Document/page/block mapping
        ↓
Section hierarchy
        ↓
Table and figure-caption evidence
        ↓
Equation and admonition evidence
        ↓
Cross-references and confidence policy
        ↓
StructuredDocument serializer
        ↓
StructuredDocument file exporter
        ↓
optional manifest registration
```

The contract foundation and mapper are implemented under
`techdoc_parser.contracts`; file export is implemented under
`techdoc_parser.exporters`. The mapper covers document, page, block,
source-span, bounding-box, heading-derived section hierarchy data, current
table/figure candidate evidence, conservative equation evidence, explicit-label
admonition evidence, explicit textual cross-references, and confidence omission
policy.

Structured-document output is optional and current default outputs remain
unchanged. Manifest registration is additive and occurs only when both
structured-document output and manifest output are requested. Runtime ingestion,
true table reconstruction, figure asset extraction, and formal cross-project
compatibility validation are not implemented. AviationRAG is one intended
consumer, but the parser remains independent and has no direct runtime
dependency on AviationRAG.

## 10. Recommended Near-Term Next Steps

- Use `docs/legacy_repository_structure_audit.md` as the current repository
  cleanup-readiness reference. Cleanup remains useful but non-blocking.
- Add optional validation profiles or strictness modes.
- Add an architecture diagram later if the pipeline grows more complex.
- Phase 13H: formalize synthetic compatibility validation against AviationRAG.
- Add a dedicated confidence scoring model only when truthful evidence exists.
- Add an advanced table extraction adapter for more reliable table structure.
