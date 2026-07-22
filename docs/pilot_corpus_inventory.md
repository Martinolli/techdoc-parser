# Approved Pilot-Corpus Inventory

Phase 13I-b1 records a read-only inventory of the locally approved pilot PDF
corpus and proposes representative pages for later owner review.

This is inventory and planning only. Source accuracy was not evaluated, OCR was
not run, PDFs were not modified, source text and images were not committed, and
AviationRAG was not modified.

## Scope

Included:

- Local PDFs already placed by the user under ignored `input/`.
- Metadata-only PDF identity checks: filename, page count, size, access status,
  Git ignore status, duplicate-file detection, outline presence, page-label
  presence, page geometry, text-mode classification, layout heuristics, and
  proposed representative page numbers.
- JSON and Markdown report serialization to ignored `output/` only when
  `--allow-report-write` is passed.

Excluded:

- PDF edits, moves, renames, deletion, staging, or commits.
- Full source text, extracted images, OCR output, or long excerpts.
- Source accuracy evaluation.
- Parser repair or parser behavior changes.
- Extraction, chunking, current JSON/Markdown/manifest output changes, or
  StructuredDocument output changes.
- Dependencies, external APIs, web calls, LLM document analysis, embeddings,
  vector databases, or AviationRAG modifications.

## CLI

List the local corpus without writing reports:

```powershell
python tools/evaluation/run-pilot-corpus-inventory.py `
  --input-dir input `
  --list-documents
```

Write local reports only when explicitly allowed:

```powershell
python tools/evaluation/run-pilot-corpus-inventory.py `
  --input-dir input `
  --report-json output/pilot_corpus_inventory.json `
  --report-markdown output/pilot_corpus_inventory.md `
  --allow-report-write
```

CLI exit codes:

| Outcome | Exit code |
| --- | ---: |
| `PASS` | 0 |
| `REVIEW` | 2 |
| `FAIL` | 1 |

`--strict` maps `REVIEW` to exit code `1` for review-gated automation.

## Local Inventory Summary

The local Phase 13I-b1 run found 8 PDFs, 2,937 total pages, 0 duplicate hash
groups, 0 tracked PDFs, 8 Git-ignored PDFs, and 0 access errors. The local
outcome was `REVIEW` because one document has an uncertain native/scanned
classification.

| Filename | Pages | Size MiB | Text mode | Access | Outline | Labels | Review burden |
| --- | ---: | ---: | --- | --- | --- | --- | --- |
| `Aircraft_System_Safety_Military_Civil_Aeronautical_Applications.pdf` | 367 | 2.012 | `native_text` | `readable` | yes | yes | high |
| `Airplane_Maintenance_Manual_CIRRUS_Design_SR22.pdf` | 1082 | 8.477 | `uncertain` | `readable` | yes | no | high |
| `Airworthiness_An_Introduction_Aircraft_Certification_And_Operations.pdf` | 524 | 14.469 | `native_text` | `readable` | yes | no | high |
| `FAA_Order_4040_26B.pdf` | 39 | 0.340 | `native_text` | `readable` | yes | no | medium |
| `Flight_Test_RM_AG_300_V32.pdf` | 210 | 7.916 | `native_text` | `readable` | yes | no | high |
| `Introduction_Aircraft_Stability_And_Control_Course_Notes_M&AE_5070.pdf` | 153 | 2.048 | `native_text` | `readable` | no | no | high |
| `Introduction_Flight_Test_Engineering_RTO-AGARDograph_300_V14.pdf` | 456 | 6.488 | `native_text` | `readable` | yes | no | high |
| `MIL-STD-882E.pdf` | 106 | 1.354 | `native_text` | `readable` | yes | no | high |

## Corpus Integrity

| Check | Local result |
| --- | --- |
| Expected PDF count | 8 |
| Found PDF count | 8 |
| Git-ignored PDFs | 8 |
| Git-tracked PDFs | 0 |
| Duplicate hash groups | 0 |
| Missing expected documents | 0 |
| Unexpected documents | 0 |
| Access errors | 0 |
| PDFs modified by inventory | no |
| OCR performed | no |
| Source accuracy evaluated | no |
| AviationRAG modified | no |

Exact SHA-256 values are written only to ignored local reports under `output/`
for owner-side verification. They are intentionally not committed in this
documentation.

## Document Characteristics

| Filename | Dominant orientation | Layout signals |
| --- | --- | --- |
| `Aircraft_System_Safety_Military_Civil_Aeronautical_Applications.pdf` | portrait | single-column, two-column, complex, rotated-page signals |
| `Airplane_Maintenance_Manual_CIRRUS_Design_SR22.pdf` | portrait | single-column, two-column, complex, uncertain-page signals |
| `Airworthiness_An_Introduction_Aircraft_Certification_And_Operations.pdf` | portrait | single-column, two-column, complex, rotated-page signals |
| `FAA_Order_4040_26B.pdf` | portrait | single-column, two-column, complex, rotated-page signals |
| `Flight_Test_RM_AG_300_V32.pdf` | portrait | single-column, two-column, complex, figure/table-page, scan-like-page signals |
| `Introduction_Aircraft_Stability_And_Control_Course_Notes_M&AE_5070.pdf` | portrait | single-column, two-column, complex signals |
| `Introduction_Flight_Test_Engineering_RTO-AGARDograph_300_V14.pdf` | portrait | single-column, two-column, complex, uncertain-page, scan-like-page signals |
| `MIL-STD-882E.pdf` | portrait | single-column, two-column, complex signals |

Heuristic content indicators found across the corpus include table-like pages,
figure-caption candidates, equation indicators, admonition indicators,
procedures, numbered clauses, cross-references, appendix or annex indicators,
multi-column reading-order candidates, rotated pages, dense pages, and low-text
pages.

## Review Finding

`Airplane_Maintenance_Manual_CIRRUS_Design_SR22.pdf` is classified as
`uncertain` by the metadata-only native/scanned heuristic and requires manual
owner review before any downstream accuracy pilot. This is not an OCR result
and does not evaluate document correctness.

## Recommended Next Step

Proceed to Phase 13I-b2 only after owner approval of the corpus inventory and
representative-page proposal. Phase 13I-b2 should remain a controlled
source-accuracy pilot and should not include parser repair, OCR, external APIs,
embeddings, vector databases, or AviationRAG runtime ingestion unless separately
approved.
