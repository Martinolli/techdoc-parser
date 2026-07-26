# OCR Capability and Environment Inventory

## Purpose

D.7b-1 inventories repository OCR references and local OCR/rendering capability
without running OCR recognition, processing the wing-design chapter, installing
software, downloading packages, or changing parser behavior. D.7b-2 adds an
explicit controlled Tesseract adapter; this document now records the updated
repository capability while preserving the D.7b-1 inventory findings.

## Relationship to D.7a

D.7a is implemented as a controlled OCR-fidelity evaluator. It can compare
supplied native/OCR text artifacts, including D.7b-2 controlled OCR document
artifacts. D.7a still does not run OCR. Owner review remains required before
any final OCR-fidelity acceptance claim.

## Scope

The inventory inspected repository references, declared dependencies, Python
package metadata, allowlisted executable availability, Tesseract language
listing, and local PDF-rendering capability.

## Prohibited Actions

D.7b-1 ran no OCR recognition and processed no source document. D.7b-2 ran
only synthetic smoke OCR after implementation. No real user document was
processed. No software, Python package, OCR model, or language pack was
installed or downloaded. No default parser CLI behavior, StructuredDocument
output, current parser manifest behavior, source PDF, or AviationRAG file was
changed.

## Repository OCR References

Repository references fall into these groups:

| Reference class | Finding |
| --- | --- |
| warning_or_detection_only | Existing parser and validation paths can flag pages that require OCR. |
| declared_integration | D.7a has a report-only comparator for supplied OCR artifacts. |
| implemented_adapter | D.7b-2 adds `techdoc_parser.ocr` and `tools/ocr/run-controlled-tesseract-ocr.py` as an explicit controlled adapter. |
| optional_dependency | `pyproject.toml` declares `PyMuPDF` only; no OCR wrapper or engine dependency is declared. |
| test_fixture_only | OCR text appears in synthetic tests and fixtures only. |
| documentation_only | README, TODO, and docs describe OCR as out of scope or blocked. |

## Difference Between OCR-Need Detection and OCR Execution

`requires_ocr` and related warnings identify pages where native text extraction
is insufficient. They do not rasterize pages, invoke an OCR engine, produce OCR
text, record processed pages, or create engine provenance. D.7b-2 OCR
execution is separate and only runs through the explicit controlled OCR tool.

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
| tesseract | true | true | true | true | true | true | SUPPORTED_AND_AVAILABLE except `ell` limitation |

## Language/Model Availability

Tesseract reports `eng` and `osd`. It does not report `ell` in the local
language listing.

## Greek-Symbol Implications

The absence of `ell` is recorded as `GREEK_LANGUAGE_MODEL_UNAVAILABLE`. Even if
`ell` were present later, language-pack presence alone would not prove
mathematical Greek-symbol fidelity.

## Forced OCR Capability

Forced OCR is not supported by the default parser CLI or parser API. Explicit
full-page controlled OCR is supported only through
`tools/ocr/run-controlled-tesseract-ocr.py --mode ocr_all_pages`.

## Selective-Page OCR Capability

Selective-page OCR is not supported by the default parser CLI or parser API.
Explicit controlled selected-page OCR is supported only through
`tools/ocr/run-controlled-tesseract-ocr.py --mode ocr_selected_pages --pages`.

## Page-Provenance Capability

D.7b-2 controlled OCR artifacts record processed page lists, failed page lists,
per-page failures, rendering checksums, raw OCR checksums, normalized OCR
checksums, engine identity, engine version, OCR mode, languages, `psm`, and
`oem`.

## Manifest/Version Recording Capability

Current output manifest support exists for parser artifacts and remains
unchanged. D.7b-2 adds a separate `techdoc-ocr-manifest / 0.1.0` contract for
controlled OCR artifacts, including engine identity, engine version, OCR mode,
language/model selection, processed pages, failed pages, limitations, and
artifact checksums.

