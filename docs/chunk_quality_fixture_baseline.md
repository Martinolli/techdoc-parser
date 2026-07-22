# Chunk Quality Fixture Baseline

This document summarizes the committed Phase 13I fixture-only chunk-quality
baseline.

Fixture metrics are quality proxies only; they do not prove source-page visual
accuracy, OCR accuracy, semantic accuracy, or real aviation-document accuracy.

## Registry

Registry file:

```text
tests/fixtures/chunk_quality/evaluation_cases.json
```

Committed expected baseline:

```text
tests/fixtures/chunk_quality/expected_chunk_quality_baseline.json
```

Registered cases:

| Case | Existing fixture |
| --- | --- |
| `basic_structured_mapping` | `tests/fixtures/structured_document/mapped_structured_document.json` |
| `section_hierarchy` | `tests/fixtures/structured_document/mapped_structured_document_with_sections.json` |
| `tables_figures` | `tests/fixtures/structured_document/mapped_structured_document_with_tables_figures.json` |
| `equations_admonitions` | `tests/fixtures/structured_document/mapped_structured_document_with_equations_admonitions.json` |
| `references_confidence` | `tests/fixtures/structured_document/mapped_structured_document_with_references_confidence.json` |

## Baseline Result

Current aggregate outcome: `REVIEW`.

| Case | Outcome | Notes |
| --- | --- | --- |
| `basic_structured_mapping` | `REVIEW` | Semantic block coverage passes; source checksum provenance is not measurable. |
| `section_hierarchy` | `REVIEW` | Section and ordering proxies pass; source checksum provenance is not measurable. |
| `tables_figures` | `REVIEW` | Table and figure-caption source evidence is represented; source checksum provenance is not measurable. |
| `equations_admonitions` | `REVIEW` | Equation and admonition source evidence is represented; source checksum provenance is not measurable. |
| `references_confidence` | `REVIEW` | Cross-reference source evidence is represented; source checksum provenance is not measurable. |

The baseline intentionally treats `not_measurable` visual/table-cell/source
accuracy metrics as review signals. This keeps fixture evaluation honest while
preventing it from being mistaken for a real source-accuracy pilot.

## Reproduction Commands

```powershell
python tools/evaluation/run-chunk-quality-evaluation.py --list-cases
python tools/evaluation/run-chunk-quality-evaluation.py --all-cases
```

Optional local report generation:

```powershell
python tools/evaluation/run-chunk-quality-evaluation.py `
  --all-cases `
  --report-json output/evaluation/chunk_quality_report.json `
  --report-markdown output/evaluation/chunk_quality_report.md `
  --allow-report-write
```

Generated files under `output/` are local artifacts and should not be committed.
