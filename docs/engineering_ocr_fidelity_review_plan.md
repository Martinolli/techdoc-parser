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

If an approved controlled OCR artifact exists, add it as the supplied OCR
artifact:

```powershell
  --native-text-artifact <native-baseline-json-or-dir> `
  --ocr-text-artifact output/evaluation/controlled_ocr/<run-id>/ocr_document.json `
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

Without a supplied OCR artifact, the expected result remains `BLOCKED` with
`NO_SUPPORTED_OCR_EXECUTION_PATH`. With an approved D.7b-2 controlled OCR
artifact, D.7a can compare supplied text, but the expected disposition remains
`OWNER_REVIEW_REQUIRED` until owner checklist evidence is completed.

## D.7b-1 and D.7b-2 OCR Capability Status

D.7b-1 completed a read-only OCR capability and environment inventory. D.7b-2
adds an explicit controlled adapter for the installed local Tesseract CLI.
Tesseract is available locally, with `eng` and `osd` language/model identifiers
reported. `ell` was not reported and remains a limitation.

Engine candidates:

| Engine | Available | Adapter | Candidate status |
| --- | --- | --- | --- |
| tesseract | true | true | SUPPORTED_AND_AVAILABLE for explicit `eng` OCR, with limitations |

Implemented by D.7b-2:

- explicit OCR opt-in
- full-page OCR mode
- selected-page OCR mode
- processed and failed page lists
- raw OCR output preservation
- normalized OCR output separation
- per-page provenance
- OCR manifest metadata

Remaining limitations:

- `GREEK_LANGUAGE_MODEL_UNAVAILABLE`
- `GREEK_FIDELITY_NOT_ESTABLISHED`
- `MATHEMATICAL_FIDELITY_NOT_ESTABLISHED`
- `OWNER_REVIEW_REQUIRED_FOR_FIDELITY_ACCEPTANCE`

Recommended next action: use the controlled adapter only for explicit approved
artifacts, then run D.7a comparison and owner review.

## Exclusions

- No source PDF edits, copies, or commits.
- No default parser OCR implementation or dependency installation.
- No AviationRAG source changes or test execution.
- No embeddings, AstraDB, FAISS, retrieval, or ingestion changes.
- No final OCR-fidelity acceptance before completed owner review.
