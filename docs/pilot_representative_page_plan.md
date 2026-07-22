# Pilot Representative-Page Proposal

Phase 13I-b1 proposes representative pages for owner review before any
approved-document source-accuracy pilot. Page numbers are planning references
only. No source text, extracted images, OCR output, or PDF content is committed.

Selection is deterministic and metadata-only. The proposal favors ordinary text,
middle-of-document coverage, document start/end coverage, multi-column or
complex layout, rotated/landscape pages, tables, figure captions, equations,
admonitions, procedures, cross-references, appendix or annex indicators,
numbered clauses, dense pages, and blank or low-text pages.

## Priority Meanings

| Priority | Meaning |
| --- | --- |
| `P0` | Highest-value pages for initial owner approval and pilot spot checks. |
| `P1` | Supplemental pages that cover important structures. |
| `P2` | Lower-priority edge coverage for end pages, dense pages, or low-text pages. |

The local proposal contains 80 pages: 32 `P0`, 32 `P1`, and 16 `P2`.

## Proposed Pages

| Filename | Proposed pages |
| --- | --- |
| `Aircraft_System_Safety_Military_Civil_Aeronautical_Applications.pdf` | P0: 3, 18, 52, 106; P1: 4, 5, 9, 10; P2: 11, 12 |
| `Airplane_Maintenance_Manual_CIRRUS_Design_SR22.pdf` | P0: 1, 3, 7, 468; P1: 2, 31, 60, 92; P2: 325, 1082 |
| `Airworthiness_An_Introduction_Aircraft_Certification_And_Operations.pdf` | P0: 1, 22, 44, 60; P1: 2, 6, 7, 33; P2: 9, 12 |
| `FAA_Order_4040_26B.pdf` | P0: 1, 7, 29, 38; P1: 2, 3, 5, 10; P2: 12, 19 |
| `Flight_Test_RM_AG_300_V32.pdf` | P0: 1, 4, 33, 131; P1: 5, 20, 30, 41; P2: 2, 209 |
| `Introduction_Aircraft_Stability_And_Control_Course_Notes_M&AE_5070.pdf` | P0: 1, 3, 10, 48; P1: 5, 7, 8, 9; P2: 13, 17 |
| `Introduction_Flight_Test_Engineering_RTO-AGARDograph_300_V14.pdf` | P0: 1, 23, 145, 453; P1: 4, 5, 6, 8; P2: 9, 24 |
| `MIL-STD-882E.pdf` | P0: 1, 14, 17, 33; P1: 2, 7, 16, 19; P2: 5, 106 |

## Coverage Roles

| Filename | Covered roles |
| --- | --- |
| `Aircraft_System_Safety_Military_Civil_Aeronautical_Applications.pdf` | ordinary text, printed page labels, table, numbered clause, appendix/annex, procedure, admonition, figure caption, cross-reference, equation, multi-column reading order, complex/rotated layout |
| `Airplane_Maintenance_Manual_CIRRUS_Design_SR22.pdf` | ordinary text, blank/low-text pages, table, multi-column reading order, complex layout, admonition, procedure, appendix/annex, figure caption, equation, dense pages, cross-reference |
| `Airworthiness_An_Introduction_Aircraft_Certification_And_Operations.pdf` | ordinary text, table, numbered clause, admonition, appendix/annex, figure caption, cross-reference, procedure, multi-column reading order, complex layout, landscape/rotated page |
| `FAA_Order_4040_26B.pdf` | table, numbered clause, cross-reference, appendix/annex, figure caption, complex layout, admonition, blank/low-text page, procedure, multi-column reading order, rotated page, ordinary text |
| `Flight_Test_RM_AG_300_V32.pdf` | ordinary text, table, blank/low-text page, complex layout, dense text, procedure, appendix/annex, figure caption, admonition, cross-reference, equation, multi-column reading order |
| `Introduction_Aircraft_Stability_And_Control_Course_Notes_M&AE_5070.pdf` | ordinary text, complex layout, reading order, procedure, admonition, numbered clause, figure caption, equation, multi-column reading order, table, appendix/annex |
| `Introduction_Flight_Test_Engineering_RTO-AGARDograph_300_V14.pdf` | ordinary text, table, admonition, numbered clause, appendix/annex, cross-reference, procedure, figure caption, complex layout, equation, dense text, multi-column reading order |
| `MIL-STD-882E.pdf` | ordinary text, table, cross-reference, numbered clause, procedure, dense text, appendix/annex, figure caption, multi-column reading order, admonition, complex layout |

## Owner Approval Checklist

- Confirm the approved corpus contains exactly these eight local PDFs.
- Confirm the local ignored report hashes in `output/pilot_corpus_inventory.json`
  are acceptable for owner-side verification.
- Confirm `Airplane_Maintenance_Manual_CIRRUS_Design_SR22.pdf` can proceed
  despite the uncertain text-mode classification, or defer it from the first
  pilot slice.
- Confirm the P0 pages are acceptable for Phase 13I-b2.
- Confirm whether any P1 or P2 pages should be promoted before the pilot.
- Confirm no OCR, parser repair, external API analysis, embeddings, or
  AviationRAG runtime ingestion is authorized by this approval.

## Proposed Pilot Scope

Recommended first Phase 13I-b2 scope:

- Use only owner-approved `P0` pages at first.
- Include all eight documents only if the SR22 uncertain text-mode finding is
  accepted by the owner.
- Treat page-level outcomes as manual source-accuracy observations, not parser
  repairs.
- Keep all generated local evidence under ignored `output/` unless a later
  sanitized summary is explicitly approved for commit.
