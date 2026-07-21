# Legacy Repository Structure and Cleanup-Readiness Audit

Date: 2026-07-21

Repository commit audited: `c6e2a84`

Audit version: 1.0

Scope: M.3 documentation-only audit of the `techdoc-parser` repository after the
Phase 13D structured-document contract hierarchy work.

## 17.1 Executive Assessment

Cleanup is useful but non-blocking.

The active parser implementation is compact and internally connected. The source
tree has no tracked runtime module that is clearly orphaned, duplicated, or safe
to delete without compatibility review. The repository does contain historical
planning and audit documents whose older statements have been superseded by
later phases, and it contains ignored local run artifacts that may be removed
locally after owner review.

Recommended next phase: Phase 13E1 - table and figure-caption mapping from
truthful parser evidence.

## 17.2 Audit Method

This audit reviewed:

- Git branch, tag, stash, and recent commit state.
- Tracked file inventory from `git ls-files`.
- Ignored local artifacts from `git status --ignored --short`.
- Package configuration and public entry points in `pyproject.toml`.
- Runtime package exports, CLI flow, parser flow, exporters, validation, and
  contract modules.
- Test modules and structured-document fixtures.
- Current documentation, older project planning documents, and generated output
  locations.

No files were removed, moved, renamed, archived, or cleaned up during this
audit.

## 17.3 Repository State Snapshot

| Area | Finding |
| --- | --- |
| Current branch | `main` |
| Upstream | `origin/main` |
| HEAD | `c6e2a84 feat(contract): add section hierarchy and source spans` |
| Remote | `https://github.com/Martinolli/techdoc-parser.git` |
| Remote branches | `origin/HEAD -> origin/main`, `origin/main` |
| Tags | `v0.1.0-mvp` |
| Stashes | none |
| Tracked files | 73 |
| Tracked source files under `src` | 31 |
| Tracked test and fixture files under `tests` | 29 |
| Tracked docs files under `docs` | 8 before this audit |
| Untracked non-ignored files | none before this audit |

Ignored local artifacts observed:

- `.venv/`
- `.mypy_cache/`
- `.pytest_cache/`
- `.ruff_cache/`
- `__pycache__/`
- `input/`
- `output/`
- `check_techdoc_parse_result.py`

The ignored `input/` directory contains local PDF inputs. Their contents were not
processed for this audit. The ignored `output/` directory contains generated
parser outputs for a local run.

## 17.4 File and Directory Classification Matrix

