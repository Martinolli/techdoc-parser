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

from techdoc_parser.evaluation.source_accuracy import (  # noqa: E402
    FAIL,
    PASS,
    REVIEW,
    SourceAccuracyFinding,
    SourceAccuracyMetricResult,
    SourceAccuracyPageResult,
    source_accuracy_page_result_to_dict,
)
from techdoc_parser.evaluation.visual_review import (  # noqa: E402
    ACCEPTED,
    ACCEPTED_WITH_LIMITATIONS,
    CONFIRMED_PARSER_DEFECT,
    INCOMPLETE,
    REJECTED,
    REQUIRED_VISUAL_CHECK_FIELDS,
    VisualReviewDecision,
    assess_p0_pilot_acceptance,
    default_visual_review_decision,
    merge_visual_review_decision,
    p0_pilot_acceptance_result_to_json,
    validate_visual_review_checklist,
    visual_review_decision_to_dict,
)
from techdoc_parser.evaluation.visual_review_reporting import (  # noqa: E402
    p0_pilot_acceptance_result_to_markdown,
    write_p0_visual_review_package,
    write_p0_visual_review_reports,
)

TOOL = ROOT / "tools" / "evaluation" / "run-p0-visual-review.py"


class P0VisualReviewTests(unittest.TestCase):
    def test_checklist_validation_accepts_valid_payload(self):
        decision = validate_visual_review_checklist(
            _decision_payload(),
            expected_document_key="doc",
            expected_pdf_page_index=0,
        )

        self.assertEqual(decision.review_status, "completed")
        self.assertEqual(decision.checklist["text_complete"], "pass")

    def test_checklist_validation_rejects_missing_bad_identity_and_unsafe_payloads(
        self,
    ):
        cases = [
            ({**_decision_payload(), "document_key": "other"}, "document_key"),
            ({**_decision_payload(), "pdf_page_index": 1}, "pdf_page_index"),
            (_without_check("text_complete"), "Missing visual checklist"),
            (_with_check("text_complete", "unknown"), "Invalid checklist value"),
            ({**_decision_payload(), "pdf_path": "doc.pdf"}, "Protected data field"),
            ({**_decision_payload(), "sanitized_notes": "x" * 501}, "too long"),
            (
                {**_decision_payload(), "sanitized_notes": "C:\\secret\\doc.pdf"},
                "Absolute",
            ),
        ]

        for payload, message in cases:
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                validate_visual_review_checklist(
                    payload,
                    expected_document_key="doc",
                    expected_pdf_page_index=0,
                )

    def test_pending_checklist_remains_pending_and_blocks_acceptance(self):
        pending = default_visual_review_decision(
            document_key="doc",
            pdf_page_index=0,
            page_number=1,
        )
        merged = merge_visual_review_decision(_page(PASS), pending)
        result = assess_p0_pilot_acceptance((merged,))

        self.assertEqual(merged.visual_review_status, "pending")
        self.assertEqual(merged.final_page_outcome, REVIEW)
        self.assertEqual(result.outcome, INCOMPLETE)
        self.assertEqual(result.summary["pending_pages"], 1)

    def test_merge_preserves_automated_evidence_and_adds_visual_evidence(self):
        page = _page(REVIEW)
        decision = _decision(review_status="completed")
        merged = merge_visual_review_decision(page, decision)

        self.assertEqual(page.automated_outcome, REVIEW)
        self.assertEqual(page.final_page_outcome, REVIEW)
        self.assertEqual(merged.automated_outcome, REVIEW)
        self.assertEqual(merged.final_page_outcome, PASS)
        self.assertEqual(merged.findings[: len(page.findings)], page.findings)
        self.assertIn("AUTOMATED_REVIEW_VISUAL_PASS", _codes(merged))
        self.assertNotEqual(id(page.findings), id(merged.findings))

    def test_visual_fail_overrides_automated_pass_and_confirms_defect(self):
        decision = _decision(
            review_status="completed",
            checks={"fabricated_content_absent": "fail"},
        )
        merged = merge_visual_review_decision(_page(PASS), decision)

        self.assertEqual(merged.final_page_outcome, FAIL)
        self.assertIn("VISUAL_FABRICATION_DETECTED", _codes(merged))
        defect = next(
            finding
            for finding in merged.findings
            if finding.code == "VISUAL_FABRICATION_DETECTED"
        )
        self.assertEqual(defect.category, CONFIRMED_PARSER_DEFECT)
        self.assertIn("AUTOMATED_PASS_VISUAL_FAIL", _codes(merged))

    def test_visual_review_and_second_review_remain_review(self):
        table_review = merge_visual_review_decision(
            _page(PASS),
            _decision(
                review_status="completed",
                checks={"table_evidence_usable": "review"},
            ),
        )
        equation_second = merge_visual_review_decision(
            _page(PASS),
            _decision(
                review_status="needs_second_review",
                checks={"equation_preserved": "review"},
            ),
        )

        self.assertEqual(table_review.final_page_outcome, REVIEW)
        self.assertEqual(equation_second.final_page_outcome, REVIEW)
        self.assertIn("VISUAL_LAYOUT_LIMITATION", _codes(table_review))
        self.assertEqual(equation_second.visual_review_status, "needs_second_review")

    def test_non_applicable_content_check_is_allowed(self):
        decision = _decision(
            review_status="completed",
            checks={"table_evidence_usable": "not_applicable"},
        )
        merged = merge_visual_review_decision(_page(PASS), decision)

        self.assertEqual(merged.final_page_outcome, PASS)

    def test_page_provenance_fail_blocks(self):
        merged = merge_visual_review_decision(
            _page(PASS),
            _decision(
                review_status="completed",
                checks={"page_provenance_correct": "fail"},
            ),
        )
        result = assess_p0_pilot_acceptance((merged,))

        self.assertEqual(result.outcome, REJECTED)
        self.assertIn("VISUAL_PAGE_PROVENANCE_ERROR", result.blocking_finding_codes)

    def test_acceptance_aggregation(self):
        accepted = assess_p0_pilot_acceptance(
            (merge_visual_review_decision(_page(PASS), _decision()),)
        )
        limited = assess_p0_pilot_acceptance(
            (
                merge_visual_review_decision(_page(PASS), _decision()),
                merge_visual_review_decision(
                    _page(PASS, index=1),
                    _decision(index=1, checks={"chunks_coherent": "review"}),
                ),
            )
        )
        rejected = assess_p0_pilot_acceptance(
            (
                merge_visual_review_decision(
                    _page(PASS),
                    _decision(checks={"text_complete": "fail"}),
                ),
            )
        )

        self.assertEqual(accepted.document_outcomes["doc"], ACCEPTED)
        self.assertEqual(limited.outcome, ACCEPTED_WITH_LIMITATIONS)
        self.assertTrue(limited.accepted_limitation_codes)
        self.assertEqual(rejected.outcome, REJECTED)
        self.assertTrue(rejected.blocking_finding_codes)

    def test_reports_are_deterministic_sanitized_and_write_gated(self):
        result = assess_p0_pilot_acceptance(
            (merge_visual_review_decision(_page(PASS), _decision()),)
        )
        first = p0_pilot_acceptance_result_to_json(result)
        second = p0_pilot_acceptance_result_to_json(result)
        markdown = p0_pilot_acceptance_result_to_markdown(result)

        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))
        self.assertTrue(markdown.endswith("\n"))
        self.assertNotIn("source text", first.lower())
        self.assertNotIn(str(ROOT), first)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            with self.assertRaises(PermissionError):
                write_p0_visual_review_reports(result, json_path=path)
            written = write_p0_visual_review_reports(
                result,
                json_path=path,
                allow_report_write=True,
            )
            self.assertEqual(written, (path,))
            json.loads(path.read_text(encoding="utf-8"))

    def test_local_package_requires_permission_and_preserves_existing_checklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_dir = root / "review"
            input_dir.mkdir()
            _write_pdf(input_dir / "doc.pdf")
            page = _page(PASS)
            checklist = output_dir / "doc" / "page_1" / "review_checklist.json"

            with self.assertRaises(PermissionError):
                write_p0_visual_review_package(
                    output_dir=output_dir,
                    input_dir=input_dir,
                    page_results=(page,),
                )
            written = write_p0_visual_review_package(
                output_dir=output_dir,
                input_dir=input_dir,
                page_results=(page,),
                allow_local_write=True,
            )
            original = checklist.read_text(encoding="utf-8")
            second = write_p0_visual_review_package(
                output_dir=output_dir,
                input_dir=input_dir,
                page_results=(page,),
                allow_local_write=True,
            )

            self.assertTrue((output_dir / "doc" / "page_1" / "page.png").is_file())
            self.assertTrue((output_dir / "doc" / "page_1" / "review.html").is_file())
            self.assertTrue(
                (output_dir / "doc" / "page_1" / "automated_summary.json").is_file()
            )
            self.assertEqual(checklist.read_text(encoding="utf-8"), original)
            self.assertGreaterEqual(len(written), len(second))
            for path in written:
                path.resolve().relative_to(output_dir.resolve())

    def test_cli_pending_completed_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "plan.json"
            report = root / "report.json"
            evidence = root / "evidence"
            _write_plan(plan)
            _write_report(report, _page(PASS))

            pending = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--plan",
                    str(plan),
                    "--automated-report",
                    str(report),
                    "--evidence-dir",
                    str(evidence),
                    "--all-p0",
                    "--list-pending",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            incomplete = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--plan",
                    str(plan),
                    "--automated-report",
                    str(report),
                    "--evidence-dir",
                    str(evidence),
                    "--all-p0",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            checklist = evidence / "doc" / "page_1"
            checklist.mkdir(parents=True)
            (checklist / "review_checklist.json").write_text(
                json.dumps(visual_review_decision_to_dict(_decision())),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--plan",
                    str(plan),
                    "--automated-report",
                    str(report),
                    "--evidence-dir",
                    str(evidence),
                    "--all-p0",
                    "--merge-checklists",
                    "--list-completed",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )
            accepted = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--plan",
                    str(plan),
                    "--automated-report",
                    str(report),
                    "--evidence-dir",
                    str(evidence),
                    "--all-p0",
                    "--merge-checklists",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

        self.assertEqual(pending.returncode, 0)
        self.assertIn("doc\t1\tpending", pending.stdout)
        self.assertEqual(incomplete.returncode, 2)
        self.assertIn("Pilot acceptance outcome: INCOMPLETE", incomplete.stdout)
        self.assertEqual(completed.returncode, 0)
        self.assertIn("doc\t1\tcompleted\tPASS", completed.stdout)
        self.assertEqual(accepted.returncode, 0)
        self.assertIn("Pilot acceptance outcome: ACCEPTED", accepted.stdout)


