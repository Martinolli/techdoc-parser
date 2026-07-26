# techdoc-parser

Convert complex technical documents into structured, traceable, machine-usable knowledge while preserving source fidelity.

## Installation

For local development:

```bash
pip install -e ".[dev]"
```

## Basic Usage

```python
from techdoc_parser import parse_document
from techdoc_parser.exporters import export_document_json

document = parse_document("manual.pdf")
export_document_json(document, "output/manual.json")
```

Markdown export:

```python
from techdoc_parser import parse_document
from techdoc_parser.exporters import export_document_markdown

document = parse_document("manual.pdf")
export_document_markdown(document, "output/manual.md")
```

Markdown export is currently simple and text-block based.

## CLI Usage

```bash
techdoc-parse manual.pdf --output output/manual.json
```

## Full Output Package

Use the full output package command when preparing parser artifacts for downstream
inspection or RAG ingestion planning:

```bash
techdoc-parse input/FAA_Order_4040_26B.pdf \
  --output output/faa_order_4040_26b_document.json \
  --chunks-output output/faa_order_4040_26b_chunks.json \
  --validation-output output/faa_order_4040_26b_validation.json \
  --validation-gate-output output/faa_order_4040_26b_gate.json \
  --validation-summary-output output/faa_order_4040_26b_validation_summary.md \
  --manifest-output output/faa_order_4040_26b_manifest.json
```

PowerShell uses backticks for line continuation:

```powershell
techdoc-parse input/FAA_Order_4040_26B.pdf `
  --output output/faa_order_4040_26b_document.json `
  --chunks-output output/faa_order_4040_26b_chunks.json `
  --validation-output output/faa_order_4040_26b_validation.json `
  --validation-gate-output output/faa_order_4040_26b_gate.json `
  --validation-summary-output output/faa_order_4040_26b_validation_summary.md `
  --manifest-output output/faa_order_4040_26b_manifest.json
```

| Output | Purpose |
| --- | --- |
| `document.json` | Full structured parser output |
| `chunks.json` | RAG-oriented semantic chunks |
| `validation.json` | Machine-readable validation report |
| `gate.json` | PASS/REVIEW/FAIL ingestion decision |
| `validation_summary.md` | Human-readable validation summary |
| `manifest.json` | Package manifest for downstream systems |

Machine-readable JSON outputs include `schema_version`, `parser.name`, and
`parser.version`. Downstream systems should start from `manifest.json` because it
records the source document, generated output paths, parser/schema metadata, gate
decision, and basic metrics.

Gate decision meanings:

- `pass`: suitable for automated ingestion
- `review`: human review recommended before ingestion
- `fail`: should not be ingested automatically

For the detailed output contract audit, see
[`docs/output_contract_0_1_0_audit.md`](docs/output_contract_0_1_0_audit.md).

## Structured-Document Contract API

An optional contract API for `techdoc-structured-document / 0.1.0` is available
under `techdoc_parser.contracts` and `techdoc_parser.exporters`. It defines
schema constants, contract dataclasses, deterministic JSON serialization
helpers, a pure parser-model mapper, and a file exporter for explicit
structured-document artifacts. The mapper covers document, page, block,
source-location, bounding-box, heading-derived section hierarchy, current
table/figure-caption candidate evidence, conservative equation evidence,
explicit-label admonition evidence, and explicit textual cross-reference
evidence. Current placeholder confidence values are intentionally omitted.

CLI structured-document output is optional:

```powershell
techdoc-parse input/synthetic.pdf `
  --output output/document.json `
  --structured-document-output output/structured_document.json `
  --structured-document-id SYNTHETIC-DOC-001
