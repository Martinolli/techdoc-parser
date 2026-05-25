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

- [ ] Define validation checks
- [ ] Validate document model completeness
- [ ] Validate page sequence
- [ ] Validate table integrity
- [ ] Validate missing source references
- [ ] Validate low-confidence extractions
- [ ] Flag pages requiring human review
- [ ] Generate parsing quality report

---

## 12. Export Layer

- [x] JSON exporter
- [x] Markdown exporter
- [x] RAG chunk JSON exporter
- [ ] Debug HTML exporter
- [ ] Optional SQLite exporter
- [ ] Optional YAML exporter

Phase 2B JSON export support completed. Added `export_document_json()`, exporter unit tests, and README usage for local development, PDF parsing, JSON export, and current limitations. Tests, ruff, and mypy pass.

Phase 3A Markdown export support completed. Added `document_to_markdown()` and `export_document_markdown()`, exported them from the exporters package, documented usage in README, and covered title/id, source path, metadata, page status, text blocks, and source traceability in tests. Tests, ruff, and mypy pass.

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
- [ ] Write architecture overview
- [ ] Write data model documentation
- [ ] Write pipeline documentation
- [ ] Write contribution guide
- [ ] Write verification approach

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
