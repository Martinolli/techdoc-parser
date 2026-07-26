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
    default_owner_review_decision,
    engineering_ocr_result_to_json,
    evaluate_engineering_ocr_fidelity,
    validate_owner_review_decision,
    write_engineering_ocr_reports,
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


def _write_pdf(path: Path, pages: list[str]) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 72), text, fontsize=11)
    document.save(path)
    document.close()
