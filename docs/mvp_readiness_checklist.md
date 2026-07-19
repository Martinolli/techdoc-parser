# techdoc-parser MVP Readiness Checklist

## 1. Purpose

This document records the MVP readiness status of `techdoc-parser` before using
it as an ingestion parser for AviationRAG D.4c. It summarizes the current parser
baseline, required verification, known limitations, and intended handoff point
for controlled native-text PDF pilot ingestion.

## 2. MVP Baseline

The current MVP baseline includes:

- Native-text PDF ingestion
- Structured document JSON
- Semantic chunks JSON
- Validation report JSON
- Validation gate JSON
- Validation summary Markdown
- Output manifest JSON
- Schema/parser metadata
- Source traceability
- Section-aware chunk metadata

## 3. Required Output Package

The expected parser output package is:

- `document.json`
- `chunks.json`
- `validation.json`
- `gate.json`
- `validation_summary.md`
- `manifest.json`

Downstream systems should start from `manifest.json` because it records the
source document, generated artifact paths, parser/schema metadata, gate decision,
and basic metrics.

## 4. Final Verification Command

Bash:

```bash
techdoc-parse input/FAA_Order_4040_26B.pdf \
  --output output/faa_order_4040_26b_document.json \
  --chunks-output output/faa_order_4040_26b_chunks.json \
  --validation-output output/faa_order_4040_26b_validation.json \
  --validation-gate-output output/faa_order_4040_26b_gate.json \
  --validation-summary-output output/faa_order_4040_26b_validation_summary.md \
  --manifest-output output/faa_order_4040_26b_manifest.json
```

PowerShell:

```powershell
techdoc-parse input\FAA_Order_4040_26B.pdf `
  --output output\faa_order_4040_26b_document.json `
  --chunks-output output\faa_order_4040_26b_chunks.json `
  --validation-output output\faa_order_4040_26b_validation.json `
  --validation-gate-output output\faa_order_4040_26b_gate.json `
  --validation-summary-output output\faa_order_4040_26b_validation_summary.md `
  --manifest-output output\faa_order_4040_26b_manifest.json
```

## 5. Expected Gate Result

The current FAA test package is expected to produce:

- `decision.status = pass`
- `decision.can_ingest = true`
- `error_count = 0`
- `warning_count = 0`

Info-level findings are acceptable and do not block ingestion.

## 6. Verification Checklist

- [ ] `pytest` passes
- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes
- [ ] `mypy src` passes
- [ ] Full FAA output package generated
- [ ] `manifest.json` created
- [ ] `manifest.json` contains `schema_version`
- [ ] `manifest.json` contains `parser.name` and `parser.version`
- [ ] `manifest.json` contains output artifact paths
- [ ] Gate decision is `pass`
- [ ] `chunks.json` exists
- [ ] Chunks preserve source references
- [ ] `validation_summary.md` is readable
- [ ] README links to relevant documentation
- [ ] `docs/output_contract_0_1_0_audit.md` exists
- [ ] `docs/architecture_pipeline_overview.md` exists

## 7. Known MVP Limitations

- Native-text PDFs only.
- OCR is detected but not performed.
- Table extraction is candidate-level and partial.
- Full row/column reconstruction is not solved.
- Figure support is caption-level only.
- `FormulaBlock` model exists, but formula detection is not implemented.
- Full section hierarchy is not implemented.
- Confidence scoring is not implemented as a dedicated model.
- Cross-reference graph is not implemented.
- Multi-column layout handling is not implemented.

## 8. AviationRAG Handoff Contract

AviationRAG should:

- Read `manifest.json` first
- Verify `schema_version`
- Verify `parser.name` and `parser.version`
- Check `decision.status` and `decision.can_ingest`
- Ingest `chunks.json` only when allowed
- Retain `document.json` for traceability and debugging
- Retain `validation_summary.md` for human review

## 9. Recommended Tag

Suggested optional git tag:

```text
v0.1.0-mvp
```

Create this tag only after final verification has been run and the FAA gate
result is confirmed.

## 10. Conclusion

`techdoc-parser` is MVP-ready for controlled native-text PDF pilot ingestion into
AviationRAG, with known limitations documented and release verification captured
in this checklist.
