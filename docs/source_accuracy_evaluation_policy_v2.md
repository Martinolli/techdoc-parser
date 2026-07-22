# Source-Accuracy Evaluation Policy v2

## Purpose

Policy v2 corrects evaluator-policy defects proven by Phase 13I-c1. It is a
report-only policy update for `p0-source-accuracy`; it does not change parser
extraction, OCR, raw block creation, normalization, reading order, structure
detection, semantic chunk generation, chunk IDs, StructuredDocument mapping, or
current parser outputs.

## Policy Identity

- `evaluation_policy_name`: `p0-source-accuracy`
- `evaluation_policy_version`: `2.0`
- `run_type`: `corrected_evaluator_rerun`
- `supersedes_policy_interpretation`: `1`

The Phase 13I-b2 result remains valid historical evidence under policy
interpretation 1: 25 final `FAIL`, 7 final `REVIEW`, 0 final `PASS`.

## Corrections

Policy v2 applies these evaluator-only corrections:

- Raw text coverage is independent from duplicate-line findings. Coverage uses
  coverage ratio, missing lines, native-text availability, and symbol loss.
- Source-proxy duplicates are `SOURCE_PROXY_LIMITATION` review findings unless
  parser-only duplication is independently shown.
- Parser-only duplicates remain `PARSER_DEFECT` failures.
- Chunk source-block coverage uses the shared eligibility function
  `classify_source_block_chunk_eligibility(...)`.
- Eligibility states are `required_direct_chunk`,
  `satisfied_by_entity_chunk`, `excluded_heading`, `excluded_blank`,
  `excluded_metadata`, `excluded_non_semantic`, and `unsupported`.
- Entity-derived replacements can satisfy chunk coverage through source text
  references without changing chunk generation.
- Candidate-level tables are review/contract limitations, not parser failures
  by themselves.
- Metric statuses are independent; one metric does not inherit another metric's
  failure status.
- Reading-order coordinate inversions are `REVIEW` pending visual
  confirmation, not automatic `FAIL`.

## Correction Records

When policy v2 changes a v1 interpretation, sanitized page results include
`policy_corrections` records with:

- `original_finding_code`
- `corrected_policy_disposition`
- `corrected_metric_status`
- `correction_reason_code`
- `metric_name`

These records preserve the original finding code while identifying the v2
disposition.

## Corrected Rerun Result

The 10-case triage comparison found 9 original evaluator defects, 0 reproduced
after policy v2, and 9 resolved after policy v2.

The corrected 32-page P0 rerun returned aggregate `REVIEW`:

- Final outcomes: 32 `REVIEW`, 0 `FAIL`, 0 `PASS`.
- Automated outcomes: 2 `PASS`, 30 `REVIEW`, 0 `FAIL`.
- Raw character coverage: 32 `pass`.
- Duplicate line count: 17 `pass`, 15 `review`.
- Order inversion count: 12 `pass`, 20 `review`.
- Chunk source-block coverage: 32 `pass`.
- Visual review: 32 pending.

Policy correction counts:

- `DUPLICATION_DECOUPLED_FROM_COVERAGE`: 15
- `SOURCE_PROXY_DUPLICATION_RECLASSIFIED`: 15
- `READING_ORDER_VISUAL_REVIEW_REQUIRED`: 20
- `SOURCE_BLOCK_ELIGIBILITY_RECLASSIFIED`: 2

Two sanitized corrected reruns produced byte-identical report hashes:

- Source-accuracy JSON:
  `5DA319515370540CB2BE5F5103560DC297C6A5A7B704188201D8D1A3F61310CC`
- Source-accuracy Markdown:
  `47CB106B7845B35CD27A39FDE2F343FBFD008912775DD132B67293D89997BD33`
- Triage JSON:
  `EAB986F8DFFBEECFC6402536C14453584FAA825D6D31CA3F202696D7ECF6A74E`
- Triage Markdown:
  `5303BF01C47B3E2D7B44100721DC625408073BB715A4B6E1409DF9CFD0E94F6E`

## Privacy

The committed policy and summary documents contain no extracted source text,
source hashes, rendered pages, images, proprietary procedures, table contents,
or equations. Full local reports are under ignored `output/evaluation/`.
