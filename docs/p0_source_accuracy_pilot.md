# P0 Source-Accuracy Pilot Result

This is a sanitized summary of the local Phase 13I-b2 run. The full local
evidence package was written only under ignored
`output/evaluation/source_accuracy_p0/` and is not committed.

source_accuracy_scope: representative_p0_pages
visual_review_status: pending_or_completed_per_page
full_document_accuracy_evaluated: false
ocr_accuracy_evaluated: false

## Execution

- Command: `python tools/evaluation/run-source-accuracy-pilot.py --input-dir input --plan tests/fixtures/pilot_corpus/p0_source_accuracy_plan.json --all-p0 --output-dir output/evaluation/source_accuracy_p0 --allow-local-write --report-json output/evaluation/source_accuracy_p0/source_accuracy_p0_report.json --report-markdown output/evaluation/source_accuracy_p0/source_accuracy_p0_report.md --allow-report-write`
- Scope: 32 approved P0 pages across 8 ignored local PDFs.
- Outcome: `FAIL`.
- Final page outcomes: 25 `FAIL`, 7 `REVIEW`, 0 `PASS`.
- Visual review status: 32 `pending`, 0 completed.
- Local evidence files written: 256 ignored files.

## Aggregate Findings

| Category | Count |
| --- | ---: |
| `PARSER_DEFECT` | 37 |
| `MANUAL_REVIEW_REQUIRED` | 91 |
| `CONTRACT_LIMITATION` | 7 |

| Severity | Count |
| --- | ---: |
| `major` | 37 |
| `minor` | 48 |
| `informational` | 50 |

## Metric Summary

| Metric | Summary |
| --- | --- |
| Raw character coverage | 17 `pass`, 15 `fail` |
| Normalized line coverage | 32 `pass` |
| Duplicate line count | 17 `pass`, 15 `fail` |
| Unicode symbol loss count | 32 `pass` |
| Order inversion count | 12 `pass`, 20 `fail` |
| Page provenance consistency | 32 `pass` |
| Section parent integrity | 32 `pass` |
| Table evidence count | 10 `pass`, 15 `review`, 7 `not_applicable` |
| Figure-caption evidence count | 2 `pass`, 5 `review`, 25 `not_applicable` |
| Equation evidence count | 3 `review`, 29 `not_applicable` |
| Admonition evidence count | 1 `pass`, 2 `review`, 29 `not_applicable` |
| Cross-reference evidence count | 1 `pass`, 6 `review`, 25 `not_applicable` |
| Chunk source-block coverage | 30 `pass`, 2 `fail` |
| Source-page visual accuracy | 32 `not_measurable` |
| SR22 native-text classification | 4 `pass` |

## Document Summary

| Document key | P0 pages | Final outcomes | Findings |
| --- | --- | --- | ---: |
| `aircraft_stability_control` | 1, 3, 10, 48 | 2 `FAIL`, 2 `REVIEW` | 13 |
| `aircraft_system_safety` | 3, 18, 52, 106 | 3 `FAIL`, 1 `REVIEW` | 14 |
| `airworthiness_certification_operations` | 1, 22, 44, 60 | 3 `FAIL`, 1 `REVIEW` | 18 |
| `cirrus_sr22_maintenance_manual` | 1, 3, 7, 468 | 4 `FAIL` | 18 |
| `faa_order_4040_26b` | 1, 7, 29, 38 | 3 `FAIL`, 1 `REVIEW` | 20 |
| `flight_test_rm_ag_300` | 1, 4, 33, 131 | 4 `FAIL` | 18 |
| `introduction_flight_test_engineering` | 1, 23, 145, 453 | 4 `FAIL` | 19 |
| `mil_std_882e` | 1, 14, 17, 33 | 2 `FAIL`, 2 `REVIEW` | 15 |

## Post-Pilot Triage Status

Phase 13I-c1 completed a diagnosis-only root-cause triage of 10 approved P0
pages selected from the Phase 13I-b2 results. The original b2 report remains
the baseline and was not rewritten: 25 final `FAIL` pages, 7 final `REVIEW`
pages, 0 final `PASS` pages, and 32 pending human visual reviews.

The triage subset classified 48 original findings and returned `REVIEW`.
Automated evidence found no confirmed parser defects in the selected pages. It
classified 9 findings as `EVALUATION_FRAMEWORK_DEFECT`, 7 duplicate-text
findings as `SOURCE_PROXY_LIMITATION`, 3 table-candidate findings as
`EXPECTED_MULTI_REPRESENTATION`, 4 section-context findings as
`DOCUMENT_LAYOUT_LIMITATION`, and 25 findings as
`NEEDS_VISUAL_CONFIRMATION`.

The evidence-supported next corrective phase is `13I-c2E` for evaluator-policy
correction, followed by a rerun of both the 10-case triage subset and the
original 32-page P0 source-accuracy pilot. Parser corrective work for
duplication, reading order, text coverage, and chunk coverage remains blocked
until the required visual confirmation and evaluator-policy correction are
complete.

See [`docs/p0_failure_root_cause_analysis.md`](p0_failure_root_cause_analysis.md)
for the sanitized root-cause matrix and recommended corrective phases.

## Corrected Evaluation-Policy Rerun

Phase 13I-c2E corrected only evaluator-policy interpretation defects proven by
Phase 13I-c1. The original Phase 13I-b2 result remains valid historical
evidence under policy interpretation 1: 25 final `FAIL`, 7 final `REVIEW`, 0
final `PASS`.

The corrected rerun is identified separately:

- `evaluation_policy_name`: `p0-source-accuracy`
- `evaluation_policy_version`: `2.0`
- `run_type`: `corrected_evaluator_rerun`
- `supersedes_policy_interpretation`: `1`

