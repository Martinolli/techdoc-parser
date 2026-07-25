import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation.pilot_closure import (  # noqa: E402
    AcceptedPilotLimitation,
    close_p0_pilot,
    default_accepted_pilot_limitation,
    load_p0_pilot_acceptance_result_from_report,
    p0_pilot_closure_result_to_dict,
    p0_pilot_closure_result_to_json,
)
from techdoc_parser.evaluation.pilot_closure_reporting import (  # noqa: E402
    p0_pilot_closure_result_to_markdown,
    write_p0_pilot_closure_reports,
)
from techdoc_parser.evaluation.source_accuracy import (  # noqa: E402
    FAIL,
    PASS,
    REVIEW,
    SourceAccuracyFinding,
    SourceAccuracyPageResult,
)
from techdoc_parser.evaluation.visual_review import (  # noqa: E402
    ACCEPTED,
    ACCEPTED_WITH_LIMITATIONS,
    BLOCKED,
    COMPLETED,
    INCOMPLETE,
    NEEDS_SECOND_REVIEW,
    PENDING,
    REJECTED,
    P0PilotAcceptanceResult,
    assess_p0_pilot_acceptance,
)

TOOL = ROOT / "tools" / "evaluation" / "close-p0-pilot.py"


class P0PilotClosureTests(unittest.TestCase):
    def test_close_requires_all_32_pages(self):
        with self.assertRaisesRegex(ValueError, "32 pages"):
            close_p0_pilot(
                visual_review_result=_acceptance_result(page_count=31),
                accepted_limitations=(),
            )

    def test_pending_second_review_blocked_and_fail_block_closure(self):
        cases = [
            (_acceptance_result(status=PENDING), "zero pending"),
            (_acceptance_result(status=NEEDS_SECOND_REVIEW), "zero second-review"),
            (_acceptance_result(status=BLOCKED), "zero blocked"),
            (_acceptance_result(final_outcome=FAIL), "final FAIL"),
        ]

        for result, message in cases:
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                close_p0_pilot(
                    visual_review_result=result,
                    accepted_limitations=(),
                )

    def test_filters_stale_active_codes_and_obsolete_recommendation(self):
        result = close_p0_pilot(
            visual_review_result=_acceptance_result(
                finding_codes=(
                    "VISUAL_REVIEW_PENDING",
                    "VISUAL_CHECK_PENDING",
                    "DUPLICATE_TEXT_LINES",
                ),
                accepted_codes=(
                    "VISUAL_REVIEW_PENDING",
                    "VISUAL_CHECK_PENDING",
                    "DUPLICATE_TEXT_LINES",
                ),
                recommendations=("second_review_or_formal_limitation_acceptance",),
            ),
            accepted_limitations=(
                default_accepted_pilot_limitation("DUPLICATE_TEXT_LINES"),
            ),
        )

        self.assertEqual(
            result.resolved_review_state_findings,
            (
                "VISUAL_REVIEW_PENDING",
                "VISUAL_CHECK_PENDING",
            ),
        )
        self.assertEqual(
            result.removed_obsolete_recommendations,
            ("second_review_or_formal_limitation_acceptance",),
        )
        self.assertNotIn(
            "VISUAL_REVIEW_PENDING",
            [item.code for item in result.current_accepted_limitations],
        )
        self.assertIn("VISUAL_REVIEW_PENDING", result.historical_review_findings)
        self.assertIn("DUPLICATE_TEXT_LINES", result.historical_automated_findings)

    def test_accepted_limitation_validation_and_serialization(self):
        table_issue = default_accepted_pilot_limitation(
            "TABLE_FALSE_POSITIVE_ON_FIGURE_PAGE",
            affected_document_keys=("aircraft_system_safety",),
            affected_pages=(52,),
        )
        result = close_p0_pilot(
            visual_review_result=_acceptance_result(review_pages=4),
            accepted_limitations=(
                default_accepted_pilot_limitation("DUPLICATE_TEXT_LINES"),
                default_accepted_pilot_limitation("CHUNK_SECTION_CROSSING_REVIEW"),
                default_accepted_pilot_limitation("TABLE_CANDIDATE_ONLY"),
                table_issue,
            ),
        )
        data = p0_pilot_closure_result_to_dict(result)

        self.assertEqual(result.outcome, ACCEPTED_WITH_LIMITATIONS)
        self.assertEqual(
            [item.code for item in result.current_confirmed_nonblocking_issues],
            ["TABLE_FALSE_POSITIVE_ON_FIGURE_PAGE"],
        )
        self.assertEqual(
            data["confirmed_nonblocking_issues"][0]["affected_document_keys"],
            ["aircraft_system_safety"],
        )
        self.assertEqual(
            data["confirmed_nonblocking_issues"][0]["affected_pages"], [52]
        )
        self.assertEqual(
            [item.code for item in result.current_accepted_limitations],
            [
                "CHUNK_SECTION_CROSSING_REVIEW",
                "DUPLICATE_TEXT_LINES",
                "TABLE_CANDIDATE_ONLY",
            ],
        )

    def test_duplicate_unsupported_and_major_limitations_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            close_p0_pilot(
                visual_review_result=_acceptance_result(),
                accepted_limitations=(
                    default_accepted_pilot_limitation("DUPLICATE_TEXT_LINES"),
                    default_accepted_pilot_limitation("DUPLICATE_TEXT_LINES"),
                ),
            )
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            AcceptedPilotLimitation(
                code="BAD",
                category="TEST",
                severity="critical",
                disposition="accepted_for_pilot",
                affected_document_keys=(),
                affected_pages=(),
                downstream_control=None,
                corrective_status="deferred_refinement",
                message="Synthetic sanitized limitation.",
            )
        with self.assertRaisesRegex(ValueError, "Major"):
            close_p0_pilot(
                visual_review_result=_acceptance_result(),
                accepted_limitations=(
                    AcceptedPilotLimitation(
                        code="MAJOR_TEST",
                        category="TEST",
                        severity="major",
                        disposition="accepted_for_pilot",
                        affected_document_keys=(),
                        affected_pages=(),
                        downstream_control=None,
                        corrective_status="deferred_refinement",
                        message="Synthetic sanitized major limitation.",
                    ),
                ),
            )

    def test_outcome_and_document_aggregation(self):
        accepted = close_p0_pilot(
            visual_review_result=_acceptance_result(),
            accepted_limitations=(),
        )
        limited = close_p0_pilot(
            visual_review_result=_acceptance_result(review_pages=4),
            accepted_limitations=(),
        )
        rejected_source = assess_p0_pilot_acceptance(
            tuple(replace(page, final_page_outcome=FAIL) for page in _pages())
        )
        incomplete_source = assess_p0_pilot_acceptance(
            tuple(replace(page, visual_review_status=PENDING) for page in _pages())
        )

        self.assertEqual(accepted.outcome, ACCEPTED)
        self.assertEqual(limited.outcome, ACCEPTED_WITH_LIMITATIONS)
        self.assertEqual(rejected_source.outcome, REJECTED)
        self.assertEqual(incomplete_source.outcome, INCOMPLETE)
        self.assertEqual(
            limited.document_outcomes["doc_a"],
            ACCEPTED_WITH_LIMITATIONS,
        )

    def test_downstream_authorizations_are_deterministic(self):
        result = close_p0_pilot(
            visual_review_result=_acceptance_result(review_pages=4),
            accepted_limitations=(
                default_accepted_pilot_limitation("DUPLICATE_TEXT_LINES"),
            ),
        )
        first = p0_pilot_closure_result_to_json(result)
        second = p0_pilot_closure_result_to_json(result)

        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))
        self.assertTrue(
            result.downstream_authorizations["controlled_downstream_use_authorized"]
        )
        self.assertFalse(
            result.downstream_authorizations["full_corpus_ingestion_authorized"]
        )
        self.assertFalse(
            result.downstream_authorizations["real_embedding_rebuild_authorized"]
        )
        self.assertFalse(result.downstream_authorizations["astra_rebuild_authorized"])
        self.assertFalse(result.downstream_authorizations["faiss_rebuild_authorized"])

    def test_reporting_is_deterministic_sanitized_and_write_gated(self):
        result = close_p0_pilot(
            visual_review_result=_acceptance_result(review_pages=4),
            accepted_limitations=(
                default_accepted_pilot_limitation("TABLE_CANDIDATE_ONLY"),
            ),
        )
        markdown = p0_pilot_closure_result_to_markdown(result)
        json_text = p0_pilot_closure_result_to_json(result)

        self.assertEqual(markdown, p0_pilot_closure_result_to_markdown(result))
        self.assertNotIn(str(ROOT), json_text)
        self.assertNotIn("source text:", json_text.lower())
        self.assertNotIn('"reviewer_id"', json_text)
        self.assertTrue(markdown.endswith("\n"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "closure.json"
            with self.assertRaises(PermissionError):
                write_p0_pilot_closure_reports(result, json_path=path)
            write_p0_pilot_closure_reports(
                result,
                json_path=path,
                allow_report_write=True,
            )
            json.loads(path.read_text(encoding="utf-8"))

    def test_load_sanitized_visual_report_and_cli(self):
        visual_report = {
            "accepted_limitation_codes": [
                "VISUAL_REVIEW_PENDING",
                "DUPLICATE_TEXT_LINES",
            ],
            "blocking_finding_codes": [],
            "confirmed_defect_counts": {},
            "corrective_phase_recommendations": [
                "second_review_or_formal_limitation_acceptance"
            ],
            "document_outcomes": _document_outcomes(review_pages=4),
            "outcome": ACCEPTED_WITH_LIMITATIONS,
            "page_results": [
                {
                    "accepted_limitation_codes": ["DUPLICATE_TEXT_LINES"]
                    if index < 4
                    else [],
                    "automated_outcome": REVIEW if index < 4 else PASS,
                    "document_key": "doc_a" if index < 4 else f"doc_{index}",
                    "final_outcome": REVIEW if index < 4 else PASS,
                    "generalized_finding_codes": ["VISUAL_REVIEW_PENDING"],
                    "page_number": index + 1,
                    "pdf_page_index": index,
                    "review_status": COMPLETED,
                    "visual_review_outcome": PASS,
                }
                for index in range(32)
            ],
            "summary": _summary(review_pages=4),
            "visual_review_counts": {COMPLETED: 32},
        }
        loaded = load_p0_pilot_acceptance_result_from_report(visual_report)

        self.assertEqual(len(loaded.page_results), 32)
        with tempfile.TemporaryDirectory() as tmp:
            visual_path = Path(tmp) / "visual.json"
            closure_path = Path(tmp) / "closure.json"
            visual_path.write_text(json.dumps(visual_report), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--visual-review-report",
                    str(visual_path),
                    "--accepted-limitation",
                    "DUPLICATE_TEXT_LINES",
                    "--accepted-limitation",
                    "TABLE_FALSE_POSITIVE_ON_FIGURE_PAGE",
                    "--report-json",
                    str(closure_path),
                    "--allow-report-write",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertIn("Pages reviewed: 32", completed.stdout)
            self.assertIn("Outcome: ACCEPTED_WITH_LIMITATIONS", completed.stdout)
            self.assertTrue(closure_path.is_file())


def _acceptance_result(
    *,
    page_count: int = 32,
    review_pages: int = 0,
    status: str = COMPLETED,
    final_outcome: str = PASS,
    finding_codes: tuple[str, ...] = (),
    accepted_codes: tuple[str, ...] = (),
    recommendations: tuple[str, ...] = (),
) -> P0PilotAcceptanceResult:
    pages = _pages(
        page_count=page_count,
        review_pages=review_pages,
        status=status,
        final_outcome=final_outcome,
        finding_codes=finding_codes,
    )
    return P0PilotAcceptanceResult(
        outcome=ACCEPTED_WITH_LIMITATIONS if review_pages else ACCEPTED,
        page_results=pages,
        document_outcomes=_document_outcomes(review_pages=review_pages, pages=pages),
        visual_review_counts={status: page_count},
        confirmed_defect_counts={},
        accepted_limitation_codes=accepted_codes,
        blocking_finding_codes=(),
        corrective_phase_recommendations=recommendations,
        summary=_summary(
            page_count=page_count,
            review_pages=review_pages,
            status=status,
            final_outcome=final_outcome,
        ),
    )


def _pages(
    *,
    page_count: int = 32,
    review_pages: int = 0,
    status: str = COMPLETED,
    final_outcome: str = PASS,
    finding_codes: tuple[str, ...] = (),
) -> tuple[SourceAccuracyPageResult, ...]:
    pages = []
    for index in range(page_count):
        outcome = REVIEW if index < review_pages else final_outcome
        document_key = "doc_a" if index < 4 else f"doc_{index}"
        findings = tuple(
            SourceAccuracyFinding(
                finding_id=f"{document_key}:p{index}:finding:{seq:03d}",
                document_key=document_key,
                pdf_page_index=index,
                page_number=index + 1,
                category="MANUAL_REVIEW_REQUIRED"
                if code.startswith("VISUAL_")
                else "SOURCE_PROXY_LIMITATION",
                severity="informational",
                code=code,
                message="Synthetic sanitized finding.",
                requires_manual_review=code.startswith("VISUAL_"),
            )
            for seq, code in enumerate(finding_codes, start=1)
        )
        pages.append(
            SourceAccuracyPageResult(
                document_key=document_key,
                filename=f"{document_key}.pdf",
                pdf_page_index=index,
                page_number=index + 1,
                printed_page_label=str(index + 1),
                evaluation_roles=("synthetic",),
                automated_outcome=outcome,
                visual_review_status=status,
                visual_review_outcome=PASS if status == COMPLETED else REVIEW,
                final_page_outcome=outcome,
                metrics=(),
                findings=findings,
                parser_counts={"chunks": 1},
                source_proxy_counts={"source_hash_verified_locally": True},
                review_artifact_labels=(),
            )
        )
    return tuple(pages)


def _summary(
    *,
    page_count: int = 32,
    review_pages: int = 0,
    status: str = COMPLETED,
    final_outcome: str = PASS,
) -> dict[str, object]:
    pending = page_count if status == PENDING else 0
    second = page_count if status == NEEDS_SECOND_REVIEW else 0
    blocked = page_count if status == BLOCKED else 0
    completed = page_count if status == COMPLETED else 0
    counts = {PASS: page_count - review_pages, REVIEW: review_pages}
    if final_outcome == FAIL:
        counts = {FAIL: page_count}
    return {
        "blocked_pages": blocked,
        "completed_pages": completed,
        "completion_percentage": 100.0 if status == COMPLETED else 0.0,
        "document_count": page_count,
        "page_count": page_count,
        "page_outcome_counts": counts,
        "pending_pages": pending,
        "second_review_pages": second,
    }


def _document_outcomes(
    *,
    review_pages: int = 0,
    pages: tuple[SourceAccuracyPageResult, ...] | None = None,
) -> dict[str, str]:
    if pages is None:
        pages = _pages(review_pages=review_pages)
    outcomes: dict[str, str] = {}
    for page in pages:
        if page.visual_review_status != COMPLETED:
            outcome = INCOMPLETE
        elif page.final_page_outcome == FAIL:
            outcome = REJECTED
        elif page.final_page_outcome == REVIEW:
            outcome = ACCEPTED_WITH_LIMITATIONS
        else:
            outcome = ACCEPTED
        outcomes[page.document_key] = outcome
    return outcomes


if __name__ == "__main__":
    unittest.main()
