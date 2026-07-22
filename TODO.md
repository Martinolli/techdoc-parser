# TODO.md — Technical Document Parsing Library

## Project Working Name

**techdoc-parser**  
A Python library for parsing complex technical documents into structured, traceable, RAG-ready representations.

---

## 0. Project Initialization

- [x] Choose final project name
  - Candidate names:
    - `techdoc-parser`
    - `ragdoc-parser`
    - `aerodoc-parser`
    - `traceparse`
    - `technical-document-parser`
- [x] Create GitHub repository
- [x] Choose license
  - Recommended initial choice: MIT or Apache-2.0
- [x] Create local Python project structure
- [x] Configure virtual environment
- [x] Create `pyproject.toml`
- [x] Create initial `README.md`
- [x] Add `.gitignore`
- [x] Add `TODO.md`
- [x] Add `PROJECTPLAN.md`
- [x] Create first package skeleton
- [x] Create public placeholder function `parse_document`
- [x] Create initial tests
- [x] Make first commit

Phase 0 package foundation completed. Tests, ruff, and mypy passed.

---

## 1. High-Level Requirements

- [x] Define mission statement
- [x] Define target users
- [x] Define target document types
- [x] Define input formats for MVP
- [x] Define output formats for MVP
- [x] Define non-goals for MVP
- [x] Define traceability requirements
- [x] Define verification requirements
- [x] Define quality attributes
  - [x] Accuracy
  - [x] Traceability
  - [x] Extensibility
  - [x] Testability
  - [x] Reproducibility
  - [x] Performance

High-level requirements are defined in PROJECTPLAN.md section 5 as HLR-001 through HLR-012.

---

## 2. System Architecture

- [ ] Define system boundary
- [ ] Define external dependencies
- [ ] Define major capability domains
- [ ] Define package/module structure
- [ ] Define internal document model
- [ ] Define processing pipeline
- [ ] Define adapter strategy for external parsers
- [ ] Define confidence scoring approach
- [ ] Define validation strategy
- [ ] Define export strategy

---

## 3. Core Data Model

- [x] Define `Document` model
- [x] Define `Page` model
- [x] Define `Block` model
- [x] Add generic `Page.blocks` collection
- [x] Define `TextBlock` model
- [x] Define `HeadingBlock` model
- [x] Define `TableBlock` model
- [x] Define `FormulaBlock` model
- [x] Define `FigureBlock` model
- [ ] Define `Reference` model
- [x] Define `SourceLocation` model
- [x] Define `BoundingBox` model
- [x] Define `ParagraphBlock` model
- [ ] Define `ConfidenceScore` model
- [x] Define JSON serialization format
- [x] Define Markdown export format

Initial dataclass models implemented for `Document`, `Page`, `TextBlock`, `DocumentMetadata`, `SourceLocation`, and `BoundingBox`. JSON serialization is available through `to_dict()` and `Document.to_json()`.

Phase 1B structured block models completed with unit tests. `Page` now supports generic `Block` objects through `blocks` while preserving `text_blocks` for backward compatibility. Tests, ruff, and mypy pass.

---

## 4. MVP Scope

The first MVP shall focus on:

```text
PDF → structured document model → JSON export → Markdown export → RAG-ready chunks
```

- [x] Support PDF input
- [x] Extract document metadata
- [x] Extract page-level structure
- [x] Extract text blocks
- [x] Preserve page numbers
- [x] Preserve bounding boxes where available
- [ ] Detect headings using heuristic methods
- [x] Detect paragraphs
- [x] Detect basic tables
- [x] Add candidate-level grouping for fragmented table regions
- [ ] Preserve table row/column structure where possible
- [ ] Detect potential formula blocks
- [x] Export structured JSON
- [x] Export readable Markdown
- [x] Create simple RAG chunks with source references

Phase 4B basic heading detection completed. Added the structure package, conservative heading heuristics, `is_heading_text()`, `detect_heading_level()`, and `create_heading_block_from_text_block()`. `PDFLoader` now adds obvious `HeadingBlock` objects to `page.blocks` while preserving original `TextBlock` objects in both `page.text_blocks` and `page.blocks`. Tests, ruff, and mypy pass.

Phase 4C line-level heading extraction completed. Added `extract_heading_blocks_from_text_block()`, MIL-STD-style task and appendix heading patterns, embedded multiline `TextBlock` heading extraction, duplicate suppression, and false-positive tests. `PDFLoader` now appends all detected `HeadingBlock` objects while preserving original `TextBlock` objects unchanged. Tests, ruff, and mypy pass.

Phase 4C is a first-pass candidate heading detector, not final semantic heading classification. Real-document validation showed that content capture is good, but semantic heading classification still needs refinement before it should be used for final RAG chunk hierarchy.

Phase 4D — Context-aware heading filtering:

- [x] Reject numbered body paragraphs incorrectly detected as headings
- [x] Reject table-of-contents entries with dot leaders and page numbers
- [x] Reject heading candidates from Contents pages, except the "Contents" heading itself
- [x] Reject sentence-like Appendix references
- [x] Improve MIL-STD-882E heading precision
- [x] Improve AC-120-92 heading precision
- [x] Preserve detected true headings such as 1. SCOPE, 2. APPLICABLE DOCUMENTS, TASK 101, and APPENDIX A actual section headings
- [x] Add regression tests based on observed MIL-STD-882E and AC-120-92 false positives

Phase 4D context-aware heading filtering completed with regression tests for observed MIL-STD-882E and AC-120-92 false positives. Heading detection remains heuristic and should still be treated as candidate semantic structure until validated against more real documents. Tests, ruff, and mypy pass.

Phase 4E page-furniture detection completed. Added `TextBlock` flags for page headers, footers, page numbers, and page furniture; added conservative page-furniture classification; prevented page furniture from creating `HeadingBlock` objects; preserved original `TextBlock` objects; and updated Markdown export to show page-furniture status when applicable. Page furniture detection is conservative and should be validated against real documents such as MIL-STD-882E, AC-120-92, and FTIAS Manual. Tests, ruff, and mypy pass.