Corrected 32-page P0 rerun outcome:

- Aggregate outcome: `REVIEW`.
- Final page outcomes: 32 `REVIEW`, 0 `FAIL`, 0 `PASS`.
- Automated outcomes: 2 `PASS`, 30 `REVIEW`, 0 `FAIL`.
- Raw character coverage: 32 `pass`.
- Duplicate line count: 17 `pass`, 15 `review`.
- Order inversion count: 12 `pass`, 20 `review`.
- Chunk source-block coverage: 32 `pass`.
- Visual review status: 32 pending, 0 completed.

Corrected policy records were emitted for 25 pages:

- `DUPLICATION_DECOUPLED_FROM_COVERAGE`: 15
- `SOURCE_PROXY_DUPLICATION_RECLASSIFIED`: 15
- `READING_ORDER_VISUAL_REVIEW_REQUIRED`: 20
- `SOURCE_BLOCK_ELIGIBILITY_RECLASSIFIED`: 2

The corrected rerun does not make any page a final `PASS`; human visual review
is still required. Parser output, semantic chunk output, StructuredDocument
mapping, source PDFs, dependencies, AviationRAG, embeddings, and external APIs
were unchanged.

Corrected deterministic report hashes:

- JSON:
  `5DA319515370540CB2BE5F5103560DC297C6A5A7B704188201D8D1A3F61310CC`
- Markdown:
  `47CB106B7845B35CD27A39FDE2F343FBFD008912775DD132B67293D89997BD33`

## Owner Visual Review and Acceptance Status

Phase 13I-c3 adds the owner visual-review and P0 pilot-acceptance workflow on
top of the corrected policy-v2 evidence. It does not alter the historical
policy-v1 result, the corrected policy-v2 automated result, or the Phase
13I-c1 triage findings.

Current visual-review progress:

- Pages total: 32.
- Completed: 0.
- Pending: 32.
- Second review: 0.
- Blocked: 0.
- Completion percentage: 0.0.

Current page outcomes after pending visual-review merge:

- Final `PASS`: 0.
- Final `REVIEW`: 32.
- Final `FAIL`: 0.

Document outcomes:

| Document key | Outcome | Confirmed defects | Accepted limitations | Pending items |
| --- | --- | ---: | --- | ---: |
| `aircraft_stability_control` | `INCOMPLETE` | 0 | none | 4 |
| `aircraft_system_safety` | `INCOMPLETE` | 0 | none | 4 |
| `airworthiness_certification_operations` | `INCOMPLETE` | 0 | none | 4 |
| `cirrus_sr22_maintenance_manual` | `INCOMPLETE` | 0 | none | 4 |
| `faa_order_4040_26b` | `INCOMPLETE` | 0 | none | 4 |
| `flight_test_rm_ag_300` | `INCOMPLETE` | 0 | none | 4 |
| `introduction_flight_test_engineering` | `INCOMPLETE` | 0 | none | 4 |
| `mil_std_882e` | `INCOMPLETE` | 0 | none | 4 |

Corpus acceptance status: `INCOMPLETE`.

No parser defect has been visually confirmed. No candidate-level table,
figure-interpretation, equation-layout, or source-proxy limitation has been
formally accepted by visual review. Pending owner review remains the blocking
item before P0 pilot acceptance, targeted parser correction, or AviationRAG
persisted chunk mapping.

## Determinism

Two ignored reruns produced byte-identical sanitized reports:

- JSON hash: `02CB9E912580DACFB2A92632BCFAE112327944C3C4BBBBF32D98BF1588C51B8E`
- Markdown hash: `6EDEC60F031D62E709A29C3EA3570228EBD1276424604564E28CCC508ECEE7C1`
- Both runs exited `1` because the controlled outcome was `FAIL`.

## Limitations

- Automated source proxies use PDF text extraction and are not independent
  visual ground truth.
- Human visual review is required before any page can receive final `PASS`.
- Only approved P0 representative pages were scored.
- Full-document accuracy was not evaluated.
- OCR was not run and OCR accuracy was not evaluated.
- Table-cell accuracy and figure visual-content accuracy are not measurable
  with the current parser.
- Existing parser behavior, chunking, and StructuredDocument output were not
  changed.

No extracted source text, rendered pages, source hashes, table contents,
equations, proprietary procedures, or local evidence files are included in this
committed summary.

## Final Owner Acceptance

Phase 13I-b3 formally closes the P0 representative-page pilot after completion
of all local owner visual reviews.

Final owner-review result:

| PASS | REVIEW | FAIL |
| ---: | ---: | ---: |
| 28 | 4 | 0 |

Final pilot outcome: `ACCEPTED_WITH_LIMITATIONS`.

Confirmed blocking findings: `0`.

Confirmed nonblocking issue:

- `TABLE_FALSE_POSITIVE_ON_FIGURE_PAGE`: minor
  `CONTENT_TYPE_MISCLASSIFICATION` on `aircraft_system_safety`, page 52,
  accepted for pilot with deferred refinement.

Final active accepted limitations:

- `CHUNK_SECTION_CROSSING_REVIEW`
- `DUPLICATE_TEXT_LINES`
- `TABLE_CANDIDATE_ONLY`

Authorization boundaries:

- Controlled downstream schema design is authorized.
- Controlled local sample-persistence dry run is authorized.
- Full-corpus ingestion is not authorized.
- Embedding regeneration is not authorized.
- Astra rebuild is not authorized.
- FAISS rebuild is not authorized.

Historical policy-v1, policy-v2, and root-cause triage results remain preserved.
Parser extraction, OCR, reading order, block creation, normalization, structure
detection, chunk generation, StructuredDocument output, dependencies, and CLI
behavior were unchanged.
