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
  AviationRAG compatibility gate, but parser accuracy pilots remain future work