Phase 5A paragraph grouping completed. Added `ParagraphBlock`, `create_paragraph_blocks_for_page()`, JSON output for paragraph blocks in `page.blocks`, and tests for paragraph grouping. `PDFLoader` now creates `ParagraphBlock` objects for meaningful body text while preserving original `TextBlock` objects unchanged; page furniture and heading text blocks do not create duplicate paragraphs. Phase 5A creates one `ParagraphBlock` per meaningful `TextBlock`; cross-block paragraph merging remains future work. Tests, ruff, and mypy pass.

Phase 5B full pipeline integration testing completed. Added a generated-PDF integration test that verifies the `PDFLoader` pipeline creates `TextBlock`, `HeadingBlock`, and `ParagraphBlock` objects; validates page-furniture behavior; confirms furniture and heading text do not create duplicate semantic blocks; and checks JSON export for text, heading, paragraph, page-furniture flags, and paragraph `source_text_block_ids`. Stable JSON sanity assertions are inline in tests; no generated golden output files are committed. Tests, ruff, and mypy pass.

Phase 6A basic table candidate detection completed. Added table detection helpers, `is_table_candidate_text()`, `create_table_blocks_for_page()`, and `TableBlock` candidate metadata including `source_text_block_ids` and `is_candidate`. `PDFLoader` now creates `TableBlock` candidates for likely table text blocks while preserving original `TextBlock` objects; table candidates appear in `page.blocks` but not `page.text_blocks`, and JSON output includes candidate metadata. Phase 6A only detects table candidates; it does not reconstruct rows and columns or perform advanced table extraction yet. Tests, ruff, and mypy pass.

Phase 6B table candidate false-positive reduction completed. Improved table candidate filtering with long prose paragraph rejection plus lettered and numbered list rejection, reduced false positives from MIL-STD foreword prose and page 3 list/change-summary content, preserved true MIL-STD table detections from page 19, and added regression tests for page 2/page 3 false positives plus true table captions, headers, and rows. Table detection remains candidate-level only; Phase 6B does not reconstruct table columns, merge table regions, or create final table structures. Tests, ruff, and mypy pass.

Phase 6C table candidate precision refinement completed. Added conservative rejection for definition entries, table-reference paragraphs, and figure captions/references while preserving true MIL-STD table detections from page 19 and hidden table/list-table candidates such as acronyms and document modification structures. Added regression tests for definition entries, table-reference paragraphs, figure captions/references, and true table captions, headers, and rows. Table detection remains candidate-level only; Phase 6C does not reconstruct table columns, merge table regions, or create final table structures. Tests, ruff, and mypy pass.

Phase 6D diagram/template-label table filtering completed. Added conservative rejection for process-diagram labels, form/template label groups, and section prose where table-like words appear inside normal sentences, while preserving true MIL-STD table detections from page 19. Added regression tests for diagram-label, template-label, and section-prose false positives plus true table captions, headers, and rows. Table detection remains candidate-level only; Phase 6D does not reconstruct table columns, merge table regions, or create final table structures. Known limitation: figure/diagram-internal text, such as labels inside MIL-STD-882E FIGURE B-1 on page 103, may still be detected as `TableBlock` candidates until FigureBlock / diagram-region detection is implemented. Tests, ruff, and mypy pass.

Phase 9A/9B/9C table region grouping partially completed. Added `TableRegionBlock` and `create_table_region_blocks_for_page()` to produce conservative grouped table-region candidates after low-level `TableBlock` detection. Semantic block filtering prefers `TableRegionBlock` over duplicate lower-level blocks where possible, semantic Markdown renders grouped regions as "Table region candidate", and low-level `TextBlock`, `ParagraphBlock`, and `TableBlock` objects remain preserved unchanged. Real-document testing shows useful results for some simple/regular tables, and MIL-STD-882E page 20 TABLE III is much better grouped as one table-region candidate. However, generic table reconstruction is not solved: MIL-STD-882E page 19 TABLE I and TABLE II may still split into multiple regions/candidates; some rows may remain as low-level `TableBlock` or `ParagraphBlock` objects; and complex, nested, irregular, multi-column, or visually separated-cell tables are not reliably reconstructed. Phase 9 remains heuristic and candidate-level only; it does not infer true rows/columns, generate Markdown table syntax, or perform advanced table extraction. Added table region grouping, semantic filtering, and semantic Markdown regression tests. Tests, ruff, and mypy pass.

---

## 5. Ingestion Layer

- [x] Create `PDFLoader` interface
- [x] Implement initial PyMuPDF-based loader
- [x] Extract pages
- [x] Extract native text blocks
- [x] Extract bounding boxes
- [x] Extract metadata
- [x] Detect native PDF text versus scanned page
- [x] Add basic error handling
- [x] Add logging

Phase 2A basic PDF ingestion completed. PyMuPDF is now a runtime dependency, `PDFLoader` loads native-text PDFs into `Document`, `parse_document()` supports PDF input, and generated-PDF ingestion tests pass with pytest, ruff, and mypy.

Phase 2D native-text page detection completed. `Page` now includes `has_native_text` and `requires_ocr`, `PDFLoader` flags blank/no-text pages as requiring OCR, JSON output includes the flags, and standard library logging is used for load status and OCR warnings. Tests, ruff, and mypy pass.

---

## 6. Layout Analysis Layer

- [ ] Implement page layout object
- [ ] Detect text blocks
- [ ] Detect reading order
- [x] Detect headers and footers
- [x] Detect page numbers
- [ ] Detect multi-column layout
- [ ] Detect captions
- [ ] Detect footnotes
- [ ] Add layout confidence score

---

## 7. Content Extraction Layer

- [ ] Implement text block extraction
- [ ] Implement heading detection
- [x] Implement paragraph grouping
- [x] Implement table detection
- [ ] Implement simple table extraction
- [ ] Implement formula candidate detection
- [ ] Implement figure/image candidate detection
  - [ ] Detect figure captions and figure regions
  - [ ] Use figure-region detection to suppress table candidates inside diagrams
- [ ] Attach source location to every extracted object