```

Optional metadata flags are `--document-title`, `--document-number`,
`--document-revision`, `--document-issue`, and
`--document-effective-date`. Source SHA-256 is computed automatically from the
exact input file bytes and stored in the artifact. Existing JSON, Markdown,
validation, gate, and manifest outputs remain unchanged unless the new option
is explicitly supplied. No AviationRAG installation is required and direct
AviationRAG ingestion is not implemented.

## AviationRAG Compatibility Gate

An optional offline compatibility gate can validate a Phase 13G
structured-document artifact and manifest against a local AviationRAG checkout
through a subprocess adapter:

```powershell
python tools/compatibility/run-aviationrag-compatibility-gate.py `
  --artifact output/structured_document.json `
  --manifest output/manifest.json `
  --source input/synthetic.pdf `
  --aviationrag-root "C:\Users\Aspire5 15 i7 4G2050\ProjectRAG\AviationRAG" `
  --comparison-artifact output/structured_document_repeat.json
```

The gate is report-only and exits `0` for `PASS`, `2` for `REVIEW`, and `1`
for `FAIL`. Compatibility report writing is optional and requires
`--allow-report-write`. The gate does not import AviationRAG into parser
runtime modules, modify AviationRAG, run ingestion, generate embeddings, use
Astra, or use FAISS.

## Fixture Chunk Quality Evaluation

An offline fixture-only chunk-quality evaluator is available for current
semantic chunks:

```powershell
python tools/evaluation/run-chunk-quality-evaluation.py --all-cases
```

The evaluator uses existing committed synthetic fixtures only and reports
quality proxies for source-block coverage, ordering, section coherence,
provenance, chunk size, duplication/overlap, and explicit table, figure,
equation, admonition, and cross-reference source evidence. Fixture metrics are
quality proxies only; they do not prove source-page visual accuracy, OCR
accuracy, semantic accuracy, or real aviation-document accuracy. It does not
modify parser behavior, generate embeddings, call AviationRAG, use Astra or
FAISS, or call external APIs. Optional JSON/Markdown report files require
`--allow-report-write`.

## Approved Pilot-Corpus Inventory

Phase 13I-b1 adds a read-only approved-corpus inventory and representative-page
planning tool:

```powershell
python tools/evaluation/run-pilot-corpus-inventory.py `
  --input-dir input `
  --list-documents
```

Report files are optional, must be written under ignored `output/`, and require
`--allow-report-write`. The inventory records metadata-only planning signals
such as filename, page count, access status, Git ignore status, native/scanned
classification, outline/page-label presence, page geometry, and proposed
representative page numbers. It does not evaluate source accuracy, run OCR,
extract or commit source text/images, modify PDFs, repair parser behavior, call
external APIs, or modify AviationRAG.

## P0 Source-Accuracy Pilot

Phase 13I-b2 adds a controlled source-accuracy pilot for approved P0
representative pages only:

```powershell
python tools/evaluation/run-source-accuracy-pilot.py `
  --input-dir input `
  --plan tests/fixtures/pilot_corpus/p0_source_accuracy_plan.json `
  --all-p0
```

The pilot scores only the committed P0 page plan, supports optional ignored
local evidence output with `--allow-local-write`, and writes sanitized aggregate
JSON/Markdown reports only with `--allow-report-write`. It does not run OCR,
process P1/P2 pages, score full-document accuracy, modify PDFs, alter parser
behavior, change StructuredDocument output, call AviationRAG, use embeddings, or
call external APIs. The current local P0 run returned `FAIL`: 25 final `FAIL`
pages and 7 final `REVIEW` pages, with all human visual reviews still pending.
Phase 13I-c2E keeps that b2 result as historical policy-v1 evidence and adds a
separate corrected evaluator-policy v2 rerun. The corrected rerun is
`p0-source-accuracy / 2.0`, returns aggregate `REVIEW` with 32 final `REVIEW`
pages and no final `FAIL`, and still requires human visual review before any
page can receive final `PASS`.

Phase 13I-c3 adds owner visual-review and P0 acceptance tooling. Generate local
review pages with explicit write permission:

```powershell
python tools/evaluation/run-p0-visual-review.py `
  --input-dir input `
  --plan tests/fixtures/pilot_corpus/p0_source_accuracy_plan.json `
  --automated-report output/evaluation/source_accuracy_p0_c2e/source_accuracy_p0_policy_v2_run1.json `
  --evidence-dir output/evaluation/source_accuracy_p0_review `
  --all-p0 `
  --generate-review-package `
  --allow-local-write
```

