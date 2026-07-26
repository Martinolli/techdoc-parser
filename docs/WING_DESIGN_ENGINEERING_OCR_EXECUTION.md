# Wing Design Engineering OCR Execution

## 1. Purpose

D.7a-2 executed a controlled `eng`-only OCR baseline for
`Wing_Design_Chapter_7.pdf`, generated automated comparison evidence, and
created a local 43-page owner-review package. The phase stops at
`OWNER_REVIEW_REQUIRED`.

## 2. Relationship to D.7a, D.7b-1, and D.7b-2

D.7a supplies the report-only OCR-fidelity evaluator. D.7b-1 established local
OCR/rendering capability and the missing `ell` limitation. D.7b-2 added the
explicit controlled Tesseract adapter used here. D.7a still did not run OCR;
OCR was run only through the explicit controlled adapter.

## 3. Selected Document

Only `input/Wing_Design_Chapter_7.pdf` was processed.

## 4. Source Identity

- Filename: `Wing_Design_Chapter_7.pdf`
- SHA-256: `a93852fafbfb929719513e73174bac3d2e71b0ecfd1fdaa91e8551e3b59326cd`
- File size: `6114561` bytes

## 5. Source Protection

The source PDF remained ignored, untracked, unstaged, unmodified, and outside
the committed artifact set.

## 6. Page Count

PyMuPDF observed `43` pages. All 43 pages had a native text layer.

## 7. Native Extraction Command and Result

```powershell
.\.venv\Scripts\python.exe -c "from techdoc_parser.cli import main; raise SystemExit(main())" `
  input\Wing_Design_Chapter_7.pdf `
  --output output\evaluation\engineering_ocr_fidelity\wing_design_chapter_7\native\document.json `
  --structured-document-output output\evaluation\engineering_ocr_fidelity\wing_design_chapter_7\native\structured_document.json `
  --structured-document-id wing_design_chapter_7 `
  --structured-document-overwrite `
  --manifest-output output\evaluation\engineering_ocr_fidelity\wing_design_chapter_7\native\manifest.json
```

Result: exit code `0`. Parser version `0.1.0`. StructuredDocument schema
`techdoc-structured-document / 0.1.0`.

## 8. Controlled OCR Command and Result

```powershell
.\.venv\Scripts\python.exe `
  tools\ocr\run-controlled-tesseract-ocr.py `
  --source input\Wing_Design_Chapter_7.pdf `
  --document-id wing_design_chapter_7 `
  --mode ocr_all_pages `
  --language eng `
  --dpi 300 `
  --psm 6 `
  --oem 1 `
  --timeout-seconds 60 `
  --output-dir output\evaluation\engineering_ocr_fidelity\wing_design_chapter_7\ocr_run_1 `
  --allow-output-write `
  --preserve-rendered-pages `
  --strict