Phase 7A figure caption candidate detection completed. Added the figure detection structure module, `is_figure_caption_text()`, and `create_figure_blocks_for_page()`. `PDFLoader` now creates `FigureBlock` candidates for obvious figure captions, preserves original `TextBlock` objects unchanged, adds figures to `page.blocks` but not `page.text_blocks`, and preserves source references plus `source_text_block_ids`; JSON output includes figure candidate metadata. MIL-STD-882E page 17 and page 103 figure captions are detected as `FigureBlock` candidates. Phase 7A only detects figure captions as candidate `FigureBlock` objects; it does not extract images, detect full figure regions, or suppress table candidates inside diagrams yet. Tests, ruff, and mypy pass.

Phase 7B figure-context table suppression completed. Table candidate detection now uses detected `FigureBlock` caption context to suppress likely figure-internal labels from `TableBlock` candidate creation. MIL-STD-882E page 103 no longer creates `TableBlock` candidates for internal diagram labels such as System Risk, Hazard Tracking Log, Safety-significant Software Functions, Typical Safety Activities, CM/Drawing Control, and Operator Training; those labels remain preserved as `TextBlock` / `ParagraphBlock` content, and the FIGURE B-1 caption remains detected as a `FigureBlock` candidate. MIL-STD-882E page 19 real tables remain detected as `TableBlock` candidates, including table captions, headers, and row fragments. `PDFLoader` processing order supports figure-aware table candidate detection, original `TextBlock` objects are preserved unchanged, and `FigureBlock` and `TableBlock` objects remain candidate-level structures. Phase 7B uses conservative figure-caption context only; it does not extract figure images, compute exact figure regions, fully parse diagrams, or merge table structures. Added regression tests for figure/table interaction. Tests, ruff, and mypy pass.

---

## 8. Semantic Structuring Layer

- [x] Add RAG/export-friendly semantic block view
- [x] Add semantic Markdown export
- [ ] Build section hierarchy
- [ ] Link headings to child blocks
- [ ] Detect definitions
- [ ] Detect warnings, cautions, and notes
- [ ] Detect numbered procedures
- [ ] Detect requirement-like statements
- [ ] Detect cross-references
- [ ] Detect table and figure references

Phase 8A semantic block filtering completed. Added `get_semantic_blocks_for_page()` to return a RAG/export-friendly semantic block view that excludes raw `TextBlock` objects and suppresses duplicate `ParagraphBlock` objects when a `TableBlock`, `FigureBlock`, or `HeadingBlock` represents the same source content. Candidate table and figure blocks are preserved, and original `page.blocks` / `page.text_blocks` remain unchanged. JSON and Markdown exporter behavior remain unchanged for now. Phase 8A does not change the parser's internal traceability model, alter JSON export, implement RAG chunking, merge tables, or reconstruct table rows/columns. Added semantic block unit tests. Tests, ruff, and mypy pass.

Phase 8B semantic Markdown export completed. Added `document_to_semantic_markdown()` and `export_document_semantic_markdown()` using `get_semantic_blocks_for_page()` so Markdown can exclude raw `TextBlock` objects and suppress duplicate `ParagraphBlock` output when heading, table, or figure blocks represent the same source content. Existing Markdown and JSON exporter behavior remains unchanged, and `TableBlock` / `FigureBlock` candidates render clearly as candidate semantic blocks. Phase 8B does not implement RAG chunking, table merging, table row/column reconstruction, image extraction, or figure-region parsing. Added semantic Markdown exporter tests. Tests, ruff, and mypy pass.

---

## 9. Normalization Layer

- [x] Normalize whitespace
- [ ] Normalize hyphenation across line breaks
- [x] Normalize Unicode symbols
- [ ] Normalize units where safe
- [x] Preserve original text
- [x] Store normalized text separately from raw text
- [ ] Normalize references
- [ ] Normalize table headers

Phase 4A text normalization completed. Added the normalization package and `normalize_text()`, covered normalization behavior with unit tests, preserved raw PDF text while storing `normalized_text` separately, and updated Markdown export to indicate when normalized text is available. Tests, ruff, and mypy pass.

---

## 10. Chunking Layer

- [x] Define `Chunk` model
- [x] Implement basic semantic chunk creation
- [x] Implement section-aware chunking
- [ ] Implement paragraph-aware chunking
- [ ] Implement table-aware chunking
- [ ] Implement formula-aware chunking
- [x] Preserve source references in chunks
- [x] Exclude page/document furniture from semantic chunks
- [x] Remove embedded furniture lines from emitted chunk text
- [ ] Preserve parent-child hierarchy
- [x] Export basic chunk JSON payload

Phase 10A basic semantic chunking completed. Added the `Chunk` model and `create_semantic_chunks()` to aggregate semantic blocks from `get_semantic_blocks_for_page()` into simple RAG-oriented chunks. Raw `TextBlock` objects are excluded, source page numbers, source block ids, and available source text block ids are preserved, and table, table-region, figure, and formula candidates are labeled in chunk text. Basic `max_chars` chunk aggregation is implemented. Phase 10A does not generate embeddings, connect to vector databases, split inside oversized blocks, optimize chunk boundaries, or solve advanced table reconstruction. Added semantic chunking unit tests. Tests, ruff, and mypy pass.

Phase 10B chunk JSON export completed. Added `chunks_to_json_dict()`, `chunks_to_json()`, `export_chunks_json()`, and `export_document_chunks_json()` so semantic chunks can be written as downstream-consumable JSON with `chunk_count`, serialized chunks, source page numbers, source block ids, source text block ids, chunk type, and metadata. The CLI can optionally write semantic chunks with `--chunks-output` and `--chunk-max-chars`. Existing document JSON, Markdown, and semantic Markdown export behavior remains unchanged. Phase 10B does not generate embeddings, connect to vector databases, perform RAG ingestion, optimize chunk boundaries, or solve advanced table reconstruction. Added chunk JSON exporter tests and CLI chunk export tests. Tests, ruff, and mypy pass.

