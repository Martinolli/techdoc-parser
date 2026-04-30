# PROJECTPLAN.md — Technical Document Parsing Python Library

## 1. Project Vision

The goal of this project is to create a Python library capable of parsing complex technical documents into structured, traceable, machine-usable representations suitable for Retrieval-Augmented Generation, technical search, and engineering knowledge extraction.

The library is intended for technical domains where document fidelity matters, especially aviation, aerospace, flight test, certification, safety management, engineering standards, manuals, and technical books.

The core idea is not simply to extract text from documents. The library shall preserve document structure, source traceability, technical objects, and extraction confidence.

---

## 2. Mission Statement

Develop a systems-engineered Python library that converts complex technical documents into structured, traceable, RAG-ready data while preserving source fidelity, layout context, and technical meaning.

---

## 3. Problem Statement

Technical RAG systems depend heavily on document ingestion quality. When technical documents contain complex tables, formulas, figures, procedures, notes, warnings, cross-references, and multi-column layouts, ordinary text extraction often produces unreliable chunks.

This creates downstream problems:

- incorrect retrieval
- broken context
- missing table relationships
- lost formulas
- poor traceability
- hallucinated answers
- inability to cite exact sources
- poor confidence in engineering or aviation use cases

Therefore, the parsing layer must be treated as a core system, not as a minor preprocessing step.

---

## 4. System Engineering Approach

This project shall follow a V-model-inspired development approach.

The top-down side defines:

1. Mission need
2. High-level requirements
3. System architecture
4. Subsystem requirements
5. Component design
6. Unit design

The bottom-up side verifies:

1. Unit tests
2. Component tests
3. Subsystem integration tests
4. System integration tests
5. Validation against representative technical documents

The software architecture shall use systems-engineering-style decomposition while keeping software terminology clear.

Recommended mapping:

| Systems Engineering Term | Software Project Equivalent |
| --- | --- |
| System | Complete Python library |
| Subsystem | Capability domain or package |
| Component | Module, class, or service |
| Unit | Function or method |
| Interface | Public API, internal protocol, or data contract |
| Verification | Automated tests and validation checks |
| Validation | Demonstration against real technical use cases |

---

## 5. High-Level Requirements

### HLR-001 — Technical Document Parsing

The library shall parse technical documents into a structured internal document representation.

### HLR-002 — Source Traceability

The library shall preserve source traceability for every extracted object whenever technically possible.

Traceability should include:

- source file
- page number
- section identifier when available
- bounding box when available
- extraction method
- confidence score

### HLR-003 — Structured Output

The library shall output structured data, not only plain text.

The internal model shall support:

- documents
- pages
- sections
- headings
- paragraphs
- tables
- formulas
- figures
- captions
- references
- chunks

### HLR-004 — RAG Readiness

The library shall generate chunks suitable for Retrieval-Augmented Generation systems.

Chunks shall preserve:

- text content
- source references
- document hierarchy
- parent section
- related tables or formulas where applicable

### HLR-005 — Technical Tables

The library shall detect and extract tables while attempting to preserve row, column, header, and unit relationships.

### HLR-006 — Formula Awareness

The library shall detect formula candidates and preserve their source location, even when full formula recognition is not available in the initial MVP.

### HLR-007 — Layout Awareness

The library shall analyze page layout to improve reading order, section detection, and block grouping.

### HLR-008 — Extensibility

The library shall allow different extraction engines to be used through adapters.

Examples:

- PyMuPDF
- pdfplumber
- OCR engines
- table extraction libraries
- LLM-assisted extraction modules

### HLR-009 — Validation and Confidence

The library shall provide validation checks and confidence indicators for extracted content.

### HLR-010 — Reproducibility

The same input document and configuration shall produce reproducible output unless explicitly using nondeterministic components.

### HLR-011 — Human Review Support

The library shall flag low-confidence or structurally suspicious extraction results for possible human review.

### HLR-012 — MVP Scope Control

The first MVP shall focus on native-text PDFs and shall not attempt to solve all OCR, formula recognition, and advanced table reconstruction problems immediately.

---

## 6. Non-Goals for the MVP

The MVP shall not attempt to fully solve:

- scanned-document OCR
- handwriting recognition
- perfect formula-to-LaTeX conversion
- perfect table reconstruction for all PDF types
- legal interpretation of standards
- automatic engineering correctness validation
- real-time parsing of very large document repositories
- GUI-based human review
- full knowledge graph generation

These may become future capabilities.

---

## 7. Target Users

Primary users:

- engineers building RAG systems
- aviation and aerospace technical specialists
- safety and certification engineers
- flight test engineers
- technical documentation teams
- AI/LLM developers working with technical documents

Secondary users:

- researchers
- educators
- compliance teams
- knowledge management teams

---

## 8. Target Document Types

Initial target documents:

- technical PDFs
- manuals
- standards
- engineering books
- flight test documents
- certification guidance material
- safety documentation
- procedures
- reports

