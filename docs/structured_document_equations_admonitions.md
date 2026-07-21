# Structured-Document Equation And Admonition Mapping

Date: 2026-07-21
Status: Phase 13E2 implemented as a Python contract API

## Purpose

Phase 13E2 maps conservative equation evidence and explicit-label admonition
evidence into the root `equations` and `admonitions` collections of the
internal `techdoc-structured-document / 0.1.0` contract object.

The implementation is additive and contract-local. It does not alter PDF
extraction, OCR, reading order, block creation, chunking, current JSON output,
Markdown output, manifests, validation reports, validation gates, or CLI
behavior.

## Source Evidence

The mapper uses only parser objects already present in `Document.pages[].blocks`.

| Evidence | Contract root collection | Status |
| --- | --- | --- |
| `FormulaBlock` | `equations` | exact raw text plus optional `latex` notation |
| conservative paragraph math text | `equations` | expression text only, no math understanding |
| explicit `WARNING`, `CAUTION`, `NOTE`, `IMPORTANT`, `SAFETY NOTICE` labels | `admonitions` | exact label and body text |

Root entity IDs are deterministic and distinct from block IDs:

```text
<document_id>:e<sequence>
<document_id>:a<sequence>
```

Existing block IDs remain unchanged and are referenced through
`source_block_ids` and `source_span.source_block_ids`.

## Equation Policy

Equation detection is intentionally conservative. It accepts `FormulaBlock`
evidence and narrow single-line equation-like paragraph evidence with an
operator and lettered operands. It preserves exact `raw_text`, optional explicit
equation labels, page refs, source spans, source block references, optional
bounding boxes, and section IDs/paths when hierarchy enrichment assigned them.

The mapper does not parse mathematical meaning, convert equations into prose,
solve equations, normalize plain equation text, infer variable definitions, or
emit confidence values. `FormulaBlock.latex` is emitted as
`normalized_representation` only when already present.

Known false-positive guards include metadata-like text such as revisions, page
labels, ordinary prose with equation signs, table/figure blocks, heading blocks,
and admonition text.

## Admonition Policy

Admonition detection requires an explicit label at the start of a supported
paragraph block. Supported labels are:

- `WARNING`
- `CAUTION`
- `NOTE`
- `IMPORTANT`
- `SAFETY NOTICE`

The mapper preserves `raw_label` exactly, including punctuation when present,
and maps the normalized type to validator-compatible values. Body text is
preserved without rewriting safety wording. Same-block labels such as
`WARNING: ...` use the text after the label as body text. Label-only blocks may
collect a bounded number of immediately following same-page paragraph blocks.

The mapper does not infer safety severity, classify bold or typography-only
text, detect admonitions inside tables or figures, rewrite warnings, or emit
confidence values. Prose such as "Warnings and limitations", "Important
dimensions", or "See note 4" is intentionally not treated as an admonition.

## Compatibility

The Phase 13E2 fixture is:

```text
tests/fixtures/structured_document/mapped_structured_document_with_equations_admonitions.json
```

The focused test module is:

```text
tests/test_structured_document_equations_admonitions.py
```

Existing parser output and manifest tests remain responsible for proving that
current output packages do not gain structured-document root fields unless a
future scoped phase adds explicit CLI/export integration.

## Remaining Gaps

- Equation detection remains candidate-level and conservative.
- Formula discovery from PDF layout is not implemented.
- Mathematical semantics, variable extraction, and equation relationships are
  not implemented.
- Admonition body grouping is bounded and same-page only.
- Safety severity inference is not implemented.
- Cross-reference mapping and confidence policy are handled separately by Phase
  13F.
- Structured-document CLI and manifest output remain future work.