Phase 10C semantic chunk cleanup completed. Semantic block filtering now excludes page/document furniture from RAG-oriented output, including common headers, footers, page numbers, dates, standalone document IDs, short appendix page labels, and "Page intentionally left blank" text. Full document JSON export, debug Markdown export, original `page.blocks`, and original `page.text_blocks` remain unchanged, and legitimate headings such as full appendix titles are preserved. Phase 10C only cleans semantic/chunk output; it does not change the raw traceability model, generate embeddings, connect to vector databases, or solve advanced table reconstruction. Added semantic filtering and semantic chunking regression tests. Tests, ruff, and mypy pass.

Phase 10D embedded chunk furniture cleanup completed. Added line-level cleanup for emitted semantic chunk text so embedded standalone dates, document identifiers, short appendix headers, page labels, and "Page intentionally left blank" lines are removed even when they appear inside a larger paragraph/chunk. Legitimate full appendix headings and body references to appendices are preserved. Full document JSON export, debug Markdown export, raw extraction, and the parser traceability model remain unchanged. Phase 10D does not generate embeddings, connect to vector databases, or solve advanced table reconstruction. Added semantic chunking regression tests. Tests, ruff, and mypy pass.

Phase 10E section-aware chunk metadata completed. Semantic chunks now include lightweight section metadata from preceding `HeadingBlock` objects, including `section_title`, `section_path`, and `section_level` when heading context is available. Heading context supports nested levels and clears deeper levels when higher-level headings appear, and chunking closes active chunks when a new heading starts to avoid mixing content across sections. Existing chunk source references, general metadata, and page/document furniture cleanup remain preserved. Full document JSON, Markdown, and semantic Markdown export behavior remain unchanged. Phase 10E does not implement a full section tree, parent-child document hierarchy, embeddings, vector database export, or advanced table reconstruction. Added section-aware chunking regression tests. Tests, ruff, and mypy pass.

---

## 11. Validation Layer

- [x] Define validation checks
- [x] Validate document model completeness
- [ ] Validate page sequence
- [ ] Validate table integrity
- [x] Validate missing source references
- [ ] Validate low-confidence extractions
- [x] Flag pages requiring human review
- [x] Generate parsing quality report
- [x] Generate ingestion-readiness gate decision
- [x] Tune furniture-only page validation severity
- [x] Export human-readable validation summary Markdown

Phase 11A basic validation report completed. Added `ValidationIssue`, `ValidationReport`, `validate_document()`, `validate_chunks()`, and `validate_document_and_chunks()` with report-only quality checks for empty documents, OCR-required pages, missing text blocks, missing semantic blocks, excessive table candidates, multiple table regions, empty/short/long chunks, missing source references, possible furniture leakage, and missing section metadata. Validation reports include issue counts and summary metrics, validation JSON export is available, and the CLI can write validation reports with `--validation-output`. Phase 11A is a conservative quality gate only: it does not block execution, modify parsed content, generate embeddings, or perform RAG ingestion. Tests, ruff, and mypy pass.

Phase 11B validation decision / ingestion gate completed. Added `ValidationDecision`, `decide_ingestion_status()`, and `validate_document_and_chunks_with_decision()` so validation reports can be classified as `pass`, `review`, or `fail` with `can_ingest`, reason, issue counts, and review reasons. Info-only findings do not block ingestion, warnings produce review status, and errors produce fail status. Validation decision JSON export, combined validation gate JSON export, and CLI `--validation-gate-output` support are available. Existing validation report, parse, chunk, export, and CLI exit-code behavior remains unchanged. Phase 11B does not perform RAG ingestion, generate embeddings, connect to vector databases, or modify parsed content. Tests, ruff, and mypy pass.

Phase 11C furniture-only page validation tuning completed. Validation now distinguishes meaningful pages with missing semantic output from furniture-only or intentionally blank pages. Pages containing only headers, footers, dates, document identifiers, short appendix labels, page labels, or "Page intentionally left blank" no longer trigger `page.no_semantic_blocks` warnings and may be reported as `page.furniture_only` info. Gate decisions now pass when furniture-only pages are the only findings, while meaningful native text with missing semantic output still warns. Existing parsing, chunking, export, validation report, and CLI exit-code behavior remains unchanged. Phase 11C does not change semantic extraction, generate embeddings, or perform RAG ingestion. Tests, ruff, and mypy pass.

Phase 11D human-readable validation summary completed. Added Markdown export for `ValidationReport` and combined validation gate output, including decision status, ingestion readiness, reason, document info, summary metrics, issue counts, review reasons, and an issue table with safe Markdown table escaping. Empty validation reports render clearly, validation Markdown export tests were added, and the CLI can write summaries with `--validation-summary-output`. Existing parsing, chunking, validation, JSON export, and CLI exit-code behavior remains unchanged. Phase 11D does not change parser behavior, chunking behavior, validation decision logic, embeddings, vector database export, or RAG ingestion. Tests, ruff, and mypy pass.

---

## 12. Export Layer

- [x] JSON exporter
- [x] Markdown exporter
- [x] RAG chunk JSON exporter
- [x] Add schema/parser metadata to exported artifacts
- [x] Add output manifest JSON support
- [ ] Debug HTML exporter
- [ ] Optional SQLite exporter
- [ ] Optional YAML exporter

Phase 2B JSON export support completed. Added `export_document_json()`, exporter unit tests, and README usage for local development, PDF parsing, JSON export, and current limitations. Tests, ruff, and mypy pass.

Phase 3A Markdown export support completed. Added `document_to_markdown()` and `export_document_markdown()`, exported them from the exporters package, documented usage in README, and covered title/id, source path, metadata, page status, text blocks, and source traceability in tests. Tests, ruff, and mypy pass.

Phase 12B schema and parser metadata completed. Exported machine-readable artifacts now include `schema_version` and parser metadata with parser name and parser version. Document JSON, chunk JSON, validation JSON, validation gate JSON, and validation summary Markdown now emit versioned output content while preserving existing CLI behavior and file outputs. Added export metadata tests and updated exporter and CLI regression tests. Phase 12B only adds version metadata to exported artifacts; it does not change parsing, chunking, validation decisions, CLI flags, embeddings, vector database export, or AviationRAG ingestion. Tests, ruff, and mypy pass.