def _page(outcome: str, *, index: int = 0) -> SourceAccuracyPageResult:
    finding = SourceAccuracyFinding(
        finding_id=f"doc:p{index}:finding:001",
        document_key="doc",
        pdf_page_index=index,
        page_number=index + 1,
        category="MANUAL_REVIEW_REQUIRED"
        if outcome == REVIEW
        else "SOURCE_PROXY_LIMITATION",
        severity="informational",
        code="AUTOMATED_REVIEW_FINDING" if outcome == REVIEW else "AUTOMATED_NOTE",
        message="Synthetic sanitized automated finding.",
        requires_manual_review=outcome == REVIEW,
    )
    return SourceAccuracyPageResult(
        document_key="doc",
        filename="doc.pdf",
        pdf_page_index=index,
        page_number=index + 1,
        printed_page_label=str(index + 1),
        evaluation_roles=("ordinary_text",),
        automated_outcome=outcome,
        visual_review_status="pending",
        visual_review_outcome=REVIEW,
        final_page_outcome=FAIL if outcome == FAIL else REVIEW,
        metrics=(
            SourceAccuracyMetricResult(
                name="automated_source_proxy",
                status="fail" if outcome == FAIL else "pass",
                value=outcome,
            ),
        ),
        findings=(finding,),
        parser_counts={"text_blocks": 1, "chunks": 1},
        source_proxy_counts={"word_count": 12, "source_hash_verified_locally": True},
        review_artifact_labels=("doc/page_1/review.html",),
    )


