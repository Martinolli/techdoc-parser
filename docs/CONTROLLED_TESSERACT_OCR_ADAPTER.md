# Controlled Tesseract OCR Adapter

## Purpose

D.7b-2 adds an explicit, controlled OCR execution path for synthetic or
separately approved local sources. It uses PyMuPDF page rendering and the local
Tesseract CLI. It does not change default parser extraction, parser CLI
behavior, StructuredDocument schema, current parser manifests, AviationRAG,
embeddings, Astra, or FAISS.

## Execution Boundary

OCR runs only through:

```powershell
python tools/ocr/run-controlled-tesseract-ocr.py `
  --source <approved-or-synthetic-pdf> `
  --document-id <portable-id> `
  --mode ocr_all_pages `
  --language eng `
  --dpi 300 `
  --psm 6 `
  --oem 1 `
  --output-dir output/evaluation/controlled_ocr/<run-id> `
  --allow-output-write `
  --strict
```

The default `techdoc-parse` command is unchanged. The adapter does not process
any document unless this tool is invoked directly.

## Supported Modes

| Mode | Status |
| --- | --- |
| `ocr_all_pages` | Supported for explicit full-document OCR. |
| `ocr_selected_pages` | Supported with one-based `--pages` values. |
| `auto_when_native_text_missing` | Intentionally rejected with `AUTO_OCR_POLICY_UNDEFINED`. |

## Language Policy

Requested languages are validated against `tesseract --list-langs` before page
rendering. If a requested language is unavailable, the run fails with
`REQUESTED_OCR_LANGUAGE_UNAVAILABLE`. The adapter does not silently fall back
from `eng+ell` to `eng`.

The local environment reports `eng` and `osd`; `ell` is not available. This is
recorded as `GREEK_LANGUAGE_MODEL_UNAVAILABLE`. Greek symbol fidelity and
mathematical expression fidelity remain unestablished until owner review.

## Artifact Contract

The writer is gated by `--allow-output-write` and writes:

- `ocr_document.json`
- `ocr_manifest.json`
- `pages/page_###/raw_ocr.txt`
- `pages/page_###/normalized_ocr.txt`
- `pages/page_###/provenance.json`
- `pages/page_###/rendered_page.png` only when `--preserve-rendered-pages` is set

`ocr_document.json` uses `schema_name: techdoc-ocr-document` and
`schema_version: 0.1.0`. `ocr_manifest.json` uses
`schema_name: techdoc-ocr-manifest` and `schema_version: 0.1.0`.

Raw OCR text and normalized OCR text remain separate. The document artifact also
includes `text` and `ocr_text` aliases for the normalized page text so the D.7a
supplied-artifact loader can compare the output without running OCR.

## Provenance

Per-page provenance records:

- source filename, SHA-256, size, and observed page count
- one-based page number and zero-based PDF page index
- rendered page image SHA-256
- raw OCR text SHA-256
- normalized OCR text SHA-256
- rendering engine and DPI
- OCR engine, version, languages, mode, `psm`, and `oem`
- page status, warnings, errors, and sanitized stderr excerpt

Committed artifacts and sanitized reports do not include absolute executable
paths, output directories, source document paths, timestamps, environment
values, or source content from real user documents.

## D.7a Relationship

D.7a still does not run OCR. It can consume the controlled OCR document artifact
as an explicitly supplied OCR text artifact. Owner review remains required
before any final OCR-fidelity `PASS`, `FAIL`, or accepted-limitation claim.

## Limitations

- `ell` is unavailable locally.
- OCR fidelity is not established by adapter execution alone.
- Greek-symbol fidelity is not established.
- Mathematical expression fidelity is not established.
- Real user documents were not processed during D.7b-2 implementation.
- No software, packages, PATH entries, registry settings, or language packs were
  installed or changed.
