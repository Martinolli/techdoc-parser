# P0 Visual Review and Acceptance

## Purpose

Phase 13I-c3 adds an owner visual-review and pilot-acceptance workflow for the
corrected `p0-source-accuracy / 2.0` evidence. It records explicit human
decisions separately from automated source-proxy evidence and produces
sanitized page, document, and corpus outcomes.

## Scope

The scope is exactly the 32 approved P0 pages in
`tests/fixtures/pilot_corpus/p0_source_accuracy_plan.json`. P1 pages, P2 pages,
additional documents, full-document accuracy, OCR accuracy, and downstream
AviationRAG ingestion are out of scope.

## Automated Versus Visual Evidence

Automated policy-v2 evidence is preserved as originally reported. Visual review
does not overwrite automated outcomes, metrics, or findings. Explicit owner
checklists are merged as additive visual evidence and any automated-versus-human
conflict is recorded as a separate conflict finding.

## Required Checklist

Every page checklist must include these fields:

```text
text_complete
text_exact_enough
reading_order_correct
headings_correct
section_assignment_correct
page_provenance_correct
table_evidence_usable
figure_caption_correct
equation_preserved
admonition_exact
cross_references_preserved
chunks_coherent
fabricated_content_absent
```

Allowed values are `pass`, `review`, `fail`, `not_applicable`, and `pending`.
Content-specific checks may be `not_applicable`. Required pending checks block
final `PASS`; failed checks create visual findings.

## Page Outcome Policy

Final `PASS` requires no automated `FAIL`, completed review status, all
applicable checklist items `pass` or `not_applicable`, no critical or major
visual finding, absent fabricated content, correct page provenance, and correct
safety-critical wording where applicable.

Final `REVIEW` is used when second review is requested, an applicable check is
`review`, review remains pending, or accepted limitations still require manual
downstream control.

Final `FAIL` is used for visually confirmed material omission, misleading
duplication, meaning-changing reading order, materially wrong hierarchy or page
provenance, lost or altered warning/caution/note wording, corrupted equation,
destroyed table meaning, fabricated content, false cross-reference status, or
chunks that combine unrelated technical content.

## Visual Finding Taxonomy

Visual findings use generalized codes only, including
`VISUAL_TEXT_OMISSION`, `VISUAL_TEXT_DUPLICATION`,
`VISUAL_READING_ORDER_ERROR`, `VISUAL_HEADING_ERROR`,
`VISUAL_SECTION_ASSIGNMENT_ERROR`, `VISUAL_PAGE_PROVENANCE_ERROR`,
`VISUAL_TABLE_UNUSABLE`, `VISUAL_CAPTION_MISMATCH`,
`VISUAL_EQUATION_CORRUPTION`, `VISUAL_ADMONITION_MISMATCH`,
`VISUAL_REFERENCE_MISMATCH`, `VISUAL_CHUNK_INCOHERENCE`,
`VISUAL_FABRICATION_DETECTED`, and `VISUAL_LAYOUT_LIMITATION`. Visually
confirmed critical or major parser defects are classified as
`CONFIRMED_PARSER_DEFECT`.

## Conflict Policy

Conflicts such as automated `PASS` with visual `FAIL`, automated `REVIEW` with
visual `PASS`, source-proxy limitation with visual parser correctness, or
automated uncertainty with visual correctness are recorded without relabeling
the automated result.

## Second-Review Policy

`needs_second_review` records ambiguous multi-column order, complex equations,
large tables, safety-critical admonition questions, automation/reviewer
disagreement, or uncertain figure-caption association. It is not a multi-user
workflow and cannot produce final `PASS`.

## Acceptance Policy

Document outcomes are:

- `ACCEPTED`: all P0 pages are final `PASS` or formally accepted `REVIEW`, with
  no unresolved critical or major defect.
- `ACCEPTED_WITH_LIMITATIONS`: no final `FAIL`, at least one `REVIEW` page, and
  accepted limitations requiring downstream manual controls.
- `REJECTED`: one or more unresolved final `FAIL` pages, systematic defect, or
  source-protection/evidence failure.

Corpus outcomes are `ACCEPTED`, `ACCEPTED_WITH_LIMITATIONS`, `REJECTED`, and
`INCOMPLETE`. `INCOMPLETE` is required while any mandatory visual check remains
pending.

## Review Package

Local review packages are written under ignored
`output/evaluation/source_accuracy_p0_review/` only with
`--allow-local-write`. Each page directory contains a rendered local page,
`review.html`, `review_checklist.json`, and `automated_summary.json`. Checklist
files are not silently overwritten.

## CLI Usage

Generate local review pages:

```powershell
python tools/evaluation/run-p0-visual-review.py `
  --input-dir input `
  --plan tests/fixtures/pilot_corpus/p0_source_accuracy_plan.json `
  --automated-report output/evaluation/source_accuracy_p0_c2e/source_accuracy_p0_policy_v2_run1.json `
  --evidence-dir output/evaluation/source_accuracy_p0_review `
  --all-p0 `
  --generate-review-package `
  --allow-local-write
```

Merge edited checklists and write sanitized reports:

```powershell
python tools/evaluation/run-p0-visual-review.py `
  --plan tests/fixtures/pilot_corpus/p0_source_accuracy_plan.json `
  --automated-report output/evaluation/source_accuracy_p0_c2e/source_accuracy_p0_policy_v2_run1.json `
  --evidence-dir output/evaluation/source_accuracy_p0_review `
  --all-p0 `
  --merge-checklists `
  --report-json output/evaluation/source_accuracy_p0_review/p0_visual_review.json `
  --report-markdown output/evaluation/source_accuracy_p0_review/p0_visual_review.md `
  --allow-report-write
```

The CLI exits `0` for `ACCEPTED`, `2` for
`ACCEPTED_WITH_LIMITATIONS` or `INCOMPLETE`, and `1` for `REJECTED` or a
blocking error.

## Privacy Safeguards

Committed artifacts contain no extracted source text, rendered images,
equations, procedure wording, table contents, absolute paths, source hashes, or
personal contact details. Reviewer identity is optional and should be a short
role-like identifier only.

## Current Review Progress

Current committed sanitized status:

- Pages total: 32.
- Completed: 0.
- Pending: 32.
- Second review: 0.
- Blocked: 0.
- Completion percentage: 0.0.
- Corpus acceptance: `INCOMPLETE`.

## Page-Level Outcomes

All 32 approved P0 pages remain final `REVIEW` because visual checks are
pending. No page is final `PASS`, and no visual final `FAIL` has been confirmed.

## Document Outcomes

All 8 documents are `INCOMPLETE` because each has pending required visual
checks.

## Confirmed Parser Defects

No parser defect has been visually confirmed in Phase 13I-c3.

## Accepted Limitations

No visual limitation has been formally accepted. Automated review conditions
such as candidate-level table representation, figure interpretation, equation
layout, and source-proxy limitations remain pending owner review.

## Blocking Findings

No visual blocking finding has been confirmed. Pending visual review blocks
pilot acceptance.

## Corrective Phase Recommendations

The next step is to complete the remaining owner visual reviews. Targeted
parser correction should begin only after a visual finding confirms a parser
defect.

## Full-Document Boundary

Full-document accuracy is not evaluated by this workflow. The P0 pilot covers
only the approved representative pages.

## AviationRAG Preconditions

AviationRAG persisted chunk mapping should resume only after P0 acceptance
criteria are satisfied or the owner explicitly accepts documented limitations
with downstream manual controls. Phase 13I-c3 does not modify AviationRAG,
generate embeddings, access Astra DB, or access FAISS.

## Final Owner-Review Closure

Phase 13I-b3 closes the local owner-review cycle. All 32 P0 representative
pages are complete: 32 completed, 0 pending, 0 second review, and 0 blocked.
Completion is 100 percent.

Final page outcomes:

| Outcome | Count |
| --- | ---: |
| PASS | 28 |
| REVIEW | 4 |
| FAIL | 0 |

Final document outcomes:

| Document key | Outcome |
| --- | --- |
| `aircraft_stability_control` | `ACCEPTED_WITH_LIMITATIONS` |
| `aircraft_system_safety` | `ACCEPTED_WITH_LIMITATIONS` |
| `airworthiness_certification_operations` | `ACCEPTED` |
| `cirrus_sr22_maintenance_manual` | `ACCEPTED` |
| `faa_order_4040_26b` | `ACCEPTED` |
| `flight_test_rm_ag_300` | `ACCEPTED` |
| `introduction_flight_test_engineering` | `ACCEPTED_WITH_LIMITATIONS` |
| `mil_std_882e` | `ACCEPTED` |

Final active accepted limitations:

- `CHUNK_SECTION_CROSSING_REVIEW`
- `DUPLICATE_TEXT_LINES`
- `TABLE_CANDIDATE_ONLY`

The closure removes stale `VISUAL_REVIEW_PENDING` and
`VISUAL_CHECK_PENDING` codes from the current accepted-limitation list, while
preserving them as historical review-state findings. The obsolete
`second_review_or_formal_limitation_acceptance` recommendation is removed
because second-review count is 0.

The confirmed nonblocking issue
`TABLE_FALSE_POSITIVE_ON_FIGURE_PAGE` is recorded for
`aircraft_system_safety`, page 52. It is a minor content-type
misclassification accepted for the pilot with deferred refinement.

Controlled downstream schema design is authorized. Full-corpus ingestion,
embedding regeneration, Astra rebuild, FAISS rebuild, and production retrieval
activation are not authorized.
