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
- The evaluator may compare supplied native-text and OCR-text artifacts,
  including a D.7b-2 `techdoc-ocr-document / 0.1.0` artifact.
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
that require OCR. D.7b-2 adds a separate explicit controlled Tesseract adapter
that can produce supplied OCR artifacts for D.7a comparison. The evaluator still
does not run OCR, the default parser path is unchanged, and owner review remains
required before any final OCR-fidelity `PASS`, `FAIL`, or
`ACCEPTED_WITH_LIMITATIONS` claim.

The local environment does not report the Tesseract `ell` language model. The
adapter fails rather than falling back when a requested language is unavailable.
Greek-symbol and mathematical-expression fidelity remain limitations until
review evidence proves otherwise.