Merge completed local checklists:

```powershell
python tools/evaluation/run-p0-visual-review.py `
  --plan tests/fixtures/pilot_corpus/p0_source_accuracy_plan.json `
  --automated-report output/evaluation/source_accuracy_p0_c2e/source_accuracy_p0_policy_v2_run1.json `
  --evidence-dir output/evaluation/source_accuracy_p0_review `
  --all-p0 `
  --merge-checklists
```

Visual review is required for pilot acceptance. No checklist is auto-approved,
and local review evidence remains ignored under `output/`.

Phase 13I-b3 formally closes the representative-page P0 pilot:

```text
P0 representative-page pilot: ACCEPTED_WITH_LIMITATIONS

32 pages reviewed
28 PASS
4 REVIEW
0 FAIL
```

Source PDFs remain local and ignored. Full-document accuracy was not
established. The next authorized work is downstream persisted `ChunkRecord`
mapping design and a controlled local sample-persistence dry run, not
production ingestion, embeddings, Astra rebuild, or FAISS rebuild.

Phase D.7a adds a controlled engineering OCR-fidelity evaluator for
`Wing_Design_Chapter_7.pdf`:

```powershell
python tools/evaluation/run-engineering-ocr-fidelity.py `
  --source input/Wing_Design_Chapter_7.pdf `
  --expected-pages 43 `
  --report-json output/evaluation/engineering_ocr_fidelity/d7a_report.json `
  --report-markdown output/evaluation/engineering_ocr_fidelity/d7a_report.md `
  --allow-report-write `
  --strict
```

The evaluator does not run OCR or implement OCR. It compares supplied
native/OCR text artifacts when available; otherwise it returns `BLOCKED` with
`NO_SUPPORTED_OCR_EXECUTION_PATH`. Owner review remains required before any
final OCR-fidelity `PASS`, `FAIL`, or accepted-limitation claim.

D.7a OCR fidelity framework: implemented. D.7b-1 capability inventory:
completed. OCR execution capability: `ENGINE_INSTALLED_BUT_NOT_INTEGRATED`
because Tesseract is available locally, but no supported repository OCR adapter,
forced-OCR mode, selective-page OCR mode, page-provenance recording, or OCR
manifest integration exists.

## P0 Failure Triage

Phase 13I-c1 adds diagnosis-only triage for selected P0 source-accuracy
failures:

```powershell
python tools/evaluation/run-p0-failure-triage.py `
  --input-dir input `
  --plan tests/fixtures/pilot_corpus/p0_failure_triage_plan.json `
  --all-cases `
  --output-dir output/evaluation/p0_failure_triage `
  --allow-local-write `
  --report-json output/evaluation/p0_failure_triage/p0_failure_triage_report.json `
  --report-markdown output/evaluation/p0_failure_triage/p0_failure_triage_report.md `
  --allow-report-write
