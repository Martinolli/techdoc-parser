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

## Evaluation Policy v2

The current source-accuracy evaluator uses:

- `evaluation_policy_name`: `p0-source-accuracy`
- `evaluation_policy_version`: `2.0`
- `run_type`: `corrected_evaluator_rerun`
- `supersedes_policy_interpretation`: `1`

Policy v1 remains the historical interpretation for the Phase 13I-b2 baseline.
The b2 result must not be rewritten: 25 final `FAIL`, 7 final `REVIEW`, 0 final
`PASS`.

Policy v2 applies these evaluator-only rules:

- Raw character coverage is independent from duplicate-line findings.
- Missing source lines and parser-only text loss remain failures.
- Source-proxy duplicate evidence is a review condition unless parser-only
  duplication is independently proven.
- Parser-only duplication remains a parser-defect failure.
- Reading-order coordinate inversions are `REVIEW` pending visual confirmation,
  not automatic `FAIL`.
- Candidate-level table evidence is an expected current-parser limitation and
  requires review; it is not a parser failure by itself.
- Table-cell accuracy remains `not_measurable`.
- Metric statuses are independent; one metric does not inherit another metric's
  failure state.

## Source-Block Eligibility

Source-accuracy, chunk-quality, and triage diagnostics share the
`classify_source_block_chunk_eligibility(...)` function. The taxonomy is:

| State | Meaning |
| --- | --- |
| `required_direct_chunk` | The block must be directly represented in chunk references unless covered by a stricter finding. |
| `satisfied_by_entity_chunk` | Entity-derived or source-text replacement evidence satisfies chunk coverage. |
| `excluded_heading` | Heading context is not required as a direct chunk source under this policy. |
| `excluded_blank` | Empty source text is excluded from coverage denominators. |
| `excluded_metadata` | Page furniture and metadata are excluded. |
| `excluded_non_semantic` | Blocks that render no semantic chunk text are excluded. |
| `unsupported` | The block lacks enough identity for deterministic eligibility. |

This policy is evaluation-only. It does not mutate parser blocks, semantic
chunks, chunk IDs, source PDFs, or StructuredDocument output.

## Visual Review Requirements

Policy v2 can remove false automated `FAIL` outcomes, but it cannot grant final
`PASS`. Final `PASS` still requires completed visual checklists showing source
text completeness, reading order, table/figure/equation/admonition evidence,
chunk coherence, and absence of fabricated content.

## Owner Visual-Review Workflow

Phase 13I-c3 separates automated source-proxy evidence from owner visual
evidence. The workflow is:

1. Load the approved 32-page P0 plan.
2. Load a corrected `p0-source-accuracy / 2.0` automated report.
3. Generate ignored local review packages only with `--allow-local-write`.
4. Record explicit owner checklist decisions in local `review_checklist.json`
   files.
5. Validate checklist identity, status values, required fields, sanitized notes,
   absence of protected data fields, and absence of absolute paths.
6. Merge visual decisions additively with automated page results.
7. Derive page, document, and corpus acceptance outcomes.
8. Write sanitized reports only with `--allow-report-write`.

No checklist is auto-approved. Missing checklists and pending required fields
remain pending and block final `PASS`.

## Checklist Governance

Each page checklist records document key, zero-based PDF page index, one-based
page number, optional short reviewer identifier, review status, required
checklist fields, generalized visual finding codes, and sanitized notes.
Allowed review statuses are `pending`, `completed`, `needs_second_review`, and
`blocked`. Allowed checklist values are `pass`, `review`, `fail`,
`not_applicable`, and `pending`.

Checklist payloads reject unknown fields, protected source-derived fields,
absolute paths, oversized notes, source text payloads, rendered-image paths,
table contents, equation text, and personal contact information. Committed
summary fixtures may state only the generic reviewer role.

## Conflict Handling

Visual decisions do not overwrite automated evidence. Conflicts such as
automated `PASS` with visual `FAIL`, automated `REVIEW` with visual `PASS`, or
source-proxy uncertainty with visually correct parser behavior are recorded as
separate conflict findings. Final outcomes prioritize visually confirmed
critical or major defects while preserving the automated outcome and metrics.

## Acceptance Model

Page outcomes are `PASS`, `REVIEW`, or `FAIL`. Document outcomes are
`ACCEPTED`, `ACCEPTED_WITH_LIMITATIONS`, `REJECTED`, or `INCOMPLETE`. Corpus
outcomes use the same acceptance vocabulary. `INCOMPLETE` is mandatory while
any required visual check remains pending.

Document `ACCEPTED` requires all P0 pages final `PASS` or formally accepted
`REVIEW`, no unresolved critical or major defect, and documented limitations.
`ACCEPTED_WITH_LIMITATIONS` requires no final `FAIL` and explicit owner
acceptance of the remaining limitations. `REJECTED` applies to unresolved final
`FAIL`, systematic defects, or source-protection/evidence failure.

## Second-Review Policy

`needs_second_review` records ambiguous multi-column order, complex equations,
large tables, safety-critical admonition questions, automation/reviewer
disagreement, or uncertain figure-caption association. It is not a workflow
system and cannot produce final `PASS`.

## Downstream Authorization Conditions

Downstream persisted chunk mapping should proceed only after corpus acceptance
criteria are satisfied, or after the owner explicitly accepts documented
limitations with manual downstream controls. Phase 13I-c3 does not modify
AviationRAG, generate embeddings, access Astra DB, access FAISS, or evaluate
full-document accuracy.

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

Phase 13I-c2E completed the evaluator-policy correction and reran both scopes.
The corrected 32-page P0 source-accuracy rerun returned aggregate `REVIEW` with
32 final `REVIEW`, 0 final `FAIL`, 0 final `PASS`, and 32 pending visual
reviews.

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

## Pilot Closure Rules

Phase 13I-b3 adds a closure step after owner visual review is complete. Closure
requires the approved 32 P0 representative pages, 0 pending pages, 0
second-review pages, 0 blocked pages, and 0 final `FAIL` pages.

Current closure output separates:

- `historical_automated_findings`
- `historical_review_findings`
- `current_accepted_limitations`
- `current_confirmed_nonblocking_issues`
- `current_blocking_findings`
- `resolved_review_state_findings`

Stale review-state codes such as `VISUAL_REVIEW_PENDING` and
`VISUAL_CHECK_PENDING` are removed from active accepted limitations when review
completion is 100 percent. Historical occurrences remain preserved separately.
The obsolete `second_review_or_formal_limitation_acceptance` recommendation is
removed when the second-review count is 0.

Accepted limitations must be explicit, sanitized, and nonblocking for pilot
closure. Historical automated warnings do not automatically remain active
accepted limitations. The closure authorizes controlled downstream schema
design and a controlled local sample-persistence dry run only.

The representative-page pilot does not establish full-document accuracy,
OCR accuracy, P1/P2 accuracy, or full-corpus readiness. Full-corpus ingestion,
embedding regeneration, Astra rebuild, FAISS rebuild, and production retrieval
activation require a separate future authorization.
