# Structured-Document Cross-Reference And Confidence Policy

Date: 2026-07-22
Status: Phase 13F implemented as a Python contract API; Phase 13G optional export implemented

## Purpose

Phase 13F maps explicit textual cross-reference evidence into the root
`cross_references` collection of the internal
`techdoc-structured-document / 0.1.0` contract object and defines the confidence
field policy used by structured-document mapping.

The implementation is additive and contract-local. It does not alter PDF
extraction, OCR, reading order, block creation, chunking, current JSON output,
Markdown output, validation reports, validation gates, or default CLI behavior.
Phase 13G can write reference records into an optional structured-document
artifact and register that artifact in the manifest when requested.

## Source Evidence

Cross-reference detection uses only paragraph or unknown blocks already present
in `Document.pages[].blocks`. It ignores raw `TextBlock`, `HeadingBlock`,
`TableBlock`, `TableRegionBlock`, `FigureBlock`, `FormulaBlock`, and explicit
same-block admonitions.

Detection requires an explicit introductory phrase:

- `see`
- `refer to`
- `in accordance with`
- `as specified in`
- `as described in`
- `according to`

Supported target forms include sections, clauses, paragraphs, tables, figures,
equations, appendices, annexes, chapters, AMC/GM clauses, and external document
IDs. Multiple references in one source block are preserved as separate records
when they appear in an explicit connected reference phrase.

## Resolution Policy

Root reference IDs are deterministic document-local sequence IDs:

```text
<document_id>:r<sequence>
```

Each record preserves exact `raw_text`, `raw_reference_text`,
`reference_type`, `target_identifier`, source block IDs, source span, page refs,
and section refs when present.

Resolution uses only exact local evidence already emitted into the contract:

- sections by section number, clause identifier, appendix/annex/chapter label,
  or AMC/GM clause identifier
- tables by root table ID, caption label, or exact text label
- figures by root figure ID, caption/source-caption label, or exact text label
- equations by root equation ID, equation label, or raw equation label

Supported statuses are:

| Status | Meaning |
| --- | --- |
| `resolved` | Exactly one local target was found and `target_id` is emitted. |
| `unresolved` | A local target type was explicit but no local target matched. |
| `external` | The reference points to an external document identifier. |
| `ambiguous` | More than one local target matched the exact identifier. |
| `not_attempted` | The reference type is unsupported or lacks a resolvable target identifier. |

The mapper does not use fuzzy matching, external lookup, PDF links, bookmarks,
semantic similarity, or inferred relationships. It never fabricates `target_id`.

## Confidence Policy

Confidence helpers live in:

```text
src/techdoc_parser/contracts/structured_document_confidence.py
```

The policy is omission-first:

- current `SourceLocation.confidence` is not mapped because native PyMuPDF
  values are placeholder extraction evidence
- OCR confidence is mapped only if a source explicitly identifies OCR and
  carries a numeric confidence value
- structure, classification, provenance, and general confidence fields remain
  absent until a real evidence source exists
- confidence values must be numeric in the inclusive range `0.0..1.0`
- booleans, strings, and out-of-range numbers are rejected

The focused Phase 13F synthetic fixture intentionally contains no confidence
fields, proving placeholder confidence is not promoted.

## Compatibility

The Phase 13F fixture is:

```text
tests/fixtures/structured_document/mapped_structured_document_with_references_confidence.json
```

The focused test module is:

```text
tests/test_structured_document_references_confidence.py
```

Existing parser output and manifest tests remain responsible for proving that
current output packages do not gain structured-document root fields unless
explicit CLI/export integration is requested.

## Remaining Gaps

- PDF internal links and bookmarks are not captured.
- Fuzzy reference resolution is intentionally not implemented.
- External document references are identified but not resolved.
- Character-offset spans are not available.
- True confidence models are not implemented.
- Formal AviationRAG compatibility gating remains Phase 13H.
