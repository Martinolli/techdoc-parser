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

## Exclusions

- No source PDF edits, copies, or commits.
- No OCR implementation or dependency installation.
- No AviationRAG source changes or test execution.
- No embeddings, AstraDB, FAISS, retrieval, or ingestion changes.
- No final OCR-fidelity acceptance before completed owner review.
