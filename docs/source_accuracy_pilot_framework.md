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

## Failure Triage Process

Phase 13I-c1 adds diagnosis-only triage for selected Phase 13I-b2 P0 failures.
The triage process starts from the committed P0 page plan and a separate
sanitized triage plan. It does not change parser output, evaluator policy,
source PDFs, local evidence, chunking, StructuredDocument mapping, or the
original Phase 13I-b2 result.

The triage taxonomy is:

- `CONFIRMED_PARSER_DEFECT`
- `EVALUATION_FRAMEWORK_DEFECT`
- `SOURCE_PROXY_LIMITATION`
- `EXPECTED_MULTI_REPRESENTATION`
- `DOCUMENT_LAYOUT_LIMITATION`
- `NEEDS_VISUAL_CONFIRMATION`

For each selected page, diagnostics isolate where the evidence first appears:
source proxy, raw parser blocks, ordered semantic blocks, normalized blocks,
structured entities, semantic chunks, source-accuracy evaluator assumptions, or
human visual review. Local full evidence can be written only with
`--allow-local-write` under ignored `output/evaluation/p0_failure_triage/`.
Sanitized JSON/Markdown reports require `--allow-report-write`.

Corrective phases must target the isolated stage only. Any evaluator-policy
correction must rerun the triage subset and the original 32-page P0 pilot
without rewriting the b2 baseline. Parser changes are not justified by triage
findings classified as source-proxy limitations, expected multi-representation,
document-layout limitations, or pending visual confirmation.

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
