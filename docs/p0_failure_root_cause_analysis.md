# P0 Failure Root-Cause Analysis

## Purpose

Phase 13I-c1 diagnoses selected Phase 13I-b2 P0 source-accuracy failures before
any parser, chunker, or evaluator correction. It does not change parser
behavior or original P0 outcomes.

## Diagnostic Scope

- Triage scope: `selected_p0_failure_root_cause_isolation`.
- Selected cases: 10 approved P0 pages.
- Original findings classified: 48.
- Outcome: `REVIEW`, because 25 findings still require visual confirmation.
- Local diagnostic evidence: ignored `output/evaluation/p0_failure_triage/`.

## Selected Pages

| Case | Document | Page | Original failures | Selection reason |
| ---- | -------- | ---: | ----------------- | ---------------- |
| `control_aircraft_stability_p1` | `aircraft_stability_control` | 1 | VISUAL_REVIEW_PENDING | automated PASS control |
| `triage_aircraft_stability_p3` | `aircraft_stability_control` | 3 | duplicate, text-coverage metric, visual order | duplicate/text-coverage control |
| `triage_aircraft_stability_p10` | `aircraft_stability_control` | 10 | duplicate, order, figure, equation, admonition, section crossing | equation/text-box and multi-column |
| `triage_aircraft_system_safety_p18` | `aircraft_system_safety` | 18 | duplicate, order, cross-reference, section crossing | cross-reference and multi-column |
| `triage_sr22_p7` | `cirrus_sr22_maintenance_manual` | 7 | order, table, admonition, cross-reference, section crossing | SR22 procedure/admonition case |
| `triage_faa_order_p7_chunk_gap` | `faa_order_4040_26b` | 7 | order, cross-reference, table candidate, figure review, chunk gap | chunk gap and table-heavy |
| `triage_faa_order_p29_chunk_gap` | `faa_order_4040_26b` | 29 | duplicate, order, figure, table candidate, chunk gap, section crossing | chunk gap and complex page |
| `triage_airworthiness_p22` | `airworthiness_certification_operations` | 22 | duplicate, order, figure, table candidate | table and figure page |
| `triage_intro_flight_test_p23` | `introduction_flight_test_engineering` | 23 | duplicate, order, table, figure | multi-document table/figure |
| `triage_mil_std_p17` | `mil_std_882e` | 17 | duplicate, order, table, figure review | MIL-STD table/figure |

## Original Phase 13I-b2 Failures Represented

The subset covers duplicate-text failures, reading-order failures,
text-coverage metric failures, both chunk source-coverage gaps, table-heavy
pages, figure-caption pages, equation/text-box evidence, admonition/procedure
evidence, SR22 evidence, and one automated PASS control page.

## Pipeline-Stage Model

The diagnostic pipeline captures sanitized observations for:

1. source proxy;
2. raw parser text blocks;
3. ordered parser/semantic blocks;
4. normalized blocks;
5. structured entities;
6. semantic chunks;
7. source-accuracy evaluator assumptions.

## Root-Cause Taxonomy

The phase uses these root-cause classifications:

- `CONFIRMED_PARSER_DEFECT`
- `EVALUATION_FRAMEWORK_DEFECT`
- `SOURCE_PROXY_LIMITATION`
- `EXPECTED_MULTI_REPRESENTATION`
- `DOCUMENT_LAYOUT_LIMITATION`
- `NEEDS_VISUAL_CONFIRMATION`

## Duplicate-Text Findings

Seven investigated duplicate findings are classified as
`SOURCE_PROXY_LIMITATION` with probable certainty. The duplicate lines were
already present in direct source-block proxy extraction, so they are not proven
parser-introduced defects. Owner visual confirmation remains required before
any duplicate-text parser correction.

## Reading-Order Findings

All investigated reading-order failures remain `NEEDS_VISUAL_CONFIRMATION`.
The selected order cases involve complex layouts, tables, captions, text boxes,
or multi-column indicators. Automated coordinate inversions alone are not
sufficient evidence to classify them as parser defects.

## Text-Coverage Findings

