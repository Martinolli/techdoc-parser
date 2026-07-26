# D.7a Engineering OCR Fidelity Review Plan

## Scope

This plan covers D.7a-1 automated evaluation and review-package preparation for
`Wing_Design_Chapter_7.pdf`. D.7a-2 owner review is not performed by Codex.

## Required Command

```powershell
python tools/evaluation/run-engineering-ocr-fidelity.py `
  --source input/Wing_Design_Chapter_7.pdf `
  --expected-pages 43 `
  --report-json output/evaluation/engineering_ocr_fidelity/d7a_report.json `
  --report-markdown output/evaluation/engineering_ocr_fidelity/d7a_report.md `
  --allow-report-write `
  --strict
```

If approved OCR text artifacts exist, add:

```powershell
  --native-text-artifact <native-baseline-json-or-dir> `
  --ocr-text-artifact <ocr-candidate-json-or-dir> `
  --output-dir output/evaluation/engineering_ocr_fidelity/review_package `
  --allow-local-write
```

## Owner Checklist Fields

- `text_complete`
- `reading_order_correct`
- `greek_symbols_preserved`
- `math_symbols_preserved`
- `formulas_preserved`
- `tables_usable`
- `figures_captions_preserved`
- `page_provenance_correct`
- `fabricated_content_absent`

Each field starts as `pending`. Valid values are `pass`, `review`, `fail`,
`not_applicable`, and `pending`.

## Expected Current Result

The current expected result is `BLOCKED` with
`NO_SUPPORTED_OCR_EXECUTION_PATH`, because the parser has no documented OCR
runner. This is a capability gap, not a failed OCR-fidelity claim.

## D.7b-1 OCR Capability Inventory

D.7b-1 completed a read-only OCR capability and environment inventory. The
capability outcome is `ENGINE_INSTALLED_BUT_NOT_INTEGRATED`: Tesseract is
available locally, with `eng` and `osd` language/model identifiers reported, but
`ell` was not reported and the repository has no supported OCR execution
adapter.

Engine candidates:

| Engine | Available | Adapter | Candidate status |
| --- | --- | --- | --- |
| tesseract | true | false | AVAILABLE_NOT_INTEGRATED |

Blocking gaps:

- `OCR_ENGINE_NOT_INTEGRATED`
- `FORCED_OCR_NOT_SUPPORTED`
- `SELECTIVE_PAGE_OCR_NOT_SUPPORTED`
- `OCR_PAGE_PROVENANCE_NOT_RECORDED`
- `OCR_PROCESSED_PAGES_NOT_RECORDED`
- `OCR_MANIFEST_METADATA_MISSING`
- `RAW_OCR_OUTPUT_NOT_PRESERVED`
- `OCR_NORMALIZATION_NOT_SEPARATED`
- `GREEK_LANGUAGE_MODEL_UNAVAILABLE`
- `DETERMINISTIC_OCR_CONFIGURATION_UNDEFINED`

Recommended next action: `IMPLEMENT_ADAPTER_FOR_INSTALLED_ENGINE`.

D.7a remains blocked until a supported execution path can record engine
identity, version, mode, language/model selection, processed pages, page
provenance, and OCR manifest metadata.

## Exclusions

- No source PDF edits, copies, or commits.
- No OCR implementation or dependency installation.
- No AviationRAG source changes or test execution.
- No embeddings, AstraDB, FAISS, retrieval, or ingestion changes.
- No final OCR-fidelity acceptance before completed owner review.
