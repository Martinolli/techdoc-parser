# Controlled P0 Source-Accuracy Pilot Framework

Phase 13I-b2 adds a report-only source-accuracy pilot for owner-approved P0
representative pages from the local ignored pilot corpus.

## Scope

- Scope field: `source_accuracy_scope: representative_p0_pages`.
- Plan: `tests/fixtures/pilot_corpus/p0_source_accuracy_plan.json`.
- Input corpus location: ignored local `input/`.
- Local full evidence location: ignored `output/evaluation/source_accuracy_p0/`.
- Sanitized aggregate reports may be written only with `--allow-report-write`.
- Local evidence packages may be written only with `--allow-local-write`.

The committed plan contains 32 P0 pages across the 8 approved local PDFs. It
stores document keys, source PDF basenames, one-based page numbers, zero-based
PDF page indexes, evaluation roles, and approval status. It does not store
source hashes, absolute paths, extracted source text, rendered pages, table
contents, equations, proprietary procedures, or images.

## What Is Measured

The evaluator compares each approved P0 page against an automated source proxy
from PyMuPDF native-text/page metadata and the current parser output. Metrics
include:

- Raw character coverage and normalized line coverage.
- Missing line count, duplicate line count, and Unicode symbol loss count.
- Coordinate-order inversion signals for reading order.
- Page provenance consistency.
- Section parent integrity.
- Candidate table, figure-caption, equation, admonition, and cross-reference
  evidence counts.
- Chunk source-block coverage and section-coherence review signals.
- SR22 native-text classification for the approved SR22 P0 pages.

Human visual review is represented by a per-page checklist. The default
checklist is pending, so final `PASS` is not allowed until completed visual
checks are supplied and pass. Table-cell accuracy and figure visual-content
accuracy remain explicitly `not_measurable`.

## Commands

List approved P0 pages:

```powershell
python tools/evaluation/run-source-accuracy-pilot.py `
  --input-dir input `
  --plan tests/fixtures/pilot_corpus/p0_source_accuracy_plan.json `
  --list-pages
```

Run the approved P0 pilot and write ignored local evidence:

```powershell
python tools/evaluation/run-source-accuracy-pilot.py `
  --input-dir input `
  --plan tests/fixtures/pilot_corpus/p0_source_accuracy_plan.json `
  --all-p0 `
  --output-dir output/evaluation/source_accuracy_p0 `
  --allow-local-write `
  --report-json output/evaluation/source_accuracy_p0/source_accuracy_p0_report.json `
  --report-markdown output/evaluation/source_accuracy_p0/source_accuracy_p0_report.md `
  --allow-report-write
```

The source-accuracy CLI exits `0` for `PASS`, `2` for `REVIEW`, and `1` for
`FAIL`. A failing report is still useful evidence; it is not a parser repair
step.

## Non-Goals

Phase 13I-b2 does not:

- Modify, rename, move, delete, stage, or commit PDFs.
- Process P1/P2 representative pages or score all corpus pages.
- Run OCR or evaluate OCR accuracy.
- Change extraction, reading order, block creation, structure detection,
  chunking, StructuredDocument output, existing CLI behavior, dependencies, or
  `pyproject.toml`.
- Use embeddings, LLM evaluation, external APIs, web access, Astra, FAISS, or
  AviationRAG.
- Commit rendered images, extracted source text, proprietary procedures, table
  contents, equations, source hashes, or full local evidence packages.

The current implementation may parse a full PDF operationally because the
existing parser loader does not provide a page-selection API. Only approved P0
pages are scored, and the aggregate report records
`full_document_accuracy_evaluated: false`.