```

Result: `PASS_WITH_WARNINGS`, CLI exit code `2`. All 43 pages were requested
and processed. No pages failed or timed out.

## 9. Tesseract Version

`tesseract v5.3.0.20221214`

## 10. OCR Language

Requested OCR language: `eng`

Available local languages: `eng`, `osd`

## 11. Missing `ell` Limitation

`ell` was unavailable and was not requested. The run retained
`GREEK_LANGUAGE_MODEL_UNAVAILABLE`.

## 12. Rendering Configuration

Rendering backend: PyMuPDF `1.27.2.3`

OCR rendering DPI: `300`

Tesseract PSM/OEM: `6` / `1`

## 13. OCR Page Accounting

- Requested pages: `43`
- Processed pages: `43`
- Failed pages: `0`
- Timed-out pages: `0`

## 14. Raw and Normalized Output

Raw OCR text and normalized OCR text were preserved separately under the ignored
local OCR output. No OCR text was committed.

## 15. Provenance

Every OCR page includes source SHA-256, rendered image SHA-256, raw OCR
SHA-256, normalized OCR SHA-256, page number, PDF page index, engine identity,
engine version, language, DPI, PSM, and OEM.

## 16. Native/OCR Artifact Validation

`ocr_document.json` and `ocr_manifest.json` validated against
`techdoc-ocr-document / 0.1.0` and `techdoc-ocr-manifest / 0.1.0`.

## 17. Page Profiles

| Profile | Page count |
| --- | ---: |
| Native text | 43 |
| Image only | 0 |
| Hybrid | 26 |
| Formula heavy | 27 |
| Greek-symbol heavy | 19 |
| Figure heavy | 26 |
| Table candidate | 25 |
| Multi-column | 38 |
| Mixed layout | 43 |
| Blank/near blank | 0 |

## 18. Automated Text Findings

Automated comparison evaluated all 43 pages. It reported low OCR text coverage
on 42 pages, OCR-only token review on 43 pages, possible line collapse on 29
pages, and possible line fragmentation on 1 page. These are evidence signals,
not final truth.

## 19. Reading-Order Findings

Potential reading-order concerns were recorded through line-collapse and
line-fragmentation warning codes. Owner review is required.

## 20. Greek-Symbol Findings

Greek-symbol-heavy profile was assigned to 19 pages. Missing or substituted
symbol candidates were recorded, including alpha, beta, delta, gamma, less-than
or equal, and minus-sign substitution warnings. Greek fidelity remains
unestablished.

## 21. Equation Findings

Formula-heavy profile was assigned to 27 pages. Mathematical fidelity and
equation grouping remain unestablished pending owner review.

## 22. Figure/Caption Findings

Figure-heavy profile was assigned to 26 pages. Figure/caption association and
fabrication risk remain owner-review questions. No figure descriptions were
generated.

## 23. Table-Classification Findings

Table-candidate profile was assigned to 25 pages. No reconstructed rows or
cells are claimed.

## 24. Page-Provenance Findings

No page-provenance contradiction was detected. Page number and PDF page index
alignment were preserved for all 43 pages.

## 25. Review-Priority Results

| Priority | Page count |
| --- | ---: |
| Critical | 34 |
| High | 9 |
| Normal | 0 |
| Low | 0 |

All 43 pages still require owner review.

## 26. Determinism Result

Two identical controlled OCR runs were compared. Determinism passed for 174
files, including OCR artifacts, manifests, raw text, normalized text,
provenance files, and rendered page files.

## 27. Owner-Review Package

The ignored local review package contains:

- 43 page directories
- 43 rendered pages
- 43 review HTML files
- 43 native text files
- 43 OCR text files
- 43 native block files
- 43 OCR block files
- 43 automated summaries
- 43 pending checklists
- 1 review index

## 28. Pending Checklist Status

Owner review completion: `0/43`

Every generated checklist is `pending`.

## 29. Preliminary Outcome

Corpus outcome: `OWNER_REVIEW_REQUIRED`

Final OCR fidelity was not accepted.

## 30. Automated-Evidence Limitations

Automated checks are comparison aids. Native text is not visual ground truth,
OCR text is not visual ground truth, and universal OCR accuracy is not claimed.

## 31. What D.7a-2 Established

D.7a-2 established source identity, native baseline generation, controlled
`eng` OCR execution for all 43 pages, deterministic OCR outputs, complete
page-level provenance, automated evidence generation, and a full local
owner-review package.

## 32. What Remains Unresolved

Greek fidelity, mathematical fidelity, equation grouping, figure/caption
association, table classification, and final engineering OCR fidelity remain
unresolved until owner review.

## 33. Preconditions for D.7a-3

D.7a-3 should complete owner visual review of all 43 pending checklists. It
must not infer acceptance from automated evidence alone.

## 34. D.8 Status

D.8 remains blocked. No AviationRAG migration, ingestion, embeddings, Astra, or
FAISS activity occurred.
