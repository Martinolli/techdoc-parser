# Engineering OCR Fidelity Evaluation Policy

## Purpose

D.7a adds a controlled, parser-side evaluation path for engineering OCR
fidelity. It is report-only. It does not modify parser extraction, source PDFs,
OCR implementation, normalization, reading order, chunking, StructuredDocument
output, AviationRAG, embeddings, vector stores, or downstream retrieval.

## Policy Identity

- `evaluation_scope`: `controlled_engineering_ocr_fidelity`
- `policy_name`: `engineering-ocr-fidelity`
- `policy_version`: `0.1`
- Expected local source: `Wing_Design_Chapter_7.pdf`
- Expected pages: `43`

## Execution Rules

- The evaluator does not run OCR.
- The evaluator may compare supplied native-text and OCR-text artifacts.
- If no supported parser OCR execution path or supplied OCR artifact exists, the
  result is `BLOCKED`.
- If automated comparison runs but owner review is pending, the result is
  `OWNER_REVIEW_REQUIRED`.
- `PASS`, `FAIL`, or `ACCEPTED_WITH_LIMITATIONS` require explicit completed
  owner review evidence.
- Before D.7a OCR execution, the OCR engine identity, engine version, OCR mode,
  language/model selection, processed pages, per-page failures, page provenance,
  and manifest metadata must be recorded.

## Evidence Model

Page evidence records include:

- source page image reference
- native text baseline reference
- OCR text candidate reference
- formula, symbol, table, and figure signal counts
- reading-order warnings
- symbol normalization and substitution warnings
- page provenance
- owner checklist status
- automated and final page outcomes

Sanitized aggregate reports must not include extracted source text, rendered
page images, formulas, table contents, absolute paths, or proprietary procedure
wording. Local review packages can be written only with explicit
`--allow-local-write`.

## Current Capability Finding

`techdoc-parser` currently supports native PDF text extraction and flags pages
that require OCR. It does not expose a documented parser OCR runner or CLI path.
D.7b-1 found a local Tesseract executable and PyMuPDF rendering capability, but
no repository OCR execution adapter or OCR manifest/provenance integration.
D.7a therefore records `NO_SUPPORTED_OCR_EXECUTION_PATH` until an approved OCR
capability is added in a separate authorized phase.