Future target documents:

- DOCX
- HTML
- scanned PDFs
- images
- XML-based technical publications

---

## 9. Concept of Operations

A typical user workflow should look like this:

```bash
techdoc-parse input.pdf --output parsed_document.json
```

Or in Python:

```python
from techdoc_parser import parse_document

result = parse_document("input.pdf")
result.to_json("parsed_document.json")
result.to_markdown("parsed_document.md")
```

The user should receive structured output that can be inspected, validated, and passed to a RAG ingestion pipeline.

---

## 10. Proposed Architecture

```text
techdoc_parser/
│
├── core/
│   ├── document.py
│   ├── page.py
│   ├── block.py
│   ├── source.py
│   └── schema.py
│
├── ingestion/
│   ├── base.py
│   ├── pdf_loader.py
│   └── file_detector.py
│
├── layout/
│   ├── analyzer.py
│   ├── reading_order.py
│   ├── columns.py
│   └── headers_footers.py
│
├── extraction/
│   ├── text.py
│   ├── headings.py
│   ├── tables.py
│   ├── formulas.py
│   └── figures.py
│
├── normalization/
│   ├── text.py
│   ├── units.py
│   └── references.py
│
├── semantic/
│   ├── sections.py
│   ├── requirements.py
│   ├── procedures.py
│   └── cross_references.py
│
├── chunking/
│   ├── base.py
│   ├── semantic_chunker.py
│   └── rag_chunker.py
│
├── validation/
│   ├── checks.py
│   ├── quality.py
│   └── report.py
│
├── exporters/
│   ├── json_exporter.py
│   ├── markdown_exporter.py
│   └── vector_payload.py
│
└── cli.py
```

---

## 11. Processing Pipeline

The initial pipeline shall follow this sequence:

```text
Input Document
      ↓
File Detection
      ↓
PDF Loading
      ↓
Page Extraction
      ↓
Layout Analysis
      ↓
Block Detection
      ↓
Content Extraction
      ↓
Semantic Structuring
      ↓
Normalization
      ↓
Validation
      ↓
Chunking
      ↓
Export
```

---

## 12. Internal Document Model

The internal document model is the center of the library.

Proposed top-level structure:

```text
Document
├── metadata
├── pages
├── sections
├── blocks
├── tables
├── formulas
├── figures
├── references
├── chunks
└── validation_report
```

Each extracted object should preserve source information.

Example conceptual object:

```python
TextBlock(
    id="block_001",
    text="The aircraft shall maintain controllability...",
    page_number=12,
    bbox=(72.0, 145.0, 520.0, 170.0),
    block_type="paragraph",
    section_id="sec_3_2",
    confidence=0.95,
)
```

---

## 13. MVP Definition

### MVP Goal

Create a minimal working library that parses native-text PDFs into structured JSON and Markdown with page-level traceability.

### MVP Capabilities

The MVP shall:

- accept PDF input
- extract document metadata
- extract pages
- extract text blocks
- preserve page numbers
- preserve bounding boxes when available
- detect basic headings
- detect paragraphs
- detect simple tables where possible
- identify formula candidates where possible
- create a structured `Document` object
- export JSON
- export Markdown
- create simple RAG-ready chunks
- provide basic validation report

### MVP Exclusions

The MVP shall not include:

- advanced OCR
- full formula recognition
- perfect complex table reconstruction
- GUI review workflow
- advanced aviation-specific semantic extraction

---

## 14. Verification Strategy

### Unit Verification

Each core model, parser, and exporter shall have unit tests.

Examples:

- `Document` can serialize to JSON
- `Page` preserves page number
- `TextBlock` preserves source location
- `PDFLoader` extracts expected page count
- `MarkdownExporter` creates expected text

### Component Verification

Each subsystem shall be tested using controlled sample documents.

Examples:

- ingestion tests with simple PDFs
- layout tests with two-column PDFs
- table tests with generated table PDFs
- chunking tests with heading-based documents

### System Verification

The full pipeline shall be tested end-to-end:

```text
PDF input → Document model → JSON output → Markdown output → chunks
```

### Validation

Validation shall be performed using representative technical documents from aviation, aerospace, engineering, and standards contexts where legally permitted.

---

## 15. Initial Development Phases

### Phase 0 — Repository Setup

Objective: create a clean Python project foundation.

Deliverables:

- Git repository
- project structure
- `pyproject.toml`
- README
- TODO
- PROJECTPLAN
- basic test setup
- formatting and linting tools

### Phase 1 — Core Data Model

Objective: define the internal representation.

Deliverables:

- `Document`
- `Page`
- `Block`
- `SourceLocation`
- `BoundingBox`
- JSON serialization
- model unit tests

### Phase 2 — Basic PDF Ingestion

Objective: load native-text PDFs and extract pages and blocks.

Deliverables:

- PyMuPDF-based loader
- page extraction
- text extraction
- bounding box extraction
- metadata extraction
- ingestion tests