Seven text-coverage metric failures are classified as
`EVALUATION_FRAMEWORK_DEFECT` with confirmed certainty. The raw coverage values
met the configured threshold and missing-line counts were zero, but the metric
status inherited failure from duplicate-line handling. This is an evaluator
policy issue to correct separately without rewriting the Phase 13I-b2 results.

## Chunk Source-Coverage Findings

Both investigated chunk source-coverage gaps are classified as
`EVALUATION_FRAMEWORK_DEFECT` with confirmed certainty. Diagnostic comparison
found that the b2 evaluator counted semantic blocks as missing when chunk
rendering treated those blocks as non-emitting or the gap could not be
reproduced under the rendered chunk eligibility check.

## Table/Entity Representation Findings

Three `TABLE_CANDIDATE_ONLY` findings are classified as
`EXPECTED_MULTI_REPRESENTATION`. Candidate-level table structure is expected in
the current architecture and must not be treated as parser duplication or a
parser defect by itself.

## Equation/Text-Box Findings

The selected equation/text-box page remains `NEEDS_VISUAL_CONFIRMATION`.
Automated evidence cannot determine whether visual equation/text-box layout was
preserved.

## Control-Page Findings

The control page preserved the expected automated-clean behavior. Its only
triage finding is pending visual review.

## Visual-Confirmation Status

Twenty-five findings require owner visual confirmation. No local visual
checklists were completed in this phase.

## Root-Cause Matrix

| Case | Original failure | Introduced stage | Root cause | Certainty | Corrective owner | Recommended phase |
| ---- | ---------------- | ---------------- | ---------- | --------- | ---------------- | ----------------- |
| `control_aircraft_stability_p1` | VISUAL_REVIEW_PENDING | human_visual_review | NEEDS_VISUAL_CONFIRMATION | confirmed | owner_review | owner_visual_checklists |
| `triage_aircraft_stability_p3` | duplicate/text coverage/order review | source_proxy, source_accuracy_evaluator, human_visual_review | SOURCE_PROXY_LIMITATION, EVALUATION_FRAMEWORK_DEFECT, NEEDS_VISUAL_CONFIRMATION | probable/confirmed/uncertain | owner_review/evaluation | owner_visual_checklists, 13I-c2E |
| `triage_aircraft_stability_p10` | duplicate/text coverage/order/entities/section | source_proxy, source_accuracy_evaluator, human_visual_review, chunk_construction | SOURCE_PROXY_LIMITATION, EVALUATION_FRAMEWORK_DEFECT, NEEDS_VISUAL_CONFIRMATION, DOCUMENT_LAYOUT_LIMITATION | probable/confirmed/uncertain | owner_review/evaluation | owner_visual_checklists, 13I-c2E |
| `triage_aircraft_system_safety_p18` | duplicate/text coverage/order/cross-reference/section | source_proxy, source_accuracy_evaluator, human_visual_review, chunk_construction | SOURCE_PROXY_LIMITATION, EVALUATION_FRAMEWORK_DEFECT, NEEDS_VISUAL_CONFIRMATION, DOCUMENT_LAYOUT_LIMITATION | probable/confirmed/uncertain | owner_review/evaluation | owner_visual_checklists, 13I-c2E |
| `triage_sr22_p7` | order/table/admonition/cross-reference/section | human_visual_review, chunk_construction | NEEDS_VISUAL_CONFIRMATION, DOCUMENT_LAYOUT_LIMITATION | uncertain/probable | owner_review | owner_visual_checklists |
| `triage_faa_order_p7_chunk_gap` | order/cross-reference/table/figure/chunk gap | human_visual_review, structure/entity_mapping, source_accuracy_evaluator | NEEDS_VISUAL_CONFIRMATION, EXPECTED_MULTI_REPRESENTATION, EVALUATION_FRAMEWORK_DEFECT | uncertain/confirmed | owner_review/evaluation | owner_visual_checklists, 13I-c2E |
| `triage_faa_order_p29_chunk_gap` | duplicate/text coverage/order/figure/table/chunk/section | source_proxy, source_accuracy_evaluator, human_visual_review, structure/entity_mapping, chunk_construction | SOURCE_PROXY_LIMITATION, EVALUATION_FRAMEWORK_DEFECT, NEEDS_VISUAL_CONFIRMATION, EXPECTED_MULTI_REPRESENTATION, DOCUMENT_LAYOUT_LIMITATION | probable/confirmed/uncertain | owner_review/evaluation | owner_visual_checklists, 13I-c2E |
| `triage_airworthiness_p22` | duplicate/text coverage/order/figure/table | source_proxy, source_accuracy_evaluator, human_visual_review, structure/entity_mapping | SOURCE_PROXY_LIMITATION, EVALUATION_FRAMEWORK_DEFECT, NEEDS_VISUAL_CONFIRMATION, EXPECTED_MULTI_REPRESENTATION | probable/confirmed/uncertain | owner_review/evaluation | owner_visual_checklists, 13I-c2E |
| `triage_intro_flight_test_p23` | duplicate/text coverage/order/table/figure | source_proxy, source_accuracy_evaluator, human_visual_review | SOURCE_PROXY_LIMITATION, EVALUATION_FRAMEWORK_DEFECT, NEEDS_VISUAL_CONFIRMATION | probable/confirmed/uncertain | owner_review/evaluation | owner_visual_checklists, 13I-c2E |
| `triage_mil_std_p17` | duplicate/text coverage/order/table/figure | source_proxy, source_accuracy_evaluator, human_visual_review | SOURCE_PROXY_LIMITATION, EVALUATION_FRAMEWORK_DEFECT, NEEDS_VISUAL_CONFIRMATION | probable/confirmed/uncertain | owner_review/evaluation | owner_visual_checklists, 13I-c2E |

