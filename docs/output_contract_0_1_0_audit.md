# techdoc-parser Output Contract and 0.1.0 Schema Alignment Audit

## 1. Purpose

This audit documents the current `techdoc-parser` output contract and compares it
against the intended `techdoc-structured-document / 0.1.0` target. It is a
planning and integration reference for deciding what can be consumed now by
AviationRAG and what remains future work.

This document describes current emitted artifacts and model coverage only. It
does not define new parser behavior.

## 2. Current Parser Output Package

| Output | Purpose | Intended Consumer | Format | Current Status |
| --- | --- | --- | --- | --- |
| `document.json` | Full structured parse output with pages, blocks, source locations, metadata, and page status flags. | Downstream tools, debugging, audit workflows. | Machine-readable JSON | Implemented |
| `chunks.json` | RAG-oriented semantic chunks with source references and section metadata. | RAG ingestion pipeline, search/index preparation. | Machine-readable JSON | Implemented |
| `validation.json` | Validation report with parsing/chunking quality issues and summary metrics. | Automation, QA checks, integration gates. | Machine-readable JSON | Implemented |
| `gate.json` | Combined validation report and ingestion-readiness decision. | Automation, pipeline orchestration, ingestion gate checks. | Machine-readable JSON | Implemented |
| `validation_summary.md` | Human-readable validation gate summary with decision, counts, metrics, review reasons, and issues. | Human reviewers, project planning, release checks. | Human-readable Markdown | Implemented |
| Semantic Markdown output | Readable semantic document view without raw text-block duplicates. | Human inspection, debugging, review. | Human-readable Markdown | Implemented as exporter API |

## 3. Current Internal Model Coverage

| Object / Concept | Current Status | Notes |
| --- | --- | --- |
| Document | Implemented | Contains `id`, `source_path`, metadata, and pages. |
| DocumentMetadata | Implemented | Supports title, author, subject, keywords, producer, and creator. |
| Page | Implemented | Includes page number, dimensions, OCR/native-text flags, raw text blocks, and generic blocks. |
| SourceLocation | Implemented | Tracks document path, page number, optional bounding box, extraction method, and confidence value. |
| BoundingBox | Implemented | Stores rectangular source coordinates. |
| Block | Implemented | Base block model with id, source, block type, text, and normalized text. |
| TextBlock | Implemented | Native PDF text block with page-furniture flags. |
| ParagraphBlock | Implemented | Candidate paragraph derived from text blocks. |
| HeadingBlock | Partial | Heuristic candidate heading detection exists; not a final section hierarchy. |
| TableBlock | Partial | Candidate-level table fragments; no robust row/column reconstruction. |
| TableRegionBlock | Partial | Conservative grouping for nearby table candidates; still candidate-level. |
| FigureBlock | Partial | Figure caption candidates exist; full figure/image extraction is not implemented. |
| FormulaBlock | Placeholder | Model exists, but formula candidate detection is not implemented yet. |
| Chunk | Implemented | Semantic RAG chunk with source references and metadata. |
| ValidationIssue | Implemented | Represents info, warning, and error findings. |
| ValidationReport | Implemented | Aggregates validation issues, counts, and summary metrics. |
| ValidationDecision | Implemented | Converts validation report into pass/review/fail gate status. |
| Reference | Missing | No reference or cross-reference model yet. |
| ConfidenceScore | Missing | No dedicated confidence score model yet. SourceLocation has optional confidence. |
| Section hierarchy | Partial | Chunk metadata is section-aware, but there is no full section tree or parent-child hierarchy. |

## 4. Current JSON Document Output

`document.json` is the full structured parser output. It currently includes:

- document id
- source path
- document metadata
- pages
- page dimensions where available
- `has_native_text` and `requires_ocr` flags
- `text_blocks` for native extracted text
- generic `page.blocks` containing raw text and derived/candidate block objects
- source locations with page number, extraction method, confidence, and bounding boxes where available
- block types and block-specific metadata
- page-furniture flags on `TextBlock`

Small illustrative shape:

```json
{
  "id": "manual",
  "source_path": "manual.pdf",
  "metadata": {
    "title": "Manual"
  },
  "pages": [
    {
      "page_number": 1,
      "has_native_text": true,
      "requires_ocr": false,
      "blocks": [
        {
          "id": "text-1",
          "block_type": "text",
          "text": "Example text",
          "source": {
            "document_path": "manual.pdf",
            "page_number": 1
          }
        }
      ],
      "text_blocks": [
        {
          "id": "text-1",
          "block_type": "text",
          "text": "Example text"
        }
      ]
    }
  ]
}
```

The document output is useful for traceability and debugging, but it is not yet
versioned with a schema identifier.

## 5. Current Chunk JSON Output

`chunks.json` is the current RAG-oriented output. It contains:

- `chunk_count`
- `chunks` list
- chunk id
- document id
- chunk text
- source page numbers
- source block ids
- source text block ids
- chunk type
- metadata
- section metadata when available:
  - `section_title`
  - `section_path`
  - `section_level`

Chunks are generated from the semantic block view, not directly from raw text
blocks. They are cleaned of page/document furniture, preserve source references,
and include lightweight section context from preceding headings. They are
section-aware, but they are not backed by a full section tree yet.

## 6. Current Validation Output

The validation output package includes `validation.json`, `gate.json`, and
`validation_summary.md`.

`validation.json` contains a `ValidationReport`:

- document id
- source path
- issue count
- error count
- warning count
- info count
- ordered issue list
- summary metrics such as page count, chunk count, OCR pages, furniture-only
  pages, missing semantic pages, empty/short/long chunks, missing source
  references, and warning/error flags

`gate.json` combines the report with a `ValidationDecision`:

- `pass`, `review`, or `fail`
- `can_ingest`
- reason
- issue counts
- review reasons
- full validation report

`validation_summary.md` is the human-readable equivalent of the gate output. It
includes decision status, ingestion readiness, reason, document info, summary
metrics, issue counts, review reasons, and an issue table.

Validation severity behavior:

- `error`: blocks automated ingestion and produces `fail`.
- `warning`: requires review and produces `review`.
- `info`: does not block ingestion by itself.

## 7. Alignment Against techdoc-structured-document / 0.1.0

| Target 0.1.0 Field / Capability | Current Support | Gap | Priority |
| --- | --- | --- | --- |
| Document identity | Supported | No explicit schema version in output. | High |
| Source path | Supported | None for current MVP. | High |
| Document metadata | Supported | Limited to PDF metadata fields. | Medium |
| Pages | Supported | No page-level layout model beyond dimensions and blocks. | High |
| Native text blocks | Supported | Native-text PDFs only. | High |
| Normalized text | Supported | Normalization is conservative and not exhaustive. | Medium |
| Page numbers | Supported | None for current MVP. | High |
| Bounding boxes | Supported | Available where PDF extraction provides them. | High |
| Headings | Partially supported | Heuristic candidate detection, no validated hierarchy. | Medium |
| Paragraphs | Partially supported | Basic grouping, not full cross-block paragraph reconstruction. | Medium |
| Tables | Partially supported | Candidate-level only; no robust row/column reconstruction. | Medium |
| Table regions | Partially supported | Conservative grouping, still candidate-level. | Medium |
| Figures/captions | Partially supported | Caption candidates only; no image extraction or full figure regions. | Low |
| Formulas | Not supported | Model exists, but detection is not implemented. | Low |
| References/cross-references | Not supported | No reference model or graph. | Low |
| Source traceability | Supported | Traceability is present for blocks and chunks. | High |
| Section hierarchy | Partially supported | Chunk metadata has section context, but no full tree. | Medium |
| Chunks | Supported | Basic semantic chunks; no embedding or vector export. | High |
| Chunk section metadata | Supported | Lightweight metadata only. | High |
| Validation report | Supported | Current checks are conservative and MVP-focused. | High |
| Ingestion gate decision | Supported | Decision is based on current validation severities. | High |
| Human-readable validation summary | Supported | Markdown summary is implemented. | Medium |
| Confidence scores | Partially supported | `SourceLocation.confidence` exists; no dedicated confidence model or scoring strategy. | Low |
| OCR status | Supported | Pages expose native-text and OCR-required flags; OCR itself is not implemented. | High |

## 8. Missing Capabilities Before AviationRAG D.4c

### Must have before D.4c

- Stable current output contract
- Chunk JSON
- Validation gate
- Source references
- Basic section metadata

These are present now for native-text PDF pilot ingestion.

### Should have soon

- Schema version field in exported outputs
- Parser version metadata in exported outputs
- Output manifest JSON summarizing generated files and gate decision
- README usage for the full output package
- Architecture documentation for the current pipeline

### Can wait

- Full section tree
- Advanced table reconstruction
- Formula recognition
- Dedicated confidence scoring
- OCR adapters
- Cross-reference graph
- Multi-column layout handling

## 9. Recommended Next Implementation Steps

1. Add `schema_version` and `parser_version` metadata to exported outputs.
2. Add an output manifest JSON summarizing generated files and gate decision.
3. Document CLI full-package usage in `README.md`.
4. Add architecture overview and pipeline diagram documentation.
5. Later, implement either section hierarchy or confidence scoring based on the next AviationRAG integration need.

## 10. Conclusion

`techdoc-parser` is now MVP-ingestion ready for native-text PDFs. It can produce
structured document JSON, semantic chunk JSON, validation reports, ingestion gate
decisions, and human-readable validation summaries with source traceability.

It is suitable for pilot AviationRAG ingestion with known limitations. It is not
yet a complete technical-document understanding engine: advanced table
reconstruction, full section hierarchy, OCR, formula recognition, confidence
scoring, and cross-reference modeling remain future work.
