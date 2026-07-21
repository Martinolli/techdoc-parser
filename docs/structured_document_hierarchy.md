# StructuredDocument Section Hierarchy

Date: 2026-07-21
Status: Phase 13D implemented as a Python contract API

## Purpose

Phase 13D adds durable section hierarchy and section source-span enrichment to
the internal `techdoc-structured-document / 0.1.0` mapper. The implementation is
contract-local and pure: it reads existing parser `HeadingBlock` evidence and
returns new contract records.

It does not change parser extraction, heading detection, OCR, reading-order
detection, block creation, normalization, chunking, current JSON, Markdown,
manifest, validation, gate, or CLI behavior.

## Implemented Module

```text
src/techdoc_parser/contracts/structured_document_hierarchy.py
```

The mapper uses this module by default through:

```text
map_document_to_structured_document(..., include_sections=True)
```

Set `include_sections=False` to preserve the Phase 13C no-section mapper shape.

## Evidence Used

The hierarchy builder uses only:

- `HeadingBlock.text`
- `HeadingBlock.normalized_text`
- `HeadingBlock.level`
- the mapped heading block ID
- mapped block order
- mapped block source spans

It does not use chunk metadata as authoritative section evidence, and it does
not inspect AviationRAG.

## Hierarchy Decisions

| Scenario | Decision |
| --- | --- |
| First heading is level 2 or deeper | Emit it as a root section and preserve its level. |
| Child heading | Parent is the nearest preceding section with a lower level. |
| Same-level heading | Emit as sibling; close deeper active sections. |
| Skipped levels | Do not fabricate intermediary sections. |
| Blocks before first heading | Leave `section_id` absent. |
| Heading block | Assign to its own section. |
| Blocks after heading | Assign to the active section until another heading changes context. |
| Empty pages | Preserve page records; create no sections or block links. |

## Heading Text Policy

Raw heading text is preserved in `raw_heading`. Normalized heading text is
emitted as `normalized_heading` only when it exists and normalized-text mapping
is enabled. Section `path` items use the validator-compatible display form
`section_number + title`; this may omit source punctuation such as the dot in
`1. Heading` because the exact source form remains in `raw_heading`.

The parser recognizes only narrow source-provided prefixes:

- numeric section numbers such as `5`, `5.1`, and `5.1.1(a)`
- appendix and annex labels such as `APPENDIX A`
- AMC/GM-style clause identifiers such as `AMC1 145.A.30(e)`

Unnumbered headings are valid sections. No section number, clause identifier,
or title is fabricated.

## Source-Span Policy

Section source spans are derived from blocks directly assigned to the section.
The span includes:

- `page_start` and `page_end`
- `pdf_page_index_start` and `pdf_page_index_end`
- ordered `source_block_ids`
- a common `extraction_method` when direct blocks agree

Multi-block section spans do not merge bounding boxes. A section-level `bbox` is
emitted only when the section has one directly assigned block with a real block
bounding box.

## Compatibility

The Phase 13D fixture is:

```text
tests/fixtures/structured_document/mapped_structured_document_with_sections.json
```

The Phase 13C no-section fixture remains covered with `include_sections=False`.
As of Phase 13F, root table, figure-caption, equation, admonition, and
cross-reference entities reuse the same block-level `section_id` and section
path assigned by this hierarchy builder when source evidence is assigned to a
section.
