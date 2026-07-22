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

from techdoc_parser.core import TextBlock  # noqa: E402
from techdoc_parser.evaluation import (  # noqa: E402
    BLOCKED,
    COMPLETE,
    CONFIRMED_PARSER_DEFECT,
    EVALUATION_FRAMEWORK_DEFECT,
    NEEDS_VISUAL_CONFIRMATION,
    REVIEW,
    SOURCE_PROXY_LIMITATION,
    FailureTriageCase,
    SourceAccuracyMetricResult,
    SourceAccuracyPageResult,
    SourceAccuracyPlanPage,
    default_root_cause_checklist,
    failure_triage_result_to_json,
    failure_triage_result_to_markdown,
    load_default_p0_failure_triage_plan,
    load_p0_failure_triage_plan,
    run_p0_failure_triage,
    triage_p0_failure_case,
    validate_root_cause_checklist,
    write_failure_triage_evidence,
    write_failure_triage_reports,
)
from techdoc_parser.ingestion import PDFLoader  # noqa: E402

PLAN = ROOT / "tests" / "fixtures" / "pilot_corpus" / "p0_failure_triage_plan.json"
TOOL = ROOT / "tools" / "evaluation" / "run-p0-failure-triage.py"


class P0FailureTriageTests(unittest.TestCase):
    def test_committed_triage_plan_loads_selected_p0_subset(self):
        cases = load_default_p0_failure_triage_plan(PLAN)

        self.assertEqual(len(cases), 10)
        self.assertEqual(cases[0].case_id, "control_aircraft_stability_p1")
        self.assertTrue(all(case.priority == "P0" for case in cases))
        self.assertFalse(any(Path(case.filename).is_absolute() for case in cases))
        self.assertIn(
            "triage_faa_order_p29_chunk_gap",
            {case.case_id for case in cases},
        )

    def test_plan_validation_rejects_duplicate_non_p0_and_non_approved_page(self):
        case = _case("case_a", filename="synthetic.pdf")
        approved = [_approved_page("synthetic.pdf")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            duplicate = root / "duplicate.json"
            _write_plan(duplicate, [case, case])
            non_p0 = root / "non-p0.json"
            _write_plan(non_p0, [{**case, "priority": "P1"}])
            non_approved = root / "non-approved.json"
            _write_plan(non_approved, [{**case, "pdf_page_index": 1, "page_number": 2}])

            with self.assertRaisesRegex(ValueError, "Duplicate triage case_id"):
                load_p0_failure_triage_plan(duplicate, approved_plan=approved)
            with self.assertRaisesRegex(ValueError, "not priority P0"):
                load_p0_failure_triage_plan(non_p0, approved_plan=approved)
            with self.assertRaisesRegex(ValueError, "not in the approved P0 plan"):
                load_p0_failure_triage_plan(non_approved, approved_plan=approved)

    def test_missing_source_file_blocks_case_without_parser_work(self):
        result = run_p0_failure_triage(
            input_dir=ROOT / "missing",
            plan=[_triage_case("missing", filename="missing.pdf")],
        )

        self.assertEqual(result.outcome, BLOCKED)
        self.assertEqual(result.cases[0].final_triage_status, BLOCKED)

    def test_duplicate_from_source_proxy_is_not_parser_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            _write_pdf(pdf, ["duplicate line", "duplicate line"])
            document = PDFLoader(str(pdf)).load()
            case = _triage_case(
                "dup_source",
                filename=pdf.name,
                codes=("DUPLICATE_TEXT_LINES",),
                dimensions=("duplicate_text",),
            )

            result = triage_p0_failure_case(
                source_path=pdf,
                case=case,
                page_result=_page_result(case),
                parser_document=document,
            )

        finding = result.triage_findings[0]
        self.assertEqual(finding.root_cause_classification, SOURCE_PROXY_LIMITATION)
        self.assertTrue(finding.requires_visual_confirmation)

    def test_parser_introduced_duplicate_is_probable_parser_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            _write_pdf(pdf, ["unique visible line"])
            document = PDFLoader(str(pdf)).load()
            original = document.pages[0].text_blocks[0]
            duplicate = TextBlock(
                id="page-1-text-duplicate",
                text=original.text or "",
                source=original.source,
                normalized_text=original.normalized_text,
            )
            document.pages[0].text_blocks.append(duplicate)
            document.pages[0].blocks.append(duplicate)
            case = _triage_case(
                "dup_parser",
                filename=pdf.name,
                codes=("DUPLICATE_TEXT_LINES",),
                dimensions=("duplicate_text",),
            )

            result = triage_p0_failure_case(
                source_path=pdf,
                case=case,
                page_result=_page_result(case),
                parser_document=document,
            )

        finding = result.triage_findings[0]
        self.assertEqual(finding.root_cause_classification, CONFIRMED_PARSER_DEFECT)
        self.assertEqual(finding.recommended_corrective_phase, "13I-c2A")

    def test_raw_coverage_status_failure_is_evaluator_defect_when_value_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            _write_pdf(pdf, ["coverage line"])
            document = PDFLoader(str(pdf)).load()
            case = _triage_case(
                "coverage",
                filename=pdf.name,
                codes=("RAW_CHARACTER_COVERAGE_STATUS_FAIL",),
                dimensions=("text_coverage",),
            )

            result = triage_p0_failure_case(
                source_path=pdf,
                case=case,
                page_result=_page_result(case),
                parser_document=document,
            )

        finding = result.triage_findings[0]
        self.assertEqual(finding.root_cause_classification, EVALUATION_FRAMEWORK_DEFECT)
        self.assertFalse(finding.requires_visual_confirmation)

    def test_reading_order_on_complex_layout_remains_visual_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            _write_pdf(pdf, ["first", "second"])
            document = PDFLoader(str(pdf)).load()
            case = _triage_case(
                "order",
                filename=pdf.name,
                codes=("READING_ORDER_INVERSION",),
                dimensions=("reading_order",),
            )

            result = triage_p0_failure_case(
                source_path=pdf,
                case=case,
                page_result=_page_result(case),
                parser_document=document,
            )

        finding = result.triage_findings[0]
        self.assertEqual(finding.root_cause_classification, NEEDS_VISUAL_CONFIRMATION)
        self.assertEqual(result.final_triage_status, REVIEW)

    def test_chunk_gap_not_reproduced_is_evaluator_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            _write_pdf(pdf, ["chunk text"])
            document = PDFLoader(str(pdf)).load()
            case = _triage_case(
                "chunk",
                filename=pdf.name,
                codes=("CHUNK_SOURCE_COVERAGE_GAP",),
                dimensions=("chunk_source_coverage",),
            )

            result = triage_p0_failure_case(
                source_path=pdf,
                case=case,
                page_result=_page_result(case),
                parser_document=document,
            )

        finding = result.triage_findings[0]
        self.assertEqual(finding.root_cause_classification, EVALUATION_FRAMEWORK_DEFECT)
        self.assertEqual(finding.recommended_corrective_phase, "13I-c2E")

    def test_visual_checklist_validation_rejects_unknown_values(self):
        checklist = default_root_cause_checklist("case")
        checklist["checks"]["missing_text_is_visible"] = "yes"

        with self.assertRaisesRegex(ValueError, "Invalid checklist value"):
            validate_root_cause_checklist(checklist)

    def test_aggregate_review_and_serialization_are_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "synthetic.pdf"
            _write_pdf(pdf, ["aggregate line"])
            case = _triage_case(
                "aggregate",
                filename=pdf.name,
                codes=("RAW_CHARACTER_COVERAGE_STATUS_FAIL",),
                dimensions=("text_coverage",),
            )
            result = run_p0_failure_triage(input_dir=root, plan=[case])
            json_text = failure_triage_result_to_json(result)
            markdown = failure_triage_result_to_markdown(result)

        self.assertEqual(result.outcome, COMPLETE)
        self.assertEqual(json_text, failure_triage_result_to_json(result))
        self.assertTrue(json_text.endswith("\n"))
        self.assertTrue(markdown.endswith("\n"))
        self.assertNotIn("aggregate line", json_text)
        self.assertIn("Parser behavior changed: `False`", markdown)

    def test_report_and_evidence_writes_are_explicitly_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "synthetic.pdf"
            _write_pdf(pdf, ["local evidence line"])
            result = run_p0_failure_triage(
                input_dir=root,
                plan=[
                    _triage_case(
                        "write_case",
                        filename=pdf.name,
                        codes=("RAW_CHARACTER_COVERAGE_STATUS_FAIL",),
                        dimensions=("text_coverage",),
                    )
                ],
            )
            report = root / "report.json"
            evidence_dir = root / "evidence"

            with self.assertRaises(PermissionError):
                write_failure_triage_reports(result, json_path=report)
            with self.assertRaises(PermissionError):
                write_failure_triage_evidence(
                    result=result,
                    output_dir=evidence_dir,
                    input_dir=root,
                )

            report_paths = write_failure_triage_reports(
                result,
                json_path=report,
                allow_report_write=True,
            )
            evidence_paths = write_failure_triage_evidence(
                result=result,
                output_dir=evidence_dir,
                input_dir=root,
                allow_local_write=True,
            )

            self.assertEqual(report_paths, (report,))
            self.assertTrue((evidence_dir / "write_case/source_proxy.json").is_file())
            self.assertTrue((evidence_dir / "write_case/review.html").is_file())
            self.assertGreaterEqual(len(evidence_paths), 11)

    def test_cli_lists_cases_and_requires_selection(self):
        list_completed = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "--input-dir",
                "input",
                "--plan",
                str(PLAN),
                "--list-cases",
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
        self.assertEqual(len(list_completed.stdout.strip().splitlines()), 10)
        self.assertEqual(missing_selection.returncode, 2)
        self.assertIn("Select --all-cases", missing_selection.stderr)

    def test_cli_report_write_guard_and_complete_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "synthetic.pdf"
            plan_path = root / "plan.json"
            report_path = root / "triage.json"
            approved_filename = (
                "Introduction_Aircraft_Stability_And_Control_Course_Notes_M&AE_5070.pdf"
            )
            pdf = root / approved_filename
            _write_pdf(pdf, ["cli line"])
            _write_plan(
                plan_path,
                [
                    _case(
                        "cli_case",
                        document_key="aircraft_stability_control",
                        filename=approved_filename,
                        codes=["RAW_CHARACTER_COVERAGE_STATUS_FAIL"],
                        dimensions=["text_coverage"],
                    )
                ],
            )

            blocked = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--input-dir",
                    str(root),
                    "--plan",
                    str(plan_path),
                    "--all-cases",
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
                    "--all-cases",
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
        self.assertEqual(allowed.returncode, 0)
        self.assertIn("Diagnosis only: true", allowed.stdout)

    def test_cli_merges_existing_root_cause_checklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "plan.json"
            report_path = root / "triage.json"
            evidence_dir = root / "evidence"
            approved_filename = (
                "Introduction_Aircraft_Stability_And_Control_Course_Notes_M&AE_5070.pdf"
            )
            _write_pdf(root / approved_filename, ["cli line"])
            _write_plan(
                plan_path,
                [
                    _case(
                        "cli_case",
                        document_key="aircraft_stability_control",
                        filename=approved_filename,
                        codes=["RAW_CHARACTER_COVERAGE_STATUS_FAIL"],
                        dimensions=["text_coverage"],
                    )
                ],
            )
            checklist = default_root_cause_checklist("cli_case")
            checklist["checks"] = {key: "not_applicable" for key in checklist["checks"]}
            checklist_path = evidence_dir / "cli_case" / "root_cause_checklist.json"
            checklist_path.parent.mkdir(parents=True)
            checklist_path.write_text(
                json.dumps(checklist, indent=2) + "\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--input-dir",
                    str(root),
                    "--plan",
                    str(plan_path),
                    "--all-cases",
                    "--output-dir",
                    str(evidence_dir),
                    "--allow-local-write",
                    "--merge-review-checklists",
                    "--report-json",
                    str(report_path),
                    "--allow-report-write",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0)
        self.assertIn("Merged review checklists: 1", completed.stdout)
        self.assertEqual(report["cases"][0]["visual_review_status"], "completed")


def _write_pdf(path: Path, lines: list[str]) -> None:
    document = fitz.open()
    try:
        page = document.new_page(width=612, height=792)
        for index, line in enumerate(lines):
            page.insert_text((72, 72 + index * 18), line, fontsize=10)
        document.save(path)
    finally:
        document.close()


def _case(
    case_id: str,
    *,
    filename: str,
    document_key: str = "synthetic_document",
    codes: list[str] | None = None,
    dimensions: list[str] | None = None,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "document_key": document_key,
        "filename": filename,
        "pdf_page_index": 0,
        "page_number": 1,
        "original_finding_codes": codes or ["DUPLICATE_TEXT_LINES"],
        "failure_dimensions": dimensions or ["duplicate_text"],
        "selection_reason": ["synthetic"],
        "priority": "P0",
        "visual_review_required": True,
    }


def _triage_case(
    case_id: str,
    *,
    filename: str,
    codes: tuple[str, ...] = ("DUPLICATE_TEXT_LINES",),
    dimensions: tuple[str, ...] = ("duplicate_text",),
) -> FailureTriageCase:
    return FailureTriageCase(
        case_id=case_id,
        document_key="synthetic_document",
        filename=filename,
        pdf_page_index=0,
        page_number=1,
        original_finding_codes=codes,
        failure_dimensions=dimensions,
        selection_reason=("synthetic",),
        priority="P0",
        visual_review_required=True,
    )


def _approved_page(filename: str) -> SourceAccuracyPlanPage:
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


def _page_result(case: FailureTriageCase) -> SourceAccuracyPageResult:
    return SourceAccuracyPageResult(
        document_key=case.document_key,
        filename=case.filename,
        pdf_page_index=case.pdf_page_index,
        page_number=case.page_number,
        printed_page_label=None,
        evaluation_roles=case.failure_dimensions,
        automated_outcome="FAIL",
        visual_review_status="pending",
        visual_review_outcome="REVIEW",
        final_page_outcome="FAIL",
        metrics=(
            SourceAccuracyMetricResult(
                name="raw_character_coverage",
                status="fail",
                value=1.0,
                threshold=0.95,
                unit="ratio",
            ),
            SourceAccuracyMetricResult(
                name="missing_line_count",
                status="pass",
                value=0,
                threshold=0,
                unit="lines",
            ),
        ),
        findings=(),
        parser_counts={},
        source_proxy_counts={},
        review_artifact_labels=(),
    )


def _write_plan(path: Path, cases: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"cases": cases}), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
