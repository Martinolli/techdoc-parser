# StructuredDocument Export

Date: 2026-07-22
Status: Phase 13G implemented

## 1. Purpose

Phase 13G exposes the existing `techdoc-structured-document / 0.1.0` mapper as
an optional parser artifact. Existing default JSON, Markdown, chunk,
validation, gate, and manifest outputs remain unchanged unless the caller
explicitly requests the structured-document output.

## 2. Public Python Construction API

Use the pure construction API when a parsed `Document` already exists and no
file output is wanted:

```python
from techdoc_parser.contracts import build_structured_document_artifact

structured = build_structured_document_artifact(
    document,
    document_id="SYNTHETIC-DOC-001",
    document_title="Synthetic Export Guide",
)
```

The API is provisional and versioned by the emitted
`techdoc-structured-document / 0.1.0` schema. It reuses the existing mapper,
does not mutate the parser document, does not write files, and does not infer
document-control metadata from filenames or timestamps.

## 3. Public File Export API

Use the file API when the source file bytes and output path are known:

```python
from techdoc_parser.exporters import export_structured_document

artifact = export_structured_document(
    document,
    source_path="input/synthetic.pdf",
    output_path="output/structured_document.json",
    document_id="SYNTHETIC-DOC-001",
)
```

The returned `StructuredDocumentArtifact` includes:

- `output_path`
- `schema_name`
- `schema_version`
- `source_sha256`
- `artifact_sha256`
- `document_id`

## 4. CLI Option

```powershell
techdoc-parse input/synthetic.pdf `
  --output output/document.json `
  --structured-document-output output/structured_document.json `
  --structured-document-id SYNTHETIC-DOC-001
```

Optional explicit metadata flags are:

- `--document-title`
- `--document-number`
- `--document-revision`
- `--document-issue`
- `--document-effective-date`

The `--structured-document-id` flag is required only when
`--structured-document-output` is supplied. Structured-document metadata flags
are rejected when no structured-document output is requested.

## 5. Checksum Ownership

`techdoc-parser` owns source checksum calculation for this artifact. The helper
`compute_source_sha256(path)` reads the exact source file bytes in binary chunks
with `hashlib.sha256` and returns the lowercase hexadecimal digest without a
prefix. It does not hash extracted text, filenames, timestamps, or metadata.

The structured-document JSON stores this digest in `document.source_hash`.
Downstream consumers should compare it against the exact source bytes they
intend to govern.

The file export API also returns `artifact_sha256`, computed from the exact
written structured-document JSON bytes. The manifest records both source and
artifact digests when the structured-document artifact is registered.

## 6. Deterministic Output

Structured-document JSON uses the contract serializer with
`ensure_ascii=False`, indentation of two spaces by default, UTF-8 encoding, and
a final newline. Repeated exports with the same parsed document, metadata, and
source bytes produce identical artifact bytes.

The artifact does not include generation timestamps, absolute output paths,
temporary filenames, hostnames, usernames, environment values, or random IDs.
The source filename inside the contract is basename-only.

## 7. Atomic And Fail-Safe Writing

`write_structured_document()` serializes the complete payload before touching
the destination. It writes to a sibling temporary file, flushes and closes it,
then uses atomic replacement where supported. Handled failures clean up the
temporary file. Serialization failure leaves the destination unchanged.

Parent directories are created automatically, matching the existing exporter
convention.

## 8. Overwrite And Path Safety

Structured-document output uses a stricter policy than legacy exporters:
existing destinations are rejected by default. Python callers must pass
`overwrite=True`; CLI callers must pass `--structured-document-overwrite`.

The file API rejects using the input source path as the output path and rejects
directory output paths. Relative paths are written exactly as supplied; manifest
paths follow the same string convention as current output paths.

## 9. Manifest Registration

When both `--structured-document-output` and `--manifest-output` are supplied,
the manifest adds:

- `outputs.structured_document`
- an `artifacts[]` record with `artifact_type: structured_document`
- `media_type: application/json`
- schema name and version
- source SHA-256
- artifact SHA-256
- document ID

No manifest entry is created if structured-document writing fails. Manifest
shape is unchanged when no structured-document artifact is requested.

## 10. Retention Policy

The structured-document output is a durable parser artifact. Retain it with the
source document and manifest because it supports audit, reproducibility,
downstream re-chunking, parser-version comparison, and evidence traceability.
It is not merely a transient intermediate file.

## 11. Failure Semantics

If structured-document writing fails, the CLI returns non-zero and no manifest
success entry is written. If the structured-document artifact succeeds but a
later manifest write fails, the CLI reports the failure honestly and leaves the
valid structured-document artifact in place. Phase 13G does not add an
all-or-nothing transaction framework.

## 12. Backward Compatibility And Independence

Existing parser APIs, current CLI commands, current default output filenames,
JSON output, Markdown output, validation reports, ingestion gates, and manifest
shape without a structured-document artifact remain unchanged.

The output is intended for validated downstream consumers such as AviationRAG,
but `techdoc-parser` does not import AviationRAG, run the AviationRAG validator
as part of normal export, upload artifacts, generate embeddings, or perform RAG
ingestion.

## 13. Known Limitations

- Formal AviationRAG compatibility gating remains Phase 13H.
- Real parser accuracy evaluation remains Phase 13I.
- Printed page-label extraction is not implemented.
- Full table reconstruction is not implemented.
- Figure asset extraction and visual understanding are not implemented.
- Cross-document reference resolution is not implemented.
- Confidence fields remain absent unless truthful numeric evidence exists.