## Confirmed Parser Defects

No selected finding was classified as `CONFIRMED_PARSER_DEFECT`.

## Evaluator Defects

Nine findings are classified as `EVALUATION_FRAMEWORK_DEFECT`: seven
text-coverage status false positives and both chunk source-coverage gaps.

## Source-Proxy Limitations

Seven duplicate-text findings are classified as `SOURCE_PROXY_LIMITATION`.
They require visual review before parser correction is justified.

## Expected Multi-Representation

Three table candidate findings are classified as
`EXPECTED_MULTI_REPRESENTATION`.

## Layout Limitations

Four section-context findings are classified as
`DOCUMENT_LAYOUT_LIMITATION`. These are review drivers, not confirmed parser
defects.

## Pending Visual Confirmation

Twenty-five findings remain `NEEDS_VISUAL_CONFIRMATION`, including reading
order, figure-caption association, equation/text-box evidence, admonition or
procedure evidence, cross-reference evidence, and pending visual review.

## Recommended Corrective Phases

Recommended evidence-supported phase:

- `13I-c2E - Evaluation-policy correction`: fix raw coverage status coupling,
  chunk source-coverage eligibility, and candidate table interpretation in the
  evaluator. Rerun `triage_aircraft_stability_p3`,
  `triage_aircraft_stability_p10`, `triage_aircraft_system_safety_p18`,
  `triage_airworthiness_p22`, `triage_faa_order_p7_chunk_gap`,
  `triage_faa_order_p29_chunk_gap`, `triage_intro_flight_test_p23`, and
  `triage_mil_std_p17`.

Owner action:

- Complete visual root-cause checklists for all selected reading-order,
  duplicate, visual entity, and SR22 cases before parser corrective work.

No parser corrective phase is recommended yet for duplication, reading order,
text coverage, or chunking because the selected evidence did not confirm parser
defects.

## Pages to Rerun After Each Correction

After `13I-c2E`, rerun the 10-case triage subset and the original 32-page P0
source-accuracy report to verify the interpretation changes without changing
parser output.

## No Parser Fix Performed

Phase 13I-c1 performed diagnosis only. It did not change PDF extraction,
normalization, reading-order logic, block creation, structure/entity mapping,
chunking, StructuredDocument output, dependencies, source PDFs, local evidence,
or AviationRAG.
