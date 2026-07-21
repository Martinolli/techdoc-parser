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

An isolated internal contract API for `techdoc-structured-document / 0.1.0` is
available under `techdoc_parser.contracts`. It defines schema constants,
contract dataclasses, deterministic JSON serialization helpers, and a pure
parser-model mapper for document, page, block, source-location, bounding-box,
and heading-derived section hierarchy data already present in the current
parser model.

This API is not wired into the CLI or current output package. Existing JSON,
Markdown, validation, gate, and manifest outputs remain unchanged.

## Documentation

- [Architecture and pipeline overview](docs/architecture_pipeline_overview.md)
- [MVP readiness checklist](docs/mvp_readiness_checklist.md)
- [Output contract audit](docs/output_contract_0_1_0_audit.md)
- [Structured-document contract foundation](docs/structured_document_contract.md)
- [Structured-document parser mapping](docs/structured_document_mapping.md)
- [Structured-document section hierarchy](docs/structured_document_hierarchy.md)
- [Planned AviationRAG structured-document contract gap analysis](docs/aviationrag_structured_document_gap_analysis.md)

## Current Limitations

- Native-text PDFs are supported
- Scanned/OCR documents are detected, but OCR is not implemented
- Tables are candidate-level and partial
- Section hierarchy is available only in the internal structured-document
  mapper from current `HeadingBlock` evidence
- Formula recognition is future work
- `techdoc-structured-document / 0.1.0` has an internal contract API and
  parser-model mapper, but CLI export and manifest integration are not
  implemented
