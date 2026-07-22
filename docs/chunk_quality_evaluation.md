# Fixture-Based Chunk Quality Evaluation

Phase 13I adds an offline, deterministic, fixture-only chunk-quality evaluation
framework under `techdoc_parser.evaluation`.

The framework measures quality proxies from committed synthetic structured
fixtures. Fixture metrics are quality proxies only; they do not prove
source-page visual accuracy, OCR accuracy, semantic accuracy, or real
aviation-document accuracy.

## Scope

Included:

- Existing repository fixtures under `tests/fixtures/structured_document/`.
- Current in-memory parser models and current semantic chunk generation.
- Deterministic coverage, provenance, ordering, section, size, duplication,
  overlap, and special-content proxy metrics.
- JSON and Markdown report serialization.
- Optional report writing only with explicit `--allow-report-write`.

Excluded:

- Proprietary or external documents.
- Source-page visual accuracy evaluation.
- OCR accuracy evaluation.
- Real aviation-document accuracy evaluation.
- Parser repair, parser behavior changes, extraction/OCR/reading-order changes,
  block-detection changes, chunk-generation changes, JSON/Markdown/manifest or
  StructuredDocument output changes.
- AviationRAG runtime ingestion, embeddings, Astra, FAISS, external APIs, and
  LLM or semantic-similarity scoring.

## CLI

List available fixture cases:

```powershell
python tools/evaluation/run-chunk-quality-evaluation.py --list-cases
```

Run all committed fixture cases:

```powershell
python tools/evaluation/run-chunk-quality-evaluation.py --all-cases
```

Write local reports only when explicitly allowed:

```powershell
python tools/evaluation/run-chunk-quality-evaluation.py `
  --all-cases `
  --report-json output/evaluation/chunk_quality_report.json `
  --report-markdown output/evaluation/chunk_quality_report.md `
  --allow-report-write
```

CLI exit codes:

| Outcome | Exit code |
| --- | ---: |
| `PASS` | 0 |
| `REVIEW` | 2 |
| `FAIL` | 1 |

`--strict` maps `REVIEW` to exit code `1` for CI modes that require manual
review to fail closed.

## Metrics

The current metric surface is:

| Metric | Purpose |
| --- | --- |
| `source_block_coverage` | Checks that semantic fixture blocks are represented by chunk `source_block_ids`. |
| `source_block_reference_integrity` | Checks that chunk source-block references resolve to the fixture. |
| `reading_order_consistency` | Checks monotonic source-block ordering against the semantic block view. |
| `section_boundary_coherence` | Checks whether chunks combine explicit fixture section paths. |
| `chunk_size` | Checks deterministic minimum and maximum chunk character thresholds. |
| `duplicate_text_ratio` | Checks duplicate normalized chunk text. |
| `duplicate_source_reference_ratio` | Checks repeated source block references across chunks. |
| `exact_text_overlap_ratio` | Checks exact normalized line overlap across comparable chunks. |
| `chunk_provenance_completeness` | Checks current-model provenance fields and reports missing future checksum evidence as review-only. |
| `table_source_preservation` | Checks explicit fixture table source block representation and text preservation. |
| `figure_caption_source_preservation` | Checks explicit fixture figure-caption representation and text preservation. |
| `equation_source_preservation` | Checks explicit fixture equation representation and text preservation. |
| `admonition_source_preservation` | Checks explicit fixture warning/caution/note representation and text preservation. |
| `cross_reference_source_preservation` | Checks explicit fixture cross-reference source representation and text preservation. |
| `table_cell_accuracy` | Always `not_measurable`; table-cell visual/source accuracy is out of scope. |
| `source_page_visual_accuracy` | Always `not_measurable`; visual/source accuracy is out of scope. |
| `determinism` | Checks repeated fixture chunking produces identical chunk dictionaries. |

Metric statuses are `pass`, `review`, `fail`, `not_measurable`, and
`not_applicable`. Overall outcomes are `PASS`, `REVIEW`, and `FAIL`.

## Current Baseline

The committed baseline is:

```text
tests/fixtures/chunk_quality/expected_chunk_quality_baseline.json
```

The current expected aggregate result is `REVIEW`:

- 5 fixture cases evaluated.
- 0 `PASS`.
- 5 `REVIEW`.
- 0 `FAIL`.

The review outcome is expected because the current fixtures and chunk model do
not carry verified source checksum provenance for chunk records, and visual
source accuracy/table-cell accuracy are intentionally not measurable in this
fixture-only phase.

## Recommended Follow-Up

Recommended next step: Phase 13I-b - Controlled approved-document
source-accuracy pilot.

That follow-up should be explicitly approved and use approved source documents
only. It should remain separate from parser repair, embeddings, AviationRAG
runtime ingestion, Astra, FAISS, or external API work.
