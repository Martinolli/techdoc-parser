# OCR Capability and Environment Inventory

## Purpose

D.7b-1 inventories repository OCR references and local OCR/rendering capability
without running OCR recognition, processing the wing-design chapter, installing
software, downloading packages, or changing parser behavior.

## Relationship to D.7a

D.7a is implemented as a controlled OCR-fidelity evaluator. It can compare
supplied native/OCR text artifacts, but its current blocking code remains
`NO_SUPPORTED_OCR_EXECUTION_PATH` because the parser has no supported OCR
execution path.

## Scope

The inventory inspected repository references, declared dependencies, Python
package metadata, allowlisted executable availability, Tesseract language
listing, and local PDF-rendering capability.

## Prohibited Actions

No OCR recognition was run. No source document was processed. No software,
Python package, OCR model, or language pack was installed or downloaded. No
parser CLI behavior, StructuredDocument output, manifest behavior, source PDF,
or AviationRAG file was changed.

## Repository OCR References

Repository references fall into these groups:

| Reference class | Finding |
| --- | --- |
| warning_or_detection_only | Existing parser and validation paths can flag pages that require OCR. |
| declared_integration | D.7a has a report-only comparator for supplied OCR artifacts. |
| implemented_adapter | No production parser OCR execution adapter was found. |
| optional_dependency | `pyproject.toml` declares `PyMuPDF` only; no OCR wrapper or engine dependency is declared. |
| test_fixture_only | OCR text appears in synthetic tests and fixtures only. |
| documentation_only | README, TODO, and docs describe OCR as out of scope or blocked. |

## Difference Between OCR-Need Detection and OCR Execution

`requires_ocr` and related warnings identify pages where native text extraction
is insufficient. They do not rasterize pages, invoke an OCR engine, produce OCR
text, record processed pages, or create engine provenance.

## Python Package Inventory

| Package | Installed | Version | Role | Integrated |
| --- | --- | --- | --- | --- |
| PyMuPDF | true | 1.27.2.3 | rendering | false |
| pytesseract | false | not_installed | OCR wrapper | false |
| tesserocr | false | not_installed | OCR wrapper | false |
| ocrmypdf | false | not_installed | OCR wrapper | false |
| easyocr | false | not_installed | OCR engine | false |
| paddleocr | false | not_installed | OCR engine | false |
| rapidocr_onnxruntime | false | not_installed | OCR engine | false |
| python-doctr | false | not_installed | OCR engine | false |
| keras-ocr | false | not_installed | OCR engine | false |

## Executable Inventory

| Executable | Available | Version | Role |
| --- | --- | --- | --- |
| tesseract | true | tesseract v5.3.0.20221214 | OCR engine |
| ocrmypdf | false | not_found | OCR wrapper |
| pdftoppm | false | not_found | rendering |
| pdftotext | false | not_found | native text extraction |
| pdfinfo | false | not_found | PDF metadata |
| mutool | false | not_found | rendering |
| magick | false | not_found | rendering |
| gswin64c | false | not_found | rendering |
| gswin32c | false | not_found | rendering |

No executable paths are recorded in committed reports.

## PDF-Rendering Inventory

`PyMuPDF` is installed and discoverable. Local page rendering is therefore
available with deterministic DPI control, page-range control, and PNG output
capability. D.7b-1 did not render the wing-design chapter.

## OCR Engine Candidates

| Engine | Available | Adapter | Forced OCR | Selective pages | Provenance | Manifest | Candidate status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tesseract | true | false | false | false | false | false | AVAILABLE_NOT_INTEGRATED |

## Language/Model Availability

Tesseract reports `eng` and `osd`. It does not report `ell` in the local
language listing.

## Greek-Symbol Implications

The absence of `ell` is recorded as `GREEK_LANGUAGE_MODEL_UNAVAILABLE`. Even if
`ell` were present later, language-pack presence alone would not prove
mathematical Greek-symbol fidelity.

## Forced OCR Capability

