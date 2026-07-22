import json
import sys
import tempfile
import unittest
from pathlib import Path

import fitz  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.core import (  # noqa: E402
    BoundingBox,
    Chunk,
    HeadingBlock,
    SourceLocation,
    TableBlock,
    TextBlock,
)
from techdoc_parser.evaluation import (  # noqa: E402
    EXCLUDED_HEADING,
    FAIL,
    REVIEW,
    SATISFIED_BY_ENTITY_CHUNK,
    SOURCE_ACCURACY_POLICY_NAME,
    SOURCE_ACCURACY_POLICY_VERSION,
    SourceBlockEligibilityPolicy,
    classify_source_block_chunk_eligibility,
    evaluate_representative_page,
    source_accuracy_page_result_to_dict,
    source_accuracy_pilot_result_to_json,
)
from techdoc_parser.evaluation.source_accuracy import (  # noqa: E402
    VISUAL_CHECK_FIELDS,
    SourceAccuracyPlanPage,
    run_source_accuracy_pilot,
)
from techdoc_parser.ingestion import PDFLoader  # noqa: E402


class SourceAccuracyPolicyCorrectionTests(unittest.TestCase):
    def test_source_proxy_duplicate_is_review_not_raw_coverage_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            duplicate = _long_line("duplicate source-proxy line")
            _write_pdf(pdf, [[duplicate, duplicate]])

            result = evaluate_representative_page(
                source_path=pdf,
                document_key="synthetic_document",
                pdf_page_index=0,
                page_number=1,
                evaluation_roles=("ordinary_text",),
                checklist=_completed_checklist(),
            )

        self.assertEqual(_metric_status(result, "raw_character_coverage"), "pass")
        self.assertEqual(_metric_status(result, "duplicate_line_count"), "review")
        self.assertEqual(result.automated_outcome, REVIEW)
        duplicate_findings = [
            finding
            for finding in result.findings
            if finding.code == "DUPLICATE_TEXT_LINES"
        ]
        self.assertEqual(duplicate_findings[0].category, "SOURCE_PROXY_LIMITATION")
        self.assertIn(
            "SOURCE_PROXY_DUPLICATION_RECLASSIFIED",
            {item.correction_reason_code for item in result.policy_corrections},
        )

    def test_parser_only_duplicate_remains_fail_independent_of_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            _write_pdf(pdf, [[_long_line("unique parser baseline")]])
            parser_document = PDFLoader(str(pdf)).load()
            original = parser_document.pages[0].text_blocks[0]
            duplicate = TextBlock(
                id="page-1-text-duplicate",
                text=original.text or "",
                source=original.source,
                normalized_text=original.normalized_text,
            )
            parser_document.pages[0].text_blocks.append(duplicate)
            parser_document.pages[0].blocks.append(duplicate)

            result = evaluate_representative_page(
                source_path=pdf,
                document_key="synthetic_document",
                pdf_page_index=0,
                page_number=1,
                evaluation_roles=("ordinary_text",),
                parser_document=parser_document,
                checklist=_completed_checklist(),
            )

        self.assertEqual(_metric_status(result, "raw_character_coverage"), "pass")
        self.assertEqual(_metric_status(result, "duplicate_line_count"), "fail")
        self.assertEqual(result.automated_outcome, FAIL)
        self.assertEqual(result.final_page_outcome, FAIL)

    def test_text_loss_still_fails_coverage_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            _write_pdf(pdf, [[_long_line("coverage loss source")]])
            parser_document = PDFLoader(str(pdf)).load()
            parser_document.pages[0].text_blocks[0].text = "short parser text"

            result = evaluate_representative_page(
                source_path=pdf,
                document_key="synthetic_document",
                pdf_page_index=0,
                page_number=1,
                evaluation_roles=("ordinary_text",),
                parser_document=parser_document,
                checklist=_completed_checklist(),
            )

        self.assertEqual(_metric_status(result, "raw_character_coverage"), "fail")
        self.assertEqual(result.automated_outcome, FAIL)

    def test_reading_order_inversion_is_review_pending_visual_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "synthetic.pdf"
            lines = [
                _long_line("top visible line"),
                _long_line("bottom visible line"),
            ]
            _write_pdf(pdf, [lines])
            parser_document = PDFLoader(str(pdf)).load()
            self.assertGreaterEqual(len(parser_document.pages[0].text_blocks), 2)
            parser_document.pages[0].text_blocks[0].source.bbox = BoundingBox(
                72, 200, 500, 212
            )
            parser_document.pages[0].text_blocks[1].source.bbox = BoundingBox(
                72, 100, 500, 112
            )

            result = evaluate_representative_page(
                source_path=pdf,
                document_key="synthetic_document",
                pdf_page_index=0,
                page_number=1,
                evaluation_roles=("ordinary_text", "reading_order"),
                parser_document=parser_document,
                checklist=_completed_checklist(),
            )

        self.assertEqual(_metric_status(result, "order_inversion_count"), "review")
        self.assertEqual(result.automated_outcome, REVIEW)
        finding = next(
            item for item in result.findings if item.code == "READING_ORDER_INVERSION"
        )
        self.assertEqual(finding.category, "MANUAL_REVIEW_REQUIRED")
        self.assertTrue(finding.requires_manual_review)

    def test_heading_exclusion_follows_configured_policy(self):
        heading = HeadingBlock(
            id="heading-1",
            source=_source_location(1),
            text="Synthetic Heading",
            level=1,
        )
        chunk = Chunk(
            id="chunk-1",
            text="Synthetic Heading\nBody",
            source_block_ids=[],
            source_page_numbers=[1],
        )

        excluded = classify_source_block_chunk_eligibility(
            heading,
            [chunk],
            policy=SourceBlockEligibilityPolicy(require_heading_chunks=False),
        )
        required = classify_source_block_chunk_eligibility(
            heading,
            [chunk],
            policy=SourceBlockEligibilityPolicy(require_heading_chunks=True),
        )

        self.assertEqual(excluded.state, EXCLUDED_HEADING)
        self.assertEqual(required.state, "required_direct_chunk")

    def test_entity_derived_source_text_replacement_satisfies_chunk_coverage(self):
        table = TableBlock(
            id="table-1",
            source=_source_location(1),
            text="Synthetic table candidate",
            source_text_block_ids=["text-1"],
        )
        chunk = Chunk(
            id="chunk-1",
            text="[Table candidate]\nSynthetic table candidate",
            source_block_ids=[],
            source_text_block_ids=["text-1"],
            source_page_numbers=[1],
        )

        eligibility = classify_source_block_chunk_eligibility(table, [chunk])

        self.assertEqual(eligibility.state, SATISFIED_BY_ENTITY_CHUNK)
        self.assertEqual(eligibility.covered_by_chunk_ids, ("chunk-1",))

    def test_policy_identity_and_corrections_are_serialized_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "synthetic.pdf"
            duplicate = _long_line("serialized duplicate")
            _write_pdf(pdf, [[duplicate, duplicate]])
            plan = [
                SourceAccuracyPlanPage(
                    document_key="synthetic_document",
                    filename=pdf.name,
                    pdf_page_index=0,
                    page_number=1,
                    printed_page_label=None,
                    evaluation_roles=("ordinary_text",),
                    priority="P0",
                    selection_reason=("synthetic",),
                )
            ]

            result = run_source_accuracy_pilot(input_dir=root, plan=plan)
            first = source_accuracy_pilot_result_to_json(result)
            second = source_accuracy_pilot_result_to_json(result)
            page_data = source_accuracy_page_result_to_dict(result.page_results[0])
            data = json.loads(first)

        self.assertEqual(first, second)
        self.assertEqual(data["evaluation_policy_name"], SOURCE_ACCURACY_POLICY_NAME)
        self.assertEqual(
            data["evaluation_policy_version"], SOURCE_ACCURACY_POLICY_VERSION
        )
        self.assertEqual(data["run_type"], "corrected_evaluator_rerun")
        self.assertTrue(page_data["policy_corrections"])