## Raw Versus Normalized OCR Output

D.7b-2 preserves raw OCR text separately from normalized OCR text in per-page
files and in `ocr_document.json`.

## Deterministic Configuration

Tesseract version and local language identifiers are recordable. D.7b-2 records
deterministic rasterization DPI, OCR mode, language selection, selected pages,
raw output retention, normalized output separation, and checksum provenance.

## Local Licensing Metadata

Local package metadata reports `PyMuPDF` as dual licensed under GNU AGPL 3.0 or
Artifex commercial license. No legal conclusion is made. The Tesseract
executable license was not asserted from local metadata.

## Deployment Considerations

D.7b-2 added repository documentation for the explicit adapter. It did not
install Tesseract, install language packs, change PATH, change registry values,
or change deployment infrastructure.

## Capability Matrix

| Capability | Status |
| --- | --- |
| Engine available locally | yes |
| Repository adapter exists | yes, explicit controlled adapter only |
| Explicit OCR opt-in possible | yes |
| Forced OCR possible | yes, explicit `ocr_all_pages` only |
| Selective-page OCR possible | yes, explicit `ocr_selected_pages` only |
| Page-by-page execution possible | yes |
| Unicode output possible | yes |
| Greek language/model available | no |
| Engine/version recordable | yes |
| Processed-page list recordable | yes |
| Per-page failure recordable | yes |
| Raw OCR output preservable | yes |
| Normalized output separable | yes |
| Page provenance preservable | yes |
| StructuredDocument integration exists | no |
| Manifest integration exists | yes, separate OCR manifest only |
| Deterministic configuration possible | yes for recorded adapter settings |
| Network/model download required | no |
| License metadata locally available | partial |
| Suitable for D.7a without changes | yes as a supplied OCR artifact, with owner review still required |

## Blocking Gaps

- `GREEK_LANGUAGE_MODEL_UNAVAILABLE`
- `GREEK_FIDELITY_NOT_ESTABLISHED`
- `MATHEMATICAL_FIDELITY_NOT_ESTABLISHED`
- `OWNER_REVIEW_REQUIRED_FOR_FIDELITY_ACCEPTANCE`

## Overall Outcome

`EXISTING_SUPPORTED_ENGINE_AVAILABLE` for explicit controlled `eng` OCR, with
recorded limitations for unavailable `ell` and unestablished OCR fidelity.

## Recommended Next Action

Use the controlled adapter only through explicit invocation. Do not claim OCR
fidelity until D.7a comparison and owner review are completed. Do not request
`eng+ell` until the `ell` language model is installed through a separately
approved environment change.

## What D.7b-1 Established

D.7b-1 established that a local Tesseract executable is available and that
PyMuPDF rendering is available, but the repository does not have a supported OCR
adapter, forced-OCR mode, selective-page OCR mode, OCR provenance recording, or
OCR manifest metadata.

## What D.7b-2 Established

D.7b-2 established an explicit controlled adapter for the local Tesseract CLI
with PyMuPDF rendering, full-page OCR, selected-page OCR, raw and normalized OCR
separation, page provenance, a separate OCR document artifact, a separate OCR
manifest, synthetic regression tests, and a synthetic-only smoke path.

## What D.7b-1 Did Not Establish

D.7b-1 did not establish OCR fidelity, Greek-symbol accuracy, source-page
accuracy, parser correctness on OCR text, owner acceptance, deployment
readiness, or downstream AviationRAG ingestion readiness.

D.7b-2 also did not establish OCR fidelity, Greek-symbol accuracy,
mathematical-expression accuracy, real-document readiness, owner acceptance, or
downstream AviationRAG ingestion readiness.

## Preconditions for D.7b-2 or D.7a Rerun

D.7a can now be rerun only if an explicitly approved OCR artifact is supplied.
The evaluator must still not run OCR itself, and owner review remains required
before any final D.7a OCR-fidelity disposition.