Phase 12C output manifest JSON completed. Added manifest generation for produced artifacts with `schema_version`, parser metadata, source document path and id, generated output artifact paths, validation decision when available, and document, chunk, and validation metrics when available. Added manifest JSON export helpers, CLI `--manifest-output` support, output manifest tests, and CLI regression tests. Existing parsing, chunking, validation, JSON export, Markdown export, and CLI exit-code behavior remains unchanged. Phase 12C does not change validation decision logic, generate embeddings, export to vector databases, or perform AviationRAG ingestion. Tests, ruff, and mypy pass.

---

## 13. Testing Strategy

- [ ] Create test document set
- [x] Add simple generated PDFs for unit tests
- [ ] Add real-world technical PDF samples where legally permitted
- [x] Unit tests for data models
- [x] Unit tests for PDF loader
- [ ] Unit tests for layout analysis
- [x] Unit tests for heading detection
- [x] Unit tests for paragraph grouping
- [x] Unit tests for table detection
- [x] Unit tests for exporters
- [x] Unit tests for CLI
- [x] Integration test for full PDF pipeline
- [ ] Golden-file tests for JSON output
- [ ] Regression tests for difficult documents

---

## 14. Documentation

- [ ] Write README overview
- [x] Write installation instructions
- [x] Write quick-start example
- [x] Write architecture overview
- [ ] Write data model documentation
- [x] Write pipeline documentation
- [x] Document full output package CLI workflow
- [x] Write output contract and schema alignment audit
- [x] Document MVP release readiness checkpoint
- [ ] Write contribution guide
- [ ] Write verification approach

Phase 12A output contract and schema alignment audit completed. Added `docs/output_contract_0_1_0_audit.md` documenting the current parser output package, internal model coverage, document JSON, chunk JSON, validation JSON, gate JSON, validation Markdown outputs, and compatibility against the intended `techdoc-structured-document / 0.1.0` target. The audit identifies missing capabilities before AviationRAG D.4c, categorizes gaps into must-have, should-have, and can-wait, and recommends next implementation steps. Phase 12A is documentation only: it does not implement missing schema fields, change parser behavior, or perform AviationRAG ingestion. Tests, ruff, and mypy pass.

Phase 12D README full-package CLI usage documentation completed. README now documents the full output package workflow for generating document JSON, chunk JSON, validation JSON, gate JSON, validation summary Markdown, and manifest JSON; explains each artifact's purpose; documents schema/parser metadata; points downstream systems to `manifest.json`; defines pass/review/fail gate meanings; and summarizes MVP limitations for native-text PDFs, OCR, tables, section hierarchy, and formulas. Phase 12D is documentation only and does not change parser, model, exporter, CLI, validation, runtime behavior, `PROJECTPLAN.md`, or AviationRAG ingestion. Tests, ruff, and mypy pass.

Phase 12E architecture and pipeline overview documentation completed. Added `docs/architecture_pipeline_overview.md` covering the current MVP architecture, major packages and responsibilities, processing stages from PDF ingestion to output package generation, raw `TextBlock` preservation and derived semantic blocks, output artifacts with schema/parser metadata, validation and gate philosophy, MVP scope and limitations, and AviationRAG integration starting from `manifest.json`. README links to the overview. Phase 12E is documentation only and does not change parser, model, exporter, CLI, validation, runtime behavior, `PROJECTPLAN.md`, or AviationRAG ingestion. Tests, ruff, and mypy pass.

Phase 12F MVP release readiness checkpoint completed. Added `docs/mvp_readiness_checklist.md` documenting the MVP baseline, required output package, final FAA verification command, expected validation gate result, release verification checklist, known MVP limitations, AviationRAG handoff contract using `manifest.json`, and optional `v0.1.0-mvp` tag recommendation. README links to the checklist. Phase 12F is a release-readiness checkpoint only and does not change parser, model, exporter, CLI, validation, runtime behavior, `PROJECTPLAN.md`, generate embeddings, export to vector databases, or perform AviationRAG ingestion. Tests, ruff, and mypy pass.

Phase 13A AviationRAG StructuredDocument contract gap analysis completed. Added `docs/aviationrag_structured_document_gap_analysis.md` and `docs/aviationrag_structured_document_mapping.json` after reviewing the current parser architecture, current output package, and read-only AviationRAG `techdoc-structured-document / 0.1.0` design fixture and validator. The analysis records direct mappings, partial mappings, missing parser capabilities, ownership boundaries, retention recommendation, minimum viable contract, risks, and a controlled implementation sequence. Phase 13A is documentation only: it does not implement structured-document export, change parser/runtime/CLI behavior, process real documents, modify AviationRAG, generate embeddings, or perform ingestion. Recommended next phase is Phase 13B - StructuredDocument contract foundation.

Phase 13B StructuredDocument contract foundation completed. Added an isolated `techdoc_parser.contracts` package with `techdoc-structured-document / 0.1.0` schema constants, contract dataclasses, version guards, deterministic dictionary/JSON serialization, empty unsupported entity collections, and a synthetic minimum fixture. Added documentation and regression tests covering schema identity, supported-version rejection, document metadata null/absent policy, zero-based PDF indexes, one-based page numbers, unknown printed page labels, empty sections, block/source-span ordering, Unicode preservation, no implicit timestamps or absolute paths, no file-writing side effects, and unchanged existing document JSON and manifest shapes. Phase 13B does not map parser models, add CLI output, modify AviationRAG, process real documents, generate embeddings, use Astra or FAISS, or change parser extraction, chunking, validation, Markdown, current JSON, manifest, or CLI behavior. Recommended next phase is Phase 13C - Document, Page, Block, and Source-Span mapping.

