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