### Phase 3 — Exporters

Objective: make parsed output usable.

Deliverables:

- JSON exporter
- Markdown exporter
- basic CLI
- example usage

### Phase 4 — Layout and Structure

Objective: improve document understanding.

Deliverables:

- reading order detection
- heading detection
- paragraph grouping
- simple table detection
- formula candidate detection

### Phase 5 — RAG Chunking

Objective: produce RAG-ready content.

Deliverables:

- chunk model
- section-aware chunking
- source-preserving chunks
- vector payload exporter

### Phase 6 — Validation and Quality

Objective: estimate parsing quality and detect issues.

Deliverables:

- validation checks
- confidence indicators
- low-confidence flags
- parsing quality report

---

## 16. Recommended Technology Stack

Initial stack:

- Python 3.11+
- PyMuPDF for native PDF extraction
- Pydantic for data models or dataclasses for lightweight core models
- pytest for tests
- ruff for linting and formatting
- mypy or pyright for type checking
- typer for CLI
- rich for CLI output

Possible future tools:

- pdfplumber
- Camelot
- OCR engines
- LayoutParser
- OpenCV
- LLM-based cleanup modules
- Pandas for table normalization

---

## 17. Repository Naming Suggestion

Recommended repository name:

```text
techdoc-parser
```

Recommended Python package name:

```text
techdoc_parser
```

Reason:

- clear
- short
- domain-neutral
- not limited only to aviation
- compatible with Python naming conventions
- suitable for future open-source release

---

## 18. Suggested Git Repository Setup

### Create project folder

```bash
mkdir techdoc-parser
cd techdoc-parser
```

### Initialize Git

```bash
git init
```

### Create Python environment

Using `venv`:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Create initial folders

```bash
mkdir -p src/techdoc_parser
mkdir -p tests
mkdir -p docs
mkdir -p examples
```

### Create initial files

```bash
touch README.md TODO.md PROJECTPLAN.md pyproject.toml .gitignore
```

### Suggested initial `.gitignore`

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/
dist/
build/
*.egg-info/
.env
.DS_Store
.vscode/
.idea/
```

### First commit

```bash
git add .
git commit -m "Initial project structure"
```

### Create GitHub repository

Option A: using GitHub CLI:

```bash
gh repo create techdoc-parser --private --source=. --remote=origin --push
```

Option B: create the repository manually on GitHub, then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/techdoc-parser.git
git branch -M main
git push -u origin main
```

---

## 19. Suggested First Codex Prompt

Use this prompt after creating the empty repository:

```text
You are helping me build a Python library called techdoc-parser.

Create the initial Python project structure using a src layout.

Requirements:
- Use Python 3.11+
- Create package directory src/techdoc_parser
- Create tests directory
- Create docs and examples directories
- Create pyproject.toml
- Configure pytest
- Configure ruff
- Configure mypy or pyright if appropriate
- Add a minimal README.md
- Add a .gitignore
- Add src/techdoc_parser/__init__.py
- Add a very simple placeholder function parse_document(path: str)
- Add one unit test that imports the package and verifies the placeholder function exists

Do not implement PDF parsing yet.
Focus only on clean project foundation.
```

---

## 20. Suggested Second Codex Prompt

After the first foundation is working:

```text
Now implement the initial core data models for techdoc-parser.

Create models for:
- BoundingBox
- SourceLocation
- TextBlock
- Page
- DocumentMetadata
- Document

Requirements:
- Use dataclasses or Pydantic, whichever better fits a lightweight library foundation
- Every extracted object must preserve source traceability
- Add JSON serialization support
- Add unit tests for model creation and serialization
- Keep the code simple, typed, and well documented
- Do not implement PDF loading yet
```

---

## 21. Suggested Third Codex Prompt

```text
Implement the first PDF ingestion capability for techdoc-parser.

Requirements:
- Use PyMuPDF as the initial backend
- Create an ingestion module
- Create a PDFLoader class
- Load a native-text PDF
- Extract document metadata
- Extract pages
- Extract text blocks
- Preserve page number
- Preserve bounding boxes when available
- Return the existing Document model
- Add unit tests using a small generated PDF fixture
- Do not implement advanced layout analysis yet
```

---

## 22. Management Workflow

Recommended workflow for this project:

1. Define the next small engineering objective.
2. Convert it into a precise Codex prompt.
3. Let Codex implement locally.
4. Run tests.
5. Review results.
6. Commit small increments.
7. Update TODO and project plan.
8. Repeat.

Each development cycle should produce a small, testable, commit-worthy result.

---

## 23. Initial Definition of Done

A feature is considered done when:

- code is implemented
- tests are added
- tests pass
- public API is typed
- source traceability is preserved where applicable
- documentation or example is updated if user-facing
- changes are committed to Git

---

## 24. Immediate Next Step

Start with repository setup and project foundation only.

Do not begin PDF parsing until the package structure, testing tools, and core project configuration are stable.
