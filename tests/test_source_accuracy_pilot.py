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
    FAIL,
    PASS,
    REVIEW,
    classify_native_text_use,
    evaluate_representative_page,
    load_p0_source_accuracy_plan,
    run_source_accuracy_pilot,
    source_accuracy_pilot_result_to_dict,
    source_accuracy_pilot_result_to_json,
    source_accuracy_pilot_result_to_markdown,
    write_source_accuracy_reports,
)
from techdoc_parser.evaluation.source_accuracy import (  # noqa: E402
    VISUAL_CHECK_FIELDS,
    SourceAccuracyPlanPage,
    validate_visual_review_checklist,
)
from techdoc_parser.evaluation.source_accuracy_reporting import (  # noqa: E402
    write_local_pilot_evidence_package,
)
from techdoc_parser.ingestion import PDFLoader  # noqa: E402

PLAN = ROOT / "tests" / "fixtures" / "pilot_corpus" / "p0_source_accuracy_plan.json"
TOOL = ROOT / "tools" / "evaluation" / "run-source-accuracy-pilot.py"


class SourceAccuracyPilotTests(unittest.TestCase):
    def test_committed_p0_plan_loads_exact_approved_scope(self):
        plan = load_p0_source_accuracy_plan(PLAN)

        self.assertEqual(len(plan), 32)
        self.assertEqual(len({page.document_key for page in plan}), 8)
        self.assertTrue(all(page.priority == "P0" for page in plan))
        self.assertTrue(
            all(page.review_status == "approved_for_execution" for page in plan)
        )
        self.assertFalse(any(Path(page.filename).is_absolute() for page in plan))
        self.assertEqual(
            {page.page_number for page in plan if page.document_key == "mil_std_882e"},
            {1, 14, 17, 33},
        )

    def test_plan_validation_rejects_non_p0_duplicate_and_path_entries(self):
        base = {
            "pages": [
                {
                    "document_key": "doc",
                    "filename": "doc.pdf",
                    "pdf_page_index": 0,
                    "page_number": 1,
                    "printed_page_label": None,
                    "evaluation_roles": ["ordinary_text"],
                    "priority": "P0",
                    "selection_reason": ["synthetic"],
                    "review_status": "approved_for_execution",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            duplicate = root / "duplicate.json"
            duplicate.write_text(
                json.dumps({**base, "pages": base["pages"] * 2}),
                encoding="utf-8",
            )
            non_p0 = root / "non-p0.json"
            non_p0_data = json.loads(json.dumps(base))
            non_p0_data["pages"][0]["priority"] = "P1"
            non_p0.write_text(json.dumps(non_p0_data), encoding="utf-8")
            bad_path = root / "bad-path.json"
            bad_path_data = json.loads(json.dumps(base))
            bad_path_data["pages"][0]["filename"] = "../doc.pdf"
            bad_path.write_text(json.dumps(bad_path_data), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Duplicate plan page"):
                load_p0_source_accuracy_plan(duplicate)
            with self.assertRaisesRegex(ValueError, "not priority P0"):
                load_p0_source_accuracy_plan(non_p0)
            with self.assertRaisesRegex(ValueError, "basename"):
                load_p0_source_accuracy_plan(bad_path)

    def test_native_text_classification_is_explicit_and_does_not_ocr(self):
        self.assertEqual(
            classify_native_text_use(
                character_count=120,
                word_count=4,
                image_count=0,
            ),
            "native_text_usable",
        )
        self.assertEqual(
            classify_native_text_use(
                character_count=20,
                word_count=2,
                image_count=1,
            ),
            "image_dominant",
        )
        self.assertEqual(
            classify_native_text_use(character_count=0, word_count=0, image_count=0),
            "uncertain",
        )

    def test_single_page_pending_visual_review_prevents_final_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            _write_pdf(pdf, [_text_page("source accuracy baseline")])

            result = evaluate_representative_page(
                source_path=pdf,
                document_key="synthetic_document",
                pdf_page_index=0,
                page_number=1,
                evaluation_roles=("ordinary_text",),
            )

        self.assertEqual(result.automated_outcome, PASS)
        self.assertEqual(result.visual_review_status, "pending")
        self.assertEqual(result.final_page_outcome, REVIEW)
        self.assertFalse(result.full_document_accuracy_evaluated)
        self.assertFalse(result.ocr_accuracy_evaluated)
        self.assertTrue(result.operational_full_document_parse)
        self.assertIn("VISUAL_REVIEW_PENDING", {item.code for item in result.findings})

    def test_completed_clean_visual_checklist_allows_final_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            _write_pdf(pdf, [_text_page("source accuracy visual pass")])

            result = evaluate_representative_page(
                source_path=pdf,
                document_key="synthetic_document",
                pdf_page_index=0,
                page_number=1,
                evaluation_roles=("ordinary_text",),
                checklist=_completed_checklist(),
            )

        self.assertEqual(result.automated_outcome, PASS)
        self.assertEqual(result.visual_review_status, "completed")
        self.assertEqual(result.visual_review_outcome, PASS)
        self.assertEqual(result.final_page_outcome, PASS)

    def test_parser_text_loss_is_a_fail_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            _write_pdf(pdf, [_text_page("source accuracy text loss")])
            parser_document = PDFLoader(str(pdf)).load()
            parser_document.pages[0].text_blocks[0].text = "shortened parser text"

            result = evaluate_representative_page(
                source_path=pdf,
                document_key="synthetic_document",
                pdf_page_index=0,
                page_number=1,
                evaluation_roles=("ordinary_text",),
                parser_document=parser_document,
                checklist=_completed_checklist(),
            )

        self.assertEqual(result.automated_outcome, FAIL)
        self.assertEqual(result.final_page_outcome, FAIL)
        self.assertIn("TEXT_COVERAGE_LOW", {item.code for item in result.findings})
        self.assertIn("SOURCE_LINES_MISSING", {item.code for item in result.findings})

    def test_expected_table_role_without_automated_entity_is_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            _write_pdf(pdf, [_text_page("table role review")])

            result = evaluate_representative_page(
                source_path=pdf,
                document_key="synthetic_document",
                pdf_page_index=0,
                page_number=1,
                evaluation_roles=("ordinary_text", "table"),
                checklist=_completed_checklist(),
            )

        self.assertEqual(result.automated_outcome, REVIEW)
        self.assertEqual(result.final_page_outcome, REVIEW)
        self.assertIn(
            "TABLE_EVIDENCE_NOT_AUTOMATED",
            {item.code for item in result.findings},
        )

    def test_missing_source_file_is_fail_without_parser_work(self):
        result = evaluate_representative_page(
            source_path=ROOT / "missing-source.pdf",
            document_key="missing_document",
            pdf_page_index=0,
            page_number=1,
            evaluation_roles=("ordinary_text",),
        )

        self.assertEqual(result.final_page_outcome, FAIL)
        self.assertFalse(result.operational_full_document_parse)
        self.assertIn("SOURCE_FILE_MISSING", {item.code for item in result.findings})

    def test_pilot_serialization_is_sanitized_and_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "synthetic.pdf"
            _write_pdf(pdf, [_text_page("sanitized report")])
            plan = [_plan_page(pdf.name)]

            result = run_source_accuracy_pilot(input_dir=root, plan=plan)
            first = source_accuracy_pilot_result_to_json(result)
            second = source_accuracy_pilot_result_to_json(result)
            markdown = source_accuracy_pilot_result_to_markdown(result)
            data = source_accuracy_pilot_result_to_dict(result)

        self.assertEqual(first, second)
        self.assertIn("source_accuracy_scope: representative_p0_pages", markdown)
        self.assertIn("full_document_accuracy_evaluated: false", markdown)
        self.assertNotIn("source_sha256", first)
        self.assertNotIn("sanitized report", first)
        self.assertEqual(data["page_count"], 1)
        self.assertEqual(data["ocr_accuracy_evaluated"], False)

    def test_report_and_local_evidence_writes_are_explicitly_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "synthetic.pdf"
            _write_pdf(pdf, [_text_page("local evidence")])
            result = run_source_accuracy_pilot(
                input_dir=root,
                plan=[_plan_page(pdf.name)],
            )
            report_path = root / "report.json"
            evidence_dir = root / "evidence"

            with self.assertRaises(PermissionError):
                write_source_accuracy_reports(result, json_path=report_path)
            with self.assertRaises(PermissionError):
                write_local_pilot_evidence_package(
                    output_dir=evidence_dir,
                    input_dir=root,
                    result=result,
                )

            written_report = write_source_accuracy_reports(
                result,
                json_path=report_path,
                allow_report_write=True,
            )
            written_evidence = write_local_pilot_evidence_package(
                output_dir=evidence_dir,
                input_dir=root,
                result=result,
                allow_local_write=True,
            )

            self.assertEqual(written_report, (report_path,))
            self.assertTrue(
                (evidence_dir / "synthetic_document/page_1/page.png").is_file()
            )
            self.assertTrue(
                (evidence_dir / "synthetic_document/page_1/review.html").is_file()
            )
            self.assertGreaterEqual(len(written_evidence), 8)

    def test_visual_checklist_validation_rejects_unknown_values(self):
        checklist = _completed_checklist()
        checklist["checks"]["text_complete"] = "unknown"

        with self.assertRaisesRegex(ValueError, "Invalid checklist value"):
            validate_visual_review_checklist(checklist)

    def test_cli_lists_pages_and_requires_selection_for_execution(self):
        list_completed = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "--input-dir",
                "input",
                "--plan",
                str(PLAN),
                "--list-pages",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        missing_selection = subprocess.run(
            [sys.executable, str(TOOL), "--input-dir", "input", "--plan", str(PLAN)],
            check=False,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        self.assertEqual(list_completed.returncode, 0)
        self.assertEqual(len(list_completed.stdout.strip().splitlines()), 32)
        self.assertEqual(missing_selection.returncode, 2)
        self.assertIn("Select --all-p0", missing_selection.stderr)

    def test_cli_report_write_guard_and_review_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "synthetic.pdf"
            plan_path = root / "plan.json"
            report_path = root / "pilot.json"
            _write_pdf(pdf, [_text_page("cli report")])
            _write_plan(plan_path, pdf.name)

            blocked = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--input-dir",
                    str(root),
                    "--plan",
                    str(plan_path),
                    "--all-p0",
                    "--report-json",
                    str(report_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            allowed = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--input-dir",
                    str(root),
                    "--plan",
                    str(plan_path),
                    "--all-p0",
                    "--report-json",
                    str(report_path),
                    "--allow-report-write",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

        self.assertEqual(blocked.returncode, 1)
        self.assertEqual(allowed.returncode, 2)
        self.assertIn("Outcome: REVIEW", allowed.stdout)


def _write_pdf(path: Path, pages: list[dict[str, object]]) -> None:
    document = fitz.open()
    try:
        for page_spec in pages:
            page = document.new_page(width=612, height=792)
            for x, y, text in page_spec["texts"]:
                page.insert_text((float(x), float(y)), str(text), fontsize=10)
        document.save(path)
    finally:
        document.close()


def _text_page(seed: str) -> dict[str, object]:
    text = (
        f"{seed} figure warning procedure shall refer to section two. "
        "This synthetic page contains enough native text for source accuracy "
        "tests and does not reproduce any pilot corpus source text."
    )
    return {"texts": ((72, 72, text),)}


def _plan_page(filename: str):
    return SourceAccuracyPlanPage(
        document_key="synthetic_document",
        filename=filename,
        pdf_page_index=0,
        page_number=1,
        printed_page_label=None,
        evaluation_roles=("ordinary_text",),
        priority="P0",
        selection_reason=("synthetic",),
    )


def _write_plan(path: Path, filename: str) -> Path:
    payload = {
        "pages": [
            {
                "document_key": "synthetic_document",
                "filename": filename,
                "pdf_page_index": 0,
                "page_number": 1,
                "printed_page_label": None,
                "evaluation_roles": ["ordinary_text"],
                "priority": "P0",
                "selection_reason": ["synthetic"],
                "review_status": "approved_for_execution",
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _completed_checklist() -> dict[str, object]:
    return {
        "page_id": "synthetic_document:p0",
        "checks": {field: "pass" for field in VISUAL_CHECK_FIELDS},
        "reviewer_notes": "Synthetic complete review.",
    }


if __name__ == "__main__":
    unittest.main()