| Path | Classification | Evidence | Compatibility risk | Recommended action | Recommended timing |
| --- | --- | --- | --- | --- | --- |
| `.gitignore` | must retain | Ignores Python, build, cache, environment, and local parser run artifacts. | Medium | retain | now |
| `pyproject.toml` | must retain | Defines package metadata, dependencies, CLI entry point, Ruff, pytest, and mypy settings. | High | retain | now |
| `README.md` | must retain | Current user-facing package, CLI, output package, and contract API documentation. | High | retain | now |
| `TODO.md` | must retain | Current project phase tracking and quality checklist. | Medium | retain | now |
| `PROJECTPLAN.md` | historical documentation | Broad historical roadmap; not the exact current package layout. | Low | archive later after canonical docs fully cover retained planning value | after 13E1 |
| `docs/architecture_pipeline_overview.md` | must retain | Current canonical architecture, package responsibilities, output artifacts, and integration boundary. | High | retain | now |
| `docs/structured_document_contract.md` | must retain | Current structured-document contract reference. | High | retain | now |
| `docs/structured_document_mapping.md` | must retain | Current parser-model to contract mapping reference. | High | retain | now |
| `docs/structured_document_hierarchy.md` | must retain | Current Phase 13D hierarchy behavior reference. | High | retain | now |
| `docs/aviationrag_structured_document_gap_analysis.md` | historical documentation | Phase 13A analysis updated through later phases; some older sections are superseded by later appended status. | Medium | document superseded sections or archive after replacement | after 13E1 |
| `docs/aviationrag_structured_document_mapping.json` | historical documentation | Gap-analysis mapping matrix with later updates. | Medium | retain until replaced by generated contract coverage matrix | after 13E1 |
| `docs/output_contract_0_1_0_audit.md` | historical documentation | Phase 12A audit; several findings were superseded by Phases 12B, 13B, 13C, and 13D. | Low | archive later or label as historical | after 13E1 |
| `docs/mvp_readiness_checklist.md` | historical documentation | MVP release checklist; useful but includes limitations now narrowed by later internal contract work. | Medium | refresh or label historical before next release checkpoint | after 13F |
| `src/techdoc_parser/__init__.py` | backward-compatibility layer | Re-exports public core models, `parse_document`, and version. | High | retain | now |
| `src/techdoc_parser/parser.py` | active runtime | Public `parse_document` path for PDF ingestion. | High | retain | now |
| `src/techdoc_parser/cli.py` | active CLI | Implements `techdoc-parse` and current output package orchestration. | High | retain | now |
| `src/techdoc_parser/core/` | active runtime | Core dataclasses and serializer methods used by parser, exporters, contracts, and tests. | High | retain | now |
| `src/techdoc_parser/ingestion/` | active runtime | `PDFLoader` and PDF metadata extraction. | High | retain | now |
| `src/techdoc_parser/structure/` | active runtime | Page furniture, heading, paragraph, table, table-region, figure, and semantic-block logic. | High | retain | now |
| `src/techdoc_parser/normalization/` | active runtime | Text normalization used by ingestion and structure detection. | Medium | retain | now |
| `src/techdoc_parser/chunking/` | active runtime | Semantic chunk generation and section metadata assignment. | High | retain | now |
| `src/techdoc_parser/validation/` | active validation | Report-only quality findings and gate decision mapping. | High | retain | now |
| `src/techdoc_parser/exporters/` | active exporter | JSON, Markdown, validation, gate, chunk, and manifest export helpers. | High | retain | now |
| `src/techdoc_parser/contracts/` | active contract layer | Structured-document contract, mapper, and hierarchy enrichment API. | High | retain | now |
| `src/techdoc_parser/version.py` | backward-compatibility layer | Central schema/parser metadata used by exports and contracts. | High | retain | now |
| `src/techdoc_parser/py.typed` | must retain | PEP 561 marker for typed package consumers. | Medium | retain | now |
| `tests/` | active test support | 26 Python test modules cover CLI, exports, validation, parser, structure, chunking, and contracts. | High | retain | now |
| `tests/fixtures/structured_document/` | active test support | Synthetic contract fixtures used by structured-document tests. | High | retain | now |
| `examples/` | obsolete but uncertain | Local empty directory; not tracked. | Low | leave alone or remove locally after owner review | M.3b local cleanup |
| `input/` | generated artifact | Ignored local parser input directory. | Low | leave ignored; optionally clean locally after owner review | M.3b local cleanup |
| `output/` | generated artifact | Ignored local parser output directory. | Low | leave ignored; optionally clean locally after owner review | M.3b local cleanup |
| `.venv/` | generated artifact | Ignored virtual environment. | Low | leave ignored; optionally recreate locally when needed | local-only |
| `.mypy_cache/` | generated artifact | Ignored type-check cache. | Low | leave ignored; safe to delete locally | local-only |
| `.pytest_cache/` | generated artifact | Ignored pytest cache. | Low | leave ignored; safe to delete locally | local-only |
| `.ruff_cache/` | generated artifact | Ignored Ruff cache. | Low | leave ignored; safe to delete locally | local-only |
| `__pycache__/` | generated artifact | Ignored Python bytecode caches under source and tests. | Low | leave ignored; safe to delete locally | local-only |
| `check_techdoc_parse_result.py` | obsolete but uncertain | Ignored local helper for manual parser-output inspection. | Low | review before local removal; do not commit as-is | M.3b local cleanup |

## 17.5 Dependency and Import Findings

No tracked source module was identified as safe to remove now.

Findings:

- `techdoc_parser.cli` is reachable from the `techdoc-parse` entry point in
  `pyproject.toml` and is tested by CLI tests.
- `techdoc_parser.parser` is the public `parse_document` API path documented in
  the README and re-exported from the package root.
- `techdoc_parser.core.models` is mostly consumed through package re-exports;
  this is a compatibility layer, not an orphan.
- `techdoc_parser.structure` modules are connected through `PDFLoader`,
  semantic views, chunking, exporters, validation, and tests.
- `techdoc_parser.exporters` modules are active current-output paths.
- `techdoc_parser.validation.report` remains active and report-only.
- `techdoc_parser.contracts` is intentionally isolated from current CLI outputs
  but active through public contract tests and documentation.
- The package-level `__all__` exports create de facto API compatibility
  constraints even where direct internal imports are sparse.

## 17.6 Output-Path Findings

The canonical current CLI output package is:

- `document.json`
- `chunks.json`
- `validation.json`
- `gate.json`
- `validation_summary.md`
- `manifest.json`

The current CLI does not emit a structured-document artifact. Structured-document
serialization exists as an internal Python API under `techdoc_parser.contracts`.

No duplicate output implementation was found that is safe to remove now. The
current exporter modules separate responsibilities by artifact type:

- `json_exporter.py` covers document, chunks, validation, and gate JSON.
- `markdown_exporter.py` covers document Markdown, semantic Markdown, validation
  report Markdown, and gate Markdown.
- `manifest.py` covers output package manifest creation and writing.