def _decision(
    *,
    review_status: str = "completed",
    checks: dict[str, str] | None = None,
    index: int = 0,
) -> VisualReviewDecision:
    payload = _decision_payload(index=index)
    payload["review_status"] = review_status
    for key, value in (checks or {}).items():
        payload["checklist"][key] = value
    return validate_visual_review_checklist(
        payload,
        expected_document_key="doc",
        expected_pdf_page_index=index,
    )


def _decision_payload(*, index: int = 0) -> dict[str, object]:
    return {
        "document_key": "doc",
        "pdf_page_index": index,
        "page_number": index + 1,
        "reviewer_id": "owner",
        "review_status": "completed",
        "checklist": {field: "pass" for field in REQUIRED_VISUAL_CHECK_FIELDS},
        "finding_codes": [],
        "sanitized_notes": "Synthetic sanitized owner-review note.",
    }


def _without_check(field_name: str) -> dict[str, object]:
    payload = _decision_payload()
    checks = dict(payload["checklist"])
    checks.pop(field_name)
    payload["checklist"] = checks
    return payload


def _with_check(field_name: str, value: str) -> dict[str, object]:
    payload = _decision_payload()
    checks = dict(payload["checklist"])
    checks[field_name] = value
    payload["checklist"] = checks
    return payload


def _codes(page: SourceAccuracyPageResult) -> set[str]:
    return {finding.code for finding in page.findings}


def _write_pdf(path: Path) -> None:
    document = fitz.open()
    try:
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 72), "Synthetic review package PDF text.", fontsize=10)
        document.save(path)
    finally:
        document.close()


def _write_plan(path: Path) -> None:
    payload = {
        "pages": [
            {
                "document_key": "doc",
                "filename": "doc.pdf",
                "pdf_page_index": 0,
                "page_number": 1,
                "printed_page_label": "1",
                "evaluation_roles": ["ordinary_text"],
                "priority": "P0",
                "selection_reason": ["synthetic"],
                "review_status": "approved_for_execution",
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_report(path: Path, page: SourceAccuracyPageResult) -> None:
    payload = {
        "page_results": [source_accuracy_page_result_to_dict(page)],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
