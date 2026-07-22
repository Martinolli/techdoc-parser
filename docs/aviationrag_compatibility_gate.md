# AviationRAG Compatibility Gate

Date: 2026-07-22
Status: Phase 13H implemented

## 1. Purpose

Phase 13H adds a formal offline compatibility gate for a Phase 13G
`techdoc-structured-document / 0.1.0` artifact, its manifest, and the exact
source file bytes. The gate is a contract check only. It does not parse source
documents, import AviationRAG, modify AviationRAG, run ingestion, generate
embeddings, use Astra, use FAISS, or process proprietary corpora.

The implementation lives in:

```text
src/techdoc_parser/compatibility/aviationrag_gate.py
tools/compatibility/run-aviationrag-compatibility-gate.py
```

Tests use synthetic files and fake validator adapters so the test suite does
not require a sibling AviationRAG checkout.

## 2. Inputs

The CLI requires:

- `--artifact`: a structured-document JSON artifact written by Phase 13G
- `--manifest`: a manifest containing the additive `artifacts[]` entry
- `--source`: the exact source file whose bytes are governed
- `--aviationrag-root`: a local AviationRAG repository root

Optional inputs:

- `--comparison-artifact`: a second generated artifact for byte-for-byte
  determinism checking
- `--approve-warning`: repeatable AviationRAG warning-code approval
- `--report`: compatibility report output path
- `--allow-report-write`: required before a compatibility report is written

## 3. Command

```powershell
python tools/compatibility/run-aviationrag-compatibility-gate.py `
  --artifact output/structured_document.json `
  --manifest output/manifest.json `
  --source input/synthetic.pdf `
  --aviationrag-root "C:\Users\Aspire5 15 i7 4G2050\ProjectRAG\AviationRAG" `
  --comparison-artifact output/structured_document_repeat.json `
  --report output/aviationrag_compatibility_gate.json `
  --allow-report-write
```

The tool prints a concise result to stdout and returns:

- `0` for `PASS`
- `2` for `REVIEW`
- `1` for `FAIL`

## 4. External Validator Adapter

The gate runs the sibling AviationRAG validator through `subprocess`:

```text
tools/chunking/validate-structured-document.py
```

The adapter supplies a temporary report path outside AviationRAG and passes
`--allow-report-write` only for that temporary path. The gate parses the
validator report fields:

- `schema_name`
- `schema_version`
- `document_id`
- `is_valid`
- `error_count`
- `warning_count`
- `summary`
- `issues`

Raw validator stdout and stderr are captured by the adapter but are not emitted
in the compatibility report, preventing temporary path leakage.

## 5. Gate Checks

The gate checks:

- Manifest registration: exactly one `structured_document` artifact entry,
  matching path, `outputs.structured_document`, media type, schema identity, and
  document ID.
- Source checksum: manifest `source_sha256`, artifact
  `document.source_hash`, and the actual source bytes must match lowercase
  SHA-256.
- Artifact checksum: manifest `artifact_sha256` must match the actual artifact
  bytes.
- Metadata consistency: root schema, parser identity, document ID, source
  filename, and media type.
- AviationRAG validator result: validator errors fail the gate.
- Warning policy: unapproved validator warnings fail; explicitly approved
  warnings produce `REVIEW`.
- Table count interpretation: validator table counts are compared with root
  table entities and table blocks so known count semantics are recorded.
  Known root-entity, block-only, and aggregate interpretations are reported;
  unknown interpretations require review.
- Cross-reference integrity: `resolved` references must target an emitted local
  entity; `unresolved` and `ambiguous` records must not claim a `target_id`;
  `external` references do not require a local target.
- Confidence policy: confidence-like fields must be numeric in `0.0..1.0`;
  generic `confidence` fields are reported for review; booleans and
  out-of-range values fail.
- Determinism: a comparison artifact is required for `PASS`; when absent, the
  gate returns `REVIEW`.

## 6. Outcomes

`PASS` means every compatibility check passed, the AviationRAG validator
reported no errors or warnings, and determinism was checked.

`REVIEW` means no check failed, but at least one review condition exists, such
as a missing comparison artifact, an explicitly approved validator warning, or
a generic confidence field.

`FAIL` means at least one contract check failed, the validator reported errors,
or unapproved validator warnings were present.

The gate is structural compatibility evidence only. It does not prove parser
accuracy, heading accuracy, table reconstruction quality, visual figure
understanding, or suitability for a particular controlled-document corpus.

## 7. Boundaries

Phase 13H does not:

- Add AviationRAG as a dependency.
- Import AviationRAG from normal parser modules.
- Modify AviationRAG files.
- Write reports inside AviationRAG.
- Change `techdoc-parse` defaults or current output shapes.
- Repair structured-document artifacts, manifests, checksums, references, or
  confidence fields.
- Add ingestion, embeddings, Astra, FAISS, RAG runtime code, or corpus
  processing.