The core model `to_json()` methods and exporter functions overlap intentionally:
the model methods define serializable shapes, while exporters own file-writing
and artifact-level metadata. Removing either would risk current consumers.

## 17.7 Test and Fixture Findings

The tracked test suite is active and broad for the current MVP surface:

- 26 Python test modules.
- Contract tests cover schema constants, serialization, mapper behavior, and
  hierarchy enrichment.
- CLI tests cover required output and optional output-package paths.
- Exporter tests cover document JSON, chunks JSON, manifest JSON, Markdown, and
  validation summaries.
- Parser and structure tests use generated temporary PDFs, not committed binary
  PDF fixtures.
- The three tracked structured-document JSON fixtures are synthetic and used for
  contract test coverage.

No tracked fixture was identified as safe to delete now.

## 17.8 Documentation Findings

Current canonical documentation:

- `README.md`
- `docs/architecture_pipeline_overview.md`
- `docs/structured_document_contract.md`
- `docs/structured_document_mapping.md`
- `docs/structured_document_hierarchy.md`
- `TODO.md`

Historical or partially superseded documentation:

- `PROJECTPLAN.md`
- `docs/output_contract_0_1_0_audit.md`
- `docs/mvp_readiness_checklist.md`
- `docs/aviationrag_structured_document_gap_analysis.md`
- `docs/aviationrag_structured_document_mapping.json`

The main documentation risk is not runtime behavior. It is reader confusion:
older documents accurately describe earlier phases but may contradict later
contract-layer status if read without phase context. The safest cleanup is to
label, archive, or refresh historical docs after the next mapping phase rather
than delete them now.

## 17.9 Local Artifact Findings

Ignored local artifacts are cleanup candidates only for the local workstation.
They are not repository cleanup candidates unless the team decides to document
local artifact handling more explicitly.

Safe local cleanup candidates after owner review:

- Python caches: `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`,
  `__pycache__/`.
- Generated local parser outputs under `output/`.
- Local virtual environment `.venv/`, if it can be recreated.
- Empty local `examples/` directory, if it is not being reserved for future
  sample files.

Local cleanup candidates requiring extra care:

- `input/`, because it contains local source PDFs.
- `check_techdoc_parse_result.py`, because it may encode a useful manual smoke
  workflow even though it is ignored and not part of the repository contract.

## 17.10 Git Reference Findings

The Git reference set is simple and does not require cleanup before Phase 13E1:

- Active local branch: `main`.
- Active remote branch: `origin/main`.
- Remote HEAD: `origin/HEAD -> origin/main`.
- Release tag present: `v0.1.0-mvp`.
- Stash list: empty.

No stale local feature branch, duplicate remote branch, or stale stash was found.
No tag movement or branch deletion is recommended.

## 17.11 Backward-Compatibility Risks

Cleanup risks to avoid:

- Removing package re-export modules because imports appear indirect.
- Collapsing current output exporters into contract serializers.
- Treating structured-document contract code as unused because it is not wired
  into the CLI yet.
- Deleting historical docs before their retained planning value is copied into a
  current canonical document.
- Removing synthetic fixtures without checking contract tests and downstream
  schema examples.
- Deleting local `input/` files without explicit owner approval.
- Moving current CLI route or artifact names before a versioned output contract
  change.

## 17.12 Recommended Cleanup Phases

M.3b1 - Local ignored artifact review:

- Confirm whether local `input/` PDFs and generated `output/` artifacts should
  remain on this workstation.
- Optionally remove local caches and pycache directories.
- Decide whether `check_techdoc_parse_result.py` should be deleted locally,
  promoted to a documented example, or replaced by a supported smoke command.

M.3b2 - Documentation archive and staleness labeling:

- Add superseded-status notes to Phase 12A and early Phase 13A documents.
- Decide whether `PROJECTPLAN.md` should be retained as historical planning or
  moved under a future docs archive.
- Refresh the MVP readiness checklist before the next release checkpoint.

M.3b3 - Verified obsolete-code removal:

- No tracked source file qualifies now.
- Revisit only after import analysis, tests, and public API review prove a
  module or export is truly obsolete.

M.3b4 - Import/package consolidation:

- Defer. Current package boundaries are readable and aligned with pipeline
  responsibilities.
- Any consolidation should be treated as a compatibility-sensitive refactor.

## 17.13 Decision Gate

Cleanup timing recommendation: after Phase 13E1.

Rationale:

- Phase 13E1 can proceed against the current active package structure.
- No runtime module, test fixture, output path, branch, tag, or stash blocks
  continued contract mapping work.
- Documentation cleanup will become clearer after the table and figure-caption
  mapping phase adds the next current-state boundary.
- Local ignored artifacts can be cleaned independently and do not affect source
  correctness.

M.3 conclusion: cleanup is useful but non-blocking.