Forced OCR is not supported by the current repository CLI or parser API.

## Selective-Page OCR Capability

Selective-page OCR is not supported by the current repository CLI or parser API.

## Page-Provenance Capability

D.7a page evidence can carry page provenance for supplied artifacts, but no
parser OCR execution adapter records OCR-processed page lists or per-page OCR
failures.

## Manifest/Version Recording Capability

Current output manifest support exists for parser artifacts, but there is no OCR
manifest contract for engine identity, engine version, OCR mode, language/model
selection, processed pages, or per-page failures.

## Raw Versus Normalized OCR Output

The repository does not currently preserve raw OCR output separately from any
future normalized OCR text because no OCR execution path exists.

## Deterministic Configuration

Tesseract version and local language identifiers are recordable. A deterministic
repository configuration for rasterization DPI, OCR mode, language selection,
processed pages, raw output retention, and normalized output separation remains
undefined.

## Local Licensing Metadata

Local package metadata reports `PyMuPDF` as dual licensed under GNU AGPL 3.0 or
Artifex commercial license. No legal conclusion is made. The Tesseract
executable license was not asserted from local metadata.

## Deployment Considerations

An OCR execution path would need explicit deployment documentation for engine
installation, language packs, version recording, deterministic rendering/OCR
configuration, and privacy-safe provenance. No deployment change was made in
D.7b-1.

## Capability Matrix

| Capability | Status |
| --- | --- |
| Engine available locally | yes |
| Repository adapter exists | no |
| Explicit OCR opt-in possible | no |
| Forced OCR possible | no |
| Selective-page OCR possible | no |
| Page-by-page execution possible | no |
| Unicode output possible | yes |
| Greek language/model available | no |
| Engine/version recordable | yes |
| Processed-page list recordable | no |
| Per-page failure recordable | no |
| Raw OCR output preservable | no |
| Normalized output separable | no |
| Page provenance preservable | no |
| StructuredDocument integration exists | no |
| Manifest integration exists | no |
| Deterministic configuration possible | partial |
| Network/model download required | no |
| License metadata locally available | partial |
| Suitable for D.7a without changes | no |

## Blocking Gaps

- `OCR_ENGINE_NOT_INTEGRATED`
- `FORCED_OCR_NOT_SUPPORTED`
- `SELECTIVE_PAGE_OCR_NOT_SUPPORTED`
- `OCR_PAGE_PROVENANCE_NOT_RECORDED`
- `OCR_PROCESSED_PAGES_NOT_RECORDED`
- `OCR_MANIFEST_METADATA_MISSING`
- `RAW_OCR_OUTPUT_NOT_PRESERVED`
- `OCR_NORMALIZATION_NOT_SEPARATED`
- `GREEK_LANGUAGE_MODEL_UNAVAILABLE`
- `DETERMINISTIC_OCR_CONFIGURATION_UNDEFINED`

## Overall Outcome

`ENGINE_INSTALLED_BUT_NOT_INTEGRATED`

## Recommended Next Action

`IMPLEMENT_ADAPTER_FOR_INSTALLED_ENGINE`

## What D.7b-1 Established

D.7b-1 established that a local Tesseract executable is available and that
PyMuPDF rendering is available, but the repository does not have a supported OCR
adapter, forced-OCR mode, selective-page OCR mode, OCR provenance recording, or
OCR manifest metadata.

## What D.7b-1 Did Not Establish

D.7b-1 did not establish OCR fidelity, Greek-symbol accuracy, source-page
accuracy, parser correctness on OCR text, owner acceptance, deployment
readiness, or downstream AviationRAG ingestion readiness.

## Preconditions for D.7b-2 or D.7a Rerun

D.7b-2 should implement a controlled adapter for the installed engine before a
D.7a rerun. The adapter must record engine identity, engine version, OCR mode,
language/model selection, processed pages, per-page failures, raw OCR output,
normalized output, page provenance, and manifest metadata before D.7a execution
can be unblocked.