Phase 13C Document, Page, Block, and SourceLocation mapping completed. Added a pure `techdoc_parser.contracts` mapper that converts existing parser `Document`, `Page`, `Block`, `SourceLocation`, and `BoundingBox` evidence into the `techdoc-structured-document / 0.1.0` contract without mutating parser objects or invoking current exporters. The mapper preserves caller-supplied document IDs and optional metadata, maps source filenames without absolute path leakage, preserves page order, derives zero-based PDF page indexes from one-based page numbers, preserves block order, emits deterministic page/document block indexes, preserves existing block IDs, generates fallback block IDs only when necessary, maps raw text separately from normalized text, maps bounding boxes and extraction methods, and keeps placeholder confidence, character offsets, printed page labels, sections, advanced entities, and fabricated checksums absent. Added `tests/test_structured_document_mapper.py`, a synthetic mapped fixture, and `docs/structured_document_mapping.md`; updated the contract docs, gap analysis, mapping matrix, architecture overview, and README. No section hierarchy, root table/figure/equation/admonition/cross-reference entities, CLI integration, current-output changes, real-document processing, AviationRAG modification, embeddings, Astra, or FAISS work occurred. Existing JSON, Markdown, validation, gate, manifest, and CLI behavior remain unchanged. Validation commands run for Phase 13C are recorded in the final task result. Recommended next phase is Phase 13D - Section hierarchy and source-span enrichment.

Phase 13D Section hierarchy and source-span enrichment completed. Added a pure contract-local hierarchy builder that derives durable `StructuredDocumentSection` records from existing `HeadingBlock` evidence, assigns deterministic section IDs, preserves raw and optional normalized headings, parses only explicit numeric section numbers, appendix/annex labels, and AMC/GM-style clause identifiers, builds parent-child paths from current heading levels, assigns block `section_id` values after the active heading, leaves pre-heading blocks unassigned, and computes section source spans from directly assigned blocks. Added focused hierarchy tests, an enriched synthetic fixture, `docs/structured_document_hierarchy.md`, and updated structured-document mapping, contract, architecture, README, gap-analysis, and mapping-matrix docs. Phase 13D did not change parser extraction, OCR, reading-order detection, block creation or normalization, chunking, current JSON, Markdown, manifest, validation, gate, CLI behavior, AviationRAG, advanced entity roots, checksums, page labels, confidence scores, character offsets, or proprietary corpus processing. Recommended next phase is either Phase 13E - Advanced entity mapping from truthful parser evidence or Phase 13G - Optional structured-document CLI/manifest output.

Phase M.3 Legacy Repository Structure and Cleanup-Readiness Audit completed. Added `docs/legacy_repository_structure_audit.md` and `docs/legacy_repository_structure_inventory.json` after reviewing Git branch/tag/stash state, tracked files, ignored local artifacts, package entry points, runtime modules, CLI/exporter/validation paths, contract modules, tests, fixtures, documentation, and generated output locations. The audit classifies cleanup as useful but non-blocking: no tracked runtime module, CLI path, exporter, contract module, test fixture, branch, tag, or stash currently blocks continued Phase 13 work. Recommended cleanup is limited to later local ignored-artifact review and documentation staleness labeling/archive decisions. M.3 was audit/documentation only: no files were removed, moved, or renamed; no parser, CLI, exporter, validation, contract, fixture, or current-output behavior changed; no proprietary documents were processed; and AviationRAG was not modified. Recommended next phase is Phase 13E1 - table and figure-caption mapping from truthful parser evidence.

Phase 13E1 Table and Figure-Caption Mapping from Existing Evidence completed. Added `src/techdoc_parser/contracts/structured_document_entities.py` and wired the pure structured-document mapper to populate root `tables` and `figures` from existing `TableBlock`, `TableRegionBlock`, and `FigureBlock` evidence only. Root table and figure entities preserve deterministic IDs, exact text/caption evidence, page refs, source spans, source block references, optional bounding boxes, section IDs/paths when available, and candidate status. Table root entities intentionally leave `columns`, `rows`, `cells`, `header_rows`, and `merged_cells` empty because current parser rows are line fragments, not reconstructed cells. Figure root entities omit `asset_reference` unless real `FigureBlock.image_path` evidence exists. Added focused tests, a synthetic fixture, and documentation updates. Phase 13E1 did not change PDF extraction, OCR, reading order, block creation, table or figure detection heuristics, table cell reconstruction, figure asset extraction, chunking, current JSON, Markdown, manifest, validation, gate, or CLI behavior; did not modify AviationRAG; did not process proprietary documents; did not add dependencies; and did not perform cleanup. Recommended next phase is Phase 13E2 - equation/admonition mapping from truthful parser evidence, Phase 13F - cross-reference/confidence policy, or Phase 13G - optional structured-document CLI/manifest output.

Phase 13E2 Equation and Admonition Evidence Implementation completed. Added conservative equation evidence detection, explicit-label admonition evidence detection, and `src/techdoc_parser/contracts/structured_document_equations_admonitions.py`, then wired the pure structured-document mapper to populate root `equations` and `admonitions` from truthful existing parser evidence only. Equation entities preserve exact raw text, optional explicit labels, existing `FormulaBlock.latex` notation when present, page/source spans, source block references, optional bounding boxes, and section paths. Admonition entities preserve exact labels, normalized validator-compatible types, body text, page/source spans, source block references, and section paths for explicit `WARNING`, `CAUTION`, `NOTE`, `IMPORTANT`, and `SAFETY NOTICE` labels only. Added focused tests, a synthetic fixture, and documentation updates. Phase 13E2 did not change PDF extraction, OCR, reading order, block creation, chunking, current JSON, Markdown, manifest, validation, gate, or CLI behavior; did not add dependencies; did not infer mathematical meaning, safety severity, confidence values, cross-references, or typography-only labels; did not modify AviationRAG; did not process proprietary documents; and did not perform cleanup. Recommended next phase is Phase 13F - cross-reference/confidence policy, Phase 13G - optional structured-document CLI/manifest output, or scoped formula discovery/table-structure parser enhancement.

