import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import fitz  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation import (  # noqa: E402
    BLOCKED,
    OWNER_REVIEW_REQUIRED,
    PASS,
    REQUIRED_OWNER_CHECK_FIELDS,
    REVIEW_CHECK_FIELDS,
    build_engineering_ocr_execution_package,
    compare_engineering_ocr_determinism,
    default_owner_review_decision,
    engineering_ocr_result_to_json,
    evaluate_engineering_ocr_fidelity,
    sanitized_summary_fixture,
    validate_owner_review_decision,
    write_engineering_ocr_reports,
)
from techdoc_parser.ocr import (  # noqa: E402
    PASS_WITH_WARNINGS,
    ControlledOcrDocumentResult,
    ControlledOcrPageResult,
    ControlledOcrRequest,
    OcrPageProvenance,
    write_controlled_ocr_artifacts,
)

TOOL = ROOT / "tools" / "evaluation" / "run-engineering-ocr-fidelity.py"


class EngineeringOcrFidelityTests(unittest.TestCase):
    def test_no_supported_ocr_artifact_returns_blocked_without_running_ocr(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "synthetic.pdf"
            _write_pdf(source, ["alpha β table", "second page figure"])

            result = evaluate_engineering_ocr_fidelity(source_path=source)
            payload = engineering_ocr_result_to_json(result)

        self.assertEqual(result.outcome, BLOCKED)
        self.assertEqual(result.observed_page_count, 2)
        self.assertFalse(result.capability.parser_ocr_runner_present)
        self.assertFalse(result.ocr_run_by_evaluator)
        self.assertEqual(result.page_outcome_counts, {"BLOCKED": 2})
        self.assertNotIn(str(source.parent), payload)
        self.assertNotIn("alpha", payload)

    def test_supplied_ocr_artifact_is_evaluated_but_owner_review_remains_required(
        self,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "synthetic.pdf"
            native_text = "alpha β = 2\nTABLE 1\nFIGURE 1"
            _write_pdf(source, [native_text])
            native = root / "native.json"
            native.write_text(
                json.dumps({"pages": [{"page_number": 1, "text": native_text}]}),
                encoding="utf-8",
            )
            ocr = root / "ocr.json"
            ocr.write_text(
                json.dumps(
                    {
                        "pages": [
                            {
                                "page_number": 1,
                                "text": "alpha b = 2\nTABLE 1\nFIGURE 1",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = evaluate_engineering_ocr_fidelity(
                source_path=source,
                native_text_artifact=native,
                ocr_text_artifact=ocr,
            )

        page = result.page_results[0]
        self.assertEqual(result.outcome, OWNER_REVIEW_REQUIRED)
        self.assertEqual(page.final_page_outcome, "REVIEW")
        self.assertIn("formula_heavy", page.source_profiles)
        self.assertIn("table_candidate", page.source_profiles)
        self.assertIn("figure_heavy", page.source_profiles)
        self.assertTrue(page.symbol_substitution_warnings)

    def test_completed_owner_review_can_support_pass_for_clean_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "synthetic.pdf"
            text = "Lift coefficient CL = 0.5\nGreek α β γ preserved"
            _write_pdf(source, [text])
            native = root / "native.json"
            native.write_text(
                json.dumps({"pages": [{"page_number": 1, "text": text}]}),
                encoding="utf-8",
            )
            ocr = root / "ocr.json"
            ocr.write_text(
                json.dumps({"pages": [{"page_number": 1, "text": text}]}),
                encoding="utf-8",
            )
            review = default_owner_review_decision(
                document_key="wing_design_chapter_7",
                pdf_page_index=0,
                page_number=1,
            )
            completed = validate_owner_review_decision(
                {
                    "document_key": review.document_key,
                    "pdf_page_index": review.pdf_page_index,
                    "page_number": review.page_number,
                    "review_status": "completed",
                    "checklist": {
                        field: "pass" for field in REQUIRED_OWNER_CHECK_FIELDS
                    },
                },
                expected_document_key="wing_design_chapter_7",
                expected_pdf_page_index=0,
            )

            result = evaluate_engineering_ocr_fidelity(
                source_path=source,
                native_text_artifact=native,
                ocr_text_artifact=ocr,
                owner_reviews={1: completed},
            )

        self.assertEqual(result.outcome, PASS)
        self.assertEqual(result.page_results[0].final_page_outcome, PASS)

    def test_owner_review_validation_rejects_protected_source_text(self):
        with self.assertRaisesRegex(ValueError, "Protected field"):
            validate_owner_review_decision(
                {
                    "document_key": "wing_design_chapter_7",
                    "pdf_page_index": 0,
                    "page_number": 1,
                    "review_status": "pending",
                    "checklist": {
                        field: "pending" for field in REQUIRED_OWNER_CHECK_FIELDS
                    },
                    "source_text": "not allowed",
                },
                expected_document_key="wing_design_chapter_7",
                expected_pdf_page_index=0,
            )

    def test_report_write_requires_explicit_permission(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "synthetic.pdf"
            _write_pdf(source, ["report only"])
            result = evaluate_engineering_ocr_fidelity(source_path=source)
            report = root / "report.json"

            with self.assertRaises(PermissionError):
                write_engineering_ocr_reports(result, json_path=report)

            written = write_engineering_ocr_reports(
                result,
                json_path=report,
                allow_report_write=True,
            )
            self.assertTrue(report.exists())

        self.assertEqual(len(written), 1)

    def test_cli_writes_blocked_sanitized_reports(self):
        output_root = ROOT / "output"
        output_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_root) as temp_dir:
            root = Path(temp_dir)
            source = root / "synthetic.pdf"
            report = root / "engineering_ocr.json"
            _write_pdf(source, ["cli report"])

            completed = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--source",
                    str(source),
                    "--expected-pages",
                    "1",
                    "--report-json",
                    str(report),
                    "--allow-report-write",
                    "--strict",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            self.assertTrue(report.exists())

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Outcome: BLOCKED", completed.stdout)

    def test_structured_document_artifact_supplies_native_page_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "synthetic.pdf"
            _write_pdf(source, ["first page", "second page"])
            structured = root / "structured_document.json"
            structured.write_text(
                json.dumps(_structured_document_payload(["first page", "second page"])),
                encoding="utf-8",
            )
            ocr = root / "ocr.json"
            ocr.write_text(
                json.dumps(
                    {
                        "pages": [
                            {"page_number": 1, "text": "first page"},
                            {"page_number": 2, "text": "second page"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = evaluate_engineering_ocr_fidelity(
                source_path=source,
                native_text_artifact=structured,
                ocr_text_artifact=ocr,
                expected_page_count=2,
            )

        self.assertEqual(result.outcome, OWNER_REVIEW_REQUIRED)
        self.assertEqual(len(result.page_results), 2)

    def test_d7a2_generates_review_package_with_pending_checklists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "synthetic.pdf"
            texts = [f"page {number} <unsafe>" for number in range(1, 44)]
            _write_pdf(source, texts)
            native_document = _write_json(
                root / "native" / "document.json",
                _native_document_payload(texts),
            )
            structured = _write_json(
                root / "native" / "structured_document.json",
                _structured_document_payload(texts),
            )
            native_manifest = _write_json(
                root / "native" / "manifest.json",
                {"schema_version": "0.1.0", "parser": {"version": "0.1.0"}},
            )
            ocr_output = root / "ocr"
            write_controlled_ocr_artifacts(
                _controlled_ocr_result(source, texts),
                ocr_output,
                allow_write=True,
                preserve_rendered_pages=False,
            )
            result = evaluate_engineering_ocr_fidelity(
                source_path=source,
                native_text_artifact=structured,
                ocr_text_artifact=ocr_output / "ocr_document.json",
                expected_page_count=43,
            )
            determinism = {
                "deterministic": True,
                "file_count": 1,
                "mismatched_files": [],
            }

            summary = build_engineering_ocr_execution_package(
                source_path=source,
                native_document_path=native_document,
                structured_document_path=structured,
                native_manifest_path=native_manifest,
                ocr_artifact_path=ocr_output / "ocr_document.json",
                ocr_manifest_path=ocr_output / "ocr_manifest.json",
                output_root=root,
                evaluation_result=result,
                determinism=determinism,
                allow_local_write=True,
            )

            review_root = root / "review"
            page_dirs = sorted(review_root.glob("page_*"))
            checklist = json.loads(
                (review_root / "page_001" / "review_checklist.json").read_text(
                    encoding="utf-8"
                )
            )
            html = (review_root / "page_001" / "review.html").read_text(
                encoding="utf-8"
            )
            fixture = sanitized_summary_fixture(summary)

            self.assertEqual(len(page_dirs), 43)
            self.assertTrue((review_root / "index.html").exists())
            self.assertEqual(checklist["review_status"], "pending")
            self.assertEqual(set(checklist["checklist"]), set(REVIEW_CHECK_FIELDS))
            self.assertTrue(
                all(value == "pending" for value in checklist["checklist"].values())
            )
            self.assertIn("&lt;unsafe&gt;", html)
            self.assertNotIn("<script", html.lower())
            self.assertEqual(summary["corpus_outcome"], OWNER_REVIEW_REQUIRED)
            self.assertEqual(summary["pending_checklist_count"], 43)
            self.assertEqual(fixture["owner_review_status"], "pending")
            self.assertEqual(fixture["corpus_outcome"], OWNER_REVIEW_REQUIRED)
            self.assertNotIn("<unsafe>", json.dumps(fixture))
            self.assertNotIn("AviationRAG", sys.modules)

    def test_d7a2_determinism_detects_changed_ocr_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "run_1" / "pages" / "page_001"
            second = root / "run_2" / "pages" / "page_001"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            (root / "run_1" / "ocr_document.json").write_text("same", encoding="utf-8")
            (root / "run_2" / "ocr_document.json").write_text("same", encoding="utf-8")
            (first / "normalized_ocr.txt").write_text("one", encoding="utf-8")
            (second / "normalized_ocr.txt").write_text("two", encoding="utf-8")

            result = compare_engineering_ocr_determinism(
                root / "run_1",
                root / "run_2",
            )

        self.assertFalse(result["deterministic"])
        self.assertIn("OCR_OUTPUT_NONDETERMINISTIC", result["warning_codes"])


def _write_pdf(path: Path, pages: list[str]) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 72), text, fontsize=11)
    document.save(path)
    document.close()


def _write_json(path: Path, data: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _native_document_payload(texts: list[str]) -> dict[str, object]:
    return {
        "parser_version": "0.1.0",
        "pages": [
            {
                "page_number": index + 1,
                "has_native_text": True,
                "requires_ocr": False,
                "text_blocks": [{"text": text}],
            }
            for index, text in enumerate(texts)
        ],
    }


def _structured_document_payload(texts: list[str]) -> dict[str, object]:
    return {
        "schema_name": "techdoc-structured-document",
        "schema_version": "0.1.0",
        "parser_name": "techdoc-parser",
        "parser_version": "0.1.0",
        "document": {
            "document_id": "wing_design_chapter_7",
            "source_filename": "synthetic.pdf",
            "page_count": len(texts),
        },
        "pages": [
            {
                "page_id": f"page-{index + 1:04d}",
                "pdf_page_index": index,
                "page_number": index + 1,
                "printed_page_label": None,
            }
            for index, _ in enumerate(texts)
        ],
        "sections": [],
        "blocks": [
            {
                "block_id": f"block-{index + 1}",
                "block_type": "paragraph",
                "text": text,
                "document_block_index": index,
                "page_block_index": 0,
                "page_id": f"page-{index + 1:04d}",
                "page_number": index + 1,
                "pdf_page_index": index,
                "source_span": {
                    "page_start": index + 1,
                    "page_end": index + 1,
                    "pdf_page_index_start": index,
                    "pdf_page_index_end": index,
                    "source_block_ids": [f"block-{index + 1}"],
                },
            }
            for index, text in enumerate(texts)
        ],
        "tables": [],
        "figures": [],
        "equations": [],
        "admonitions": [],
        "cross_references": [],
    }


def _controlled_ocr_result(
    source: Path,
    texts: list[str],
) -> ControlledOcrDocumentResult:
    request = ControlledOcrRequest(
        source_path=source,
        document_id="wing_design_chapter_7",
        languages=("eng",),
        timeout_seconds=60,
        preserve_rendered_pages=False,
    )
    source_sha = "0" * 64
    pages = tuple(
        ControlledOcrPageResult(
            page_number=index + 1,
            pdf_page_index=index,
            status="processed",
            raw_ocr_text=f"{text}\n",
            normalized_ocr_text=f"{text}\n",
            provenance=OcrPageProvenance(
                page_number=index + 1,
                pdf_page_index=index,
                source_sha256=source_sha,
                source_size_bytes=source.stat().st_size,
                rendered_image_sha256=f"{index + 1:064x}"[-64:],
                raw_ocr_sha256=f"{index + 2:064x}"[-64:],
                normalized_ocr_sha256=f"{index + 3:064x}"[-64:],
                rendering_engine="PyMuPDF",
                rendering_dpi=300,
                ocr_engine="tesseract",
                ocr_engine_version="tesseract 5.3.0",
                ocr_languages=("eng",),
                ocr_mode="ocr_all_pages",
                psm=6,
                oem=1,
            ),
        )
        for index, text in enumerate(texts)
    )
    return ControlledOcrDocumentResult(
        request=request,
        outcome=PASS_WITH_WARNINGS,
        source_filename=source.name,
        source_sha256=source_sha,
        source_size_bytes=source.stat().st_size,
        observed_page_count=len(texts),
        requested_pages=tuple(range(1, len(texts) + 1)),
        processed_pages=tuple(range(1, len(texts) + 1)),
        skipped_pages=(),
        failed_pages=(),
        page_results=pages,
        engine_version="tesseract 5.3.0",
        available_languages=("eng", "osd"),
        warnings=(
            "GREEK_LANGUAGE_MODEL_UNAVAILABLE",
            "GREEK_FIDELITY_NOT_ESTABLISHED",
            "MATHEMATICAL_FIDELITY_NOT_ESTABLISHED",
        ),
        limitations=("Owner review required.",),
    )
