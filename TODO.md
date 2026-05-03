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
- [ ] Detect paragraphs
- [ ] Detect basic tables
- [ ] Preserve table row/column structure where possible
- [ ] Detect potential formula blocks
- [x] Export structured JSON
- [x] Export readable Markdown
- [ ] Create simple RAG chunks with source references

Phase 4B basic heading detection completed. Added the structure package, conservative heading heuristics, `is_heading_text()`, `detect_heading_level()`, and `create_heading_block_from_text_block()`. `PDFLoader` now adds obvious `HeadingBlock` objects to `page.blocks` while preserving original `TextBlock` objects in both `page.text_blocks` and `page.blocks`. Tests, ruff, and mypy pass.

Phase 4C line-level heading extraction completed. Added `extract_heading_blocks_from_text_block()`, MIL-STD-style task and appendix heading patterns, embedded multiline `TextBlock` heading extraction, duplicate suppression, and false-positive tests. `PDFLoader` now appends all detected `HeadingBlock` objects while preserving original `TextBlock` objects unchanged. Tests, ruff, and mypy pass.

Phase 4C is a first-pass candidate heading detector, not final semantic heading classification. Real-document validation showed that content capture is good, but semantic heading classification still needs refinement before it should be used for final RAG chunk hierarchy.

Phase 4D — Context-aware heading filtering:

- [ ] Reject numbered body paragraphs incorrectly detected as headings
- [ ] Reject table-of-contents entries with dot leaders and page numbers
- [ ] Reject heading candidates from Contents pages, except the "Contents" heading itself
- [ ] Reject sentence-like Appendix references
- [ ] Improve MIL-STD-882E heading precision
- [ ] Improve AC-120-92 heading precision
- [ ] Preserve detected true headings such as 1. SCOPE, 2. APPLICABLE DOCUMENTS, TASK 101, and APPENDIX A actual section headings
- [ ] Add regression tests based on observed MIL-STD-882E and AC-120-92 false positives

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
- [ ] Detect headers and footers
- [ ] Detect page numbers
- [ ] Detect multi-column layout
- [ ] Detect captions
- [ ] Detect footnotes
- [ ] Add layout confidence score

---

## 7. Content Extraction Layer

- [ ] Implement text block extraction
- [ ] Implement heading detection
- [ ] Implement paragraph grouping
- [ ] Implement table detection
- [ ] Implement simple table extraction
- [ ] Implement formula candidate detection
- [ ] Implement figure/image candidate detection
- [ ] Attach source location to every extracted object

---

## 8. Semantic Structuring Layer

- [ ] Build section hierarchy
- [ ] Link headings to child blocks
- [ ] Detect definitions
- [ ] Detect warnings, cautions, and notes
- [ ] Detect numbered procedures
- [ ] Detect requirement-like statements
- [ ] Detect cross-references
- [ ] Detect table and figure references

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

- [ ] Define `Chunk` model
- [ ] Implement section-aware chunking
- [ ] Implement paragraph-aware chunking
- [ ] Implement table-aware chunking
- [ ] Implement formula-aware chunking
- [ ] Preserve source references in chunks
- [ ] Preserve parent-child hierarchy
- [ ] Export vector-database-friendly payload

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
- [ ] RAG chunk exporter
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
- [x] Unit tests for exporters
- [x] Unit tests for CLI
- [ ] Integration test for full PDF pipeline
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