Phase 13F Cross-Reference and Confidence Policy completed. Added explicit textual cross-reference detection, deterministic root `cross_references` mapping, exact local resolution against known sections/tables/figures/equations, explicit `resolved`, `unresolved`, `external`, `ambiguous`, and `not_attempted` status handling, and confidence-policy helpers that reject invalid confidence values while omitting current placeholder `SourceLocation.confidence` values. Added a focused synthetic fixture, regression tests, README and structured-document documentation updates, and read-only AviationRAG validator compatibility evidence. Phase 13F did not change PDF extraction, OCR, reading order, block creation, chunking, current JSON, Markdown, manifest, validation, gate, or CLI behavior; did not add dependencies, external lookup, fuzzy matching, ML/LLM logic, PDF link/bookmark parsing, parser-core `Reference` or `ConfidenceScore` models, AviationRAG runtime dependencies, or AviationRAG modifications; did not process proprietary documents; and did not perform cleanup. Recommended next phase is Phase 13G - optional structured-document CLI/manifest output or Phase 13H - formal synthetic AviationRAG compatibility validation.

Phase 13G Optional StructuredDocument API, File, CLI, and Manifest Output completed. Added public `build_structured_document_artifact()`, `compute_source_sha256()`, `write_structured_document()`, `export_structured_document()`, and `StructuredDocumentArtifact` APIs; source SHA-256 ownership from exact input bytes; deterministic UTF-8 JSON bytes with final newline; safe sibling temporary-file write behavior; explicit overwrite; optional CLI output through `--structured-document-output` with required `--structured-document-id`; optional explicit metadata flags; and additive manifest registration with source and artifact checksums. Existing defaults remain unchanged: no StructuredDocument file is created unless explicitly requested, current parser APIs remain compatible, current JSON/Markdown/chunk/validation/gate output behavior remains unchanged, manifest shape remains unchanged when the new artifact is absent, no dependency changes were added, no AviationRAG runtime dependency was added, no proprietary documents were processed, no AviationRAG files were modified, and no repository cleanup was performed. Validation commands for Phase 13G are recorded in the final task result. Table-count ambiguity remains for Phase 13H; next phase is Phase 13H - Formal AviationRAG compatibility gate.

Phase 13H Formal AviationRAG Compatibility Gate completed. Added isolated `techdoc_parser.compatibility` APIs and `tools/compatibility/run-aviationrag-compatibility-gate.py` to validate a Phase 13G structured-document artifact, manifest, exact source bytes, optional comparison artifact, warning policy, and external AviationRAG validator report. The gate checks manifest registration, source and artifact SHA-256 consistency, metadata consistency, validator errors/warnings, table-count interpretation, cross-reference integrity, confidence-field policy, determinism, and detected AviationRAG commit metadata. Added synthetic validator fixtures and tests that use fake adapters instead of requiring a sibling AviationRAG checkout; added compatibility documentation and updated README, architecture, mapping, gap-analysis, contract, export, and reference/confidence docs. Existing parser defaults, current JSON/Markdown/chunk/validation/gate/manifest behavior, Phase 13G export behavior, and AviationRAG files remain unchanged. No AviationRAG runtime dependency, ingestion, embeddings, Astra, FAISS, proprietary corpus processing, parser repair, or repository cleanup was added. Recommended next phase is Phase 13I - Controlled approved-document accuracy pilot or scoped parser enhancements for table structure, page labels, PDF links/bookmarks, formula discovery, or truthful confidence evidence.

Phase 13I Fixture-Based Chunk Quality Evaluation Framework completed. Added `techdoc_parser.evaluation` with deterministic fixture-only chunk-quality proxy models, evaluator, JSON/Markdown serialization, explicit report-write gating, `tools/evaluation/run-chunk-quality-evaluation.py`, a committed fixture registry, and an expected baseline. The evaluator uses existing committed synthetic structured-document fixtures only and scores source-block coverage, reference integrity, reading order, section coherence, chunk size, duplicate text, duplicate source references, exact overlap, current-model provenance, table/figure/equation/admonition/cross-reference source preservation, table-cell accuracy not-measurable status, source-page visual accuracy not-measurable status, and determinism. The current baseline evaluates five fixture cases and returns aggregate `REVIEW`, with no `FAIL`, because source checksum provenance, visual source accuracy, and table-cell accuracy remain outside the fixture-only scope. Phase 13I did not modify parser behavior, extraction, OCR, reading order, block detection, chunk generation, current JSON/Markdown/manifest or StructuredDocument output, CLI defaults, dependencies, AviationRAG, embeddings, Astra, FAISS, external APIs, LLM similarity, proprietary documents, or repository cleanup. Fixture metrics are quality proxies only; they do not prove source-page visual accuracy, OCR accuracy, semantic accuracy, or real aviation-document accuracy. Recommended next phase is Phase 13I-b - Controlled approved-document source-accuracy pilot.

Phase 13I-b1 Approved Pilot-Corpus Inventory and Representative-Page Planning completed. Added read-only pilot-corpus inventory models, metadata-only PyMuPDF inspection, corpus count and expected-document matching, duplicate hash grouping for local reports, Git ignore/tracked protection checks, access/encryption status, native/scanned/uncertain classification, page geometry/layout/special-content signals, deterministic representative-page proposal, JSON/Markdown report serialization gated by `--allow-report-write`, `tools/evaluation/run-pilot-corpus-inventory.py`, synthetic tests, and sanitized documentation. The approved local corpus run found 8 ignored PDFs, 2,937 total pages, 0 duplicate hash groups, 0 tracked PDFs, 0 access errors, and outcome `REVIEW` because `Airplane_Maintenance_Manual_CIRRUS_Design_SR22.pdf` has uncertain text-mode classification. Full hash-bearing reports were written only to ignored `output/`; committed docs contain no hashes, source text, images, or PDF contents. Phase 13I-b1 did not modify, move, rename, delete, stage, or commit PDFs; did not run OCR; did not evaluate source accuracy; did not alter parser behavior, extraction, chunking, current JSON/Markdown/manifest output, StructuredDocument output, dependencies, or `pyproject.toml`; did not use external APIs, web, embeddings, vector databases, or LLM document analysis; and did not modify AviationRAG. Recommended next phase is Phase 13I-b2 - owner-approved representative-page source-accuracy pilot.