```

The triage classifies selected b2 findings by pipeline stage and root cause.
It is report-only and does not change parser behavior, source PDFs, OCR,
reading order, normalization, structure detection, chunking,
StructuredDocument output, AviationRAG, embeddings, dependencies, or the
original Phase 13I-b2 results. Local full evidence remains ignored under
`output/evaluation/p0_failure_triage/`, and the CLI may return `REVIEW` while
visual confirmation is still pending. See
[`docs/p0_failure_root_cause_analysis.md`](docs/p0_failure_root_cause_analysis.md).

## Documentation

- [Architecture and pipeline overview](docs/architecture_pipeline_overview.md)
- [MVP readiness checklist](docs/mvp_readiness_checklist.md)
- [Output contract audit](docs/output_contract_0_1_0_audit.md)
- [Structured-document contract foundation](docs/structured_document_contract.md)
- [Structured-document parser mapping](docs/structured_document_mapping.md)
- [Structured-document section hierarchy](docs/structured_document_hierarchy.md)
- [Structured-document table and figure-caption mapping](docs/structured_document_tables_figures.md)
- [Structured-document equation and admonition mapping](docs/structured_document_equations_admonitions.md)
- [Structured-document cross-reference and confidence policy](docs/structured_document_references_confidence.md)
- [Structured-document export](docs/structured_document_export.md)
- [AviationRAG compatibility gate](docs/aviationrag_compatibility_gate.md)
- [Fixture chunk quality evaluation](docs/chunk_quality_evaluation.md)
- [Chunk quality fixture baseline](docs/chunk_quality_fixture_baseline.md)
- [Approved pilot-corpus inventory](docs/pilot_corpus_inventory.md)
- [Pilot representative-page proposal](docs/pilot_representative_page_plan.md)
- [Controlled P0 source-accuracy pilot framework](docs/source_accuracy_pilot_framework.md)
- [Source-accuracy evaluation policy v2](docs/source_accuracy_evaluation_policy_v2.md)
- [P0 source-accuracy pilot result](docs/p0_source_accuracy_pilot.md)
- [P0 failure root-cause analysis](docs/p0_failure_root_cause_analysis.md)
- [P0 visual review and acceptance](docs/p0_visual_review_and_acceptance.md)
- [P0 pilot final acceptance](docs/p0_pilot_final_acceptance.md)
- [Engineering OCR fidelity policy](docs/engineering_ocr_fidelity_policy.md)
- [D.7a engineering OCR fidelity review plan](docs/engineering_ocr_fidelity_review_plan.md)
- [Planned AviationRAG structured-document contract gap analysis](docs/aviationrag_structured_document_gap_analysis.md)

## Current Limitations

- Native-text PDFs are supported
- Scanned/OCR documents are detected, but OCR is not implemented
- Tables are candidate-level and partial; the internal structured-document
  mapper can expose existing table candidates as root entities, but it does
  not reconstruct rows, columns, or cells
- Figure support is caption-level; the internal structured-document mapper can
  expose existing caption candidates as root figure entities, but it does not
  extract image assets or understand visual regions
- Section hierarchy is available only in the internal structured-document
  mapper from current `HeadingBlock` evidence
- Formula discovery from PDF layout is future work; the internal
  structured-document mapper can expose existing `FormulaBlock` records and
  conservative paragraph equation evidence as root equation entities
- Admonition mapping is explicit-label only for warning, caution, note,
  important, and safety-notice text in the internal structured-document mapper
- Cross-reference mapping is explicit-text only in the internal
  structured-document mapper and preserves unresolved, external, ambiguous, and
  not-attempted statuses
- Confidence fields are omitted unless truthful numeric evidence exists; current
  placeholder `SourceLocation.confidence` values are not promoted
- `techdoc-structured-document / 0.1.0` has an optional API, CLI file export,
  checksum-backed output, manifest registration, and a formal offline
  AviationRAG compatibility gate
- Fixture chunk-quality evaluation is proxy-only and does not prove source-page,
  OCR, semantic, or real aviation-document accuracy
- Approved pilot-corpus inventory is planning-only and does not evaluate source
  accuracy, run OCR, or authorize downstream ingestion
- The controlled P0 representative-page pilot is accepted with limitations
  after owner visual review. It is report-only; it does not repair parser
  behavior, evaluate OCR, or prove full-document accuracy
- P0 failure triage is diagnosis-only. It identifies evaluator-policy defects,
  source-proxy limitations, expected multi-representation, layout limitations,
  and findings still requiring visual confirmation before any parser repair