def _metric_status(result, metric_name: str) -> str:
    return next(
        metric.status for metric in result.metrics if metric.name == metric_name
    )


def _write_pdf(path: Path, pages: list[list[str]]) -> None:
    document = fitz.open()
    try:
        for lines in pages:
            page = document.new_page(width=612, height=792)
            for index, text in enumerate(lines):
                page.insert_text((72, 72 + index * 24), text, fontsize=10)
        document.save(path)
    finally:
        document.close()


def _long_line(seed: str) -> str:
    return (
        f"{seed} figure warning procedure shall refer to section two. "
        "This synthetic line contains enough native text for policy correction tests."
    )


def _text_block(block_id: str, text: str, *, y0: float) -> TextBlock:
    return TextBlock(
        id=block_id,
        text=text,
        source=SourceLocation(
            document_path="synthetic.pdf",
            page_number=1,
            bbox=BoundingBox(72, y0, 500, y0 + 12),
        ),
    )


def _source_location(page_number: int) -> SourceLocation:
    return SourceLocation(
        document_path="synthetic.pdf",
        page_number=page_number,
        bbox=BoundingBox(72, 72, 500, 84),
    )


def _completed_checklist() -> dict[str, object]:
    return {
        "page_id": "synthetic_document:p0",
        "checks": {field: "pass" for field in VISUAL_CHECK_FIELDS},
        "reviewer_notes": "Synthetic complete review.",
    }


if __name__ == "__main__":
    unittest.main()