Phase 13I-b2 Controlled Representative-Page Source-Accuracy Review completed. Added an isolated report-only P0 source-accuracy evaluator, sanitized JSON/Markdown serializers, explicit report/evidence write gating, `tools/evaluation/run-source-accuracy-pilot.py`, a committed 32-page P0 execution plan, synthetic regression tests, and sanitized documentation. The approved local run scored only the 32 P0 pages across the 8 ignored PDFs in `input/`; it returned aggregate `FAIL` with 25 final `FAIL` pages, 7 final `REVIEW` pages, 0 final `PASS` pages, and 32 pending human visual reviews. Full local evidence, rendered page images, source proxies, and parser artifacts were written only under ignored `output/evaluation/source_accuracy_p0/`; committed documentation contains no extracted source text, source hashes, images, proprietary procedures, table contents, or equations. Deterministic reruns produced byte-identical sanitized reports. Phase 13I-b2 did not modify, move, rename, delete, stage, or commit PDFs; did not process P1/P2 pages for scoring; did not score full-document accuracy; did not run OCR; did not alter parser behavior, extraction, reading order, block creation, heading/table/figure/equation/admonition/reference detection, chunking, StructuredDocument output, Phase 13I baseline, dependencies, or `pyproject.toml`; did not use embeddings, LLM evaluation, external APIs, web, Astra, FAISS, or AviationRAG. Recommended next phase is a scoped parser enhancement selected from the documented P0 findings, with any visual review completion handled through explicit local checklists.

Phase 13I-c1 P0 Failure Triage and Root-Cause Isolation completed. Added diagnosis-only P0 failure triage models, pipeline-stage observations, root-cause classification, sanitized JSON/Markdown serialization, explicit report/evidence write gating, `tools/evaluation/run-p0-failure-triage.py`, a committed 10-case sanitized triage plan, focused regression tests, and sanitized documentation. The approved local triage run processed 10 selected P0 pages and 48 original findings, returned aggregate `REVIEW`, classified 0 confirmed parser defects, 9 evaluator defects, 7 source-proxy limitations, 3 expected multi-representation findings, 4 document-layout limitations, and 25 findings needing visual confirmation. Full local evidence was written only under ignored `output/evaluation/p0_failure_triage/`; committed documentation contains no extracted source text, source hashes, rendered pages, images, proprietary procedures, table contents, or equations. Phase 13I-c1 did not modify source PDFs, OCR, extraction, reading order, normalization, heading/section/table/figure/equation/admonition/reference detection, chunking, StructuredDocument mapping/output, the Phase 13I fixture baseline, the Phase 13I-b2 P0 results, dependencies, `pyproject.toml`, AviationRAG, embeddings, LLM/external APIs, Astra, or FAISS. Recommended next phase is Phase 13I-c2E - evaluator-policy correction for raw-coverage status coupling, chunk source-coverage eligibility, and candidate table interpretation, followed by rerunning the 10-case triage subset and the original 32-page P0 pilot.

Phase 13I-c2E Source-Accuracy Evaluation-Policy Correction completed. Added policy identity constants for `p0-source-accuracy / 2.0`, additive correction records, deterministic policy correction serialization, and shared source-block chunk eligibility used by source accuracy, chunk quality, and triage diagnostics. Corrected evaluator policy decouples raw coverage from duplicate handling, reclassifies source-proxy duplicates as review, keeps parser-only duplicates as failures, treats reading-order inversions as review pending visual confirmation, applies canonical chunk source-block eligibility, preserves candidate table interpretation as a review/contract limitation, and keeps metric statuses independent. The original Phase 13I-b2 result remains historical policy-v1 evidence: 25 final `FAIL`, 7 final `REVIEW`, 0 final `PASS`. The corrected 32-page P0 rerun is separately identified as `run_type: corrected_evaluator_rerun`, returned aggregate `REVIEW` with 32 final `REVIEW`, 0 final `FAIL`, 0 final `PASS`, and 32 pending visual reviews, and produced byte-identical sanitized rerun reports. Phase 13I-c2E did not modify source PDFs, OCR, extraction, raw parser blocks, normalization, parser reading-order behavior, heading/section/table/figure/equation/admonition/cross-reference detection, semantic chunk generation, chunk IDs, StructuredDocument mapping, current parser outputs, dependencies, `pyproject.toml`, AviationRAG, embeddings, external APIs, Astra, FAISS, P1/P2 processing, or repository cleanup. Recommended next step is owner visual review of the corrected 32-page P0 evidence before pilot acceptance or parser corrective work.

---

## 15. Tooling and Quality

- [x] Configure `ruff`
- [x] Configure `pytest`
- [x] Configure `mypy` or `pyright`
- [ ] Configure `pre-commit`
- [ ] Configure GitHub Actions CI
- [ ] Add code coverage reporting
- [x] Add type hints across core models
- [x] Add docstrings for public APIs

Current checks pass: `pytest`, `ruff check .`, `ruff format --check .`, and `mypy src`.

Phase 2C CLI support completed. Added `techdoc-parse`, PDF-to-JSON CLI output, `--output`/`-o`, `--indent`, user-facing error handling, generated-PDF CLI tests, and README CLI usage. Tests, ruff, and mypy pass.

---

## 16. Future Enhancements

- [ ] OCR support
- [ ] DOCX support
- [ ] HTML support
- [ ] Formula-to-LaTeX extraction
- [ ] Advanced table reconstruction
  - [ ] Row/column inference
  - [ ] Table region validation
  - [ ] Adapter strategy for specialized table extraction engines
- [ ] LLM-assisted document cleanup
- [ ] Human-in-the-loop review workflow
- [ ] Knowledge graph export
- [ ] Aviation-specific parser profiles
- [ ] Standards-specific parser profiles
- [ ] Certification requirement extraction
- [ ] Interface with vector databases
- [ ] Interface with LangChain/LlamaIndex

---

## 17. First Practical Milestone

**Milestone 1 objective:**  
Create a minimal package that can load a PDF, extract page text with page numbers, represent it in an internal `Document` object, and export it to JSON.

Acceptance criteria:

- [x] Project installs locally with `pip install -e .`
- [x] CLI command exists:

```bash
techdoc-parse input.pdf --output output.json
```

- [x] Output JSON contains:
  - [x] document metadata
  - [x] pages
  - [x] page numbers
  - [x] text blocks
  - [x] source references
- [x] Unit tests pass
- [x] README contains basic usage example
