import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.chunking.semantic import create_semantic_chunks  # noqa: E402
from techdoc_parser.core.models import Chunk  # noqa: E402
from techdoc_parser.evaluation import (  # noqa: E402
    FAIL,
    PROXY_NOTICE,
    REVIEW,
    ChunkQualityEvaluationPolicy,
    ChunkQualityIssue,
    ChunkQualityMetricResult,
    chunk_quality_evaluation_result_to_json,
    chunk_quality_evaluation_result_to_markdown,
    chunk_quality_evaluation_results_to_dict,
    chunk_quality_evaluation_results_to_json,
    evaluate_chunk_quality,
    evaluate_chunk_quality_case,
    load_chunk_quality_cases,
    load_structured_fixture_document,
    write_chunk_quality_reports,
)

REGISTRY = ROOT / "tests" / "fixtures" / "chunk_quality" / "evaluation_cases.json"
BASELINE = (
    ROOT
    / "tests"
    / "fixtures"
    / "chunk_quality"
    / ("expected_chunk_quality_baseline.json")
)
TOOL = ROOT / "tools" / "evaluation" / "run-chunk-quality-evaluation.py"


class ChunkQualityEvaluationTests(unittest.TestCase):
    def test_models_and_single_result_serialization_are_json_safe(self):
        issue = ChunkQualityIssue(
            code="SAMPLE",
            severity="warning",
            message="Synthetic sample issue.",
            source_block_ids=("block-1",),
        )
        metric = ChunkQualityMetricResult(
            name="sample_metric",
            status="review",
            value=0.5,
            threshold=1.0,
            unit="ratio",
        )

        self.assertEqual(issue.code, "SAMPLE")
        self.assertEqual(metric.status, "review")

        case = _case("basic_structured_mapping")
        result = evaluate_chunk_quality_case(case, registry_root=ROOT)
        serialized = json.loads(chunk_quality_evaluation_result_to_json(result))
        markdown = chunk_quality_evaluation_result_to_markdown(result)

        self.assertEqual(serialized["evaluation_scope"], "fixture_chunk_quality_proxy")
        self.assertEqual(serialized["proxy_notice"], PROXY_NOTICE)
        self.assertEqual(serialized["source_accuracy_evaluated"], False)
        self.assertIn("Fixture metrics are quality proxies", markdown)

    def test_registry_loads_existing_fixture_cases_only(self):
        cases = load_chunk_quality_cases(REGISTRY)

        self.assertEqual(
            [case.case_id for case in cases],
            [
                "basic_structured_mapping",
                "equations_admonitions",
                "references_confidence",
                "section_hierarchy",
                "tables_figures",
            ],
        )
        for case in cases:
            self.assertTrue((ROOT / case.fixture_path).is_file(), case.fixture_path)

    def test_fixture_loading_is_non_mutating_and_uses_semantic_block_order(self):
        case = _case("basic_structured_mapping")
        fixture_path = ROOT / case.fixture_path
        before = json.loads(fixture_path.read_text(encoding="utf-8"))

        evidence = load_structured_fixture_document(fixture_path)
        chunks = create_semantic_chunks(evidence.document)

        after = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(after, before)
        self.assertEqual(evidence.document.id, "explicit-doc-id")
        self.assertEqual(evidence.block_order[0], "page-1-heading-1")
        self.assertNotIn("page-1-text-1", chunks[0].source_block_ids)

    def test_baseline_matches_expected_fixture_json(self):
        results = [
            evaluate_chunk_quality_case(case, registry_root=ROOT)
            for case in load_chunk_quality_cases(REGISTRY)
        ]
        actual = json.loads(chunk_quality_evaluation_results_to_json(results))
        expected = json.loads(BASELINE.read_text(encoding="utf-8"))

        self.assertEqual(actual, expected)
        self.assertEqual(actual["outcome"], REVIEW)
        self.assertEqual(actual["case_count"], 5)
        self.assertEqual(actual["review_count"], 5)
        self.assertEqual(actual["fail_count"], 0)

    def test_all_cases_keep_expected_metric_surface(self):
        results = [
            evaluate_chunk_quality_case(case, registry_root=ROOT)
            for case in load_chunk_quality_cases(REGISTRY)
        ]
        aggregate = chunk_quality_evaluation_results_to_dict(results)

        metric_names_by_case = {
            result.fixture_name: {metric.name for metric in result.metrics}
            for result in results
        }
        required_metrics = {
            "source_block_coverage",
            "source_block_reference_integrity",
            "reading_order_consistency",
            "section_boundary_coherence",
            "chunk_size",
            "duplicate_text_ratio",
            "duplicate_source_reference_ratio",
            "exact_text_overlap_ratio",
            "chunk_provenance_completeness",
            "table_source_preservation",
            "figure_caption_source_preservation",
            "equation_source_preservation",
            "admonition_source_preservation",
            "cross_reference_source_preservation",
            "table_cell_accuracy",
            "source_page_visual_accuracy",
            "determinism",
        }

        self.assertEqual(aggregate["outcome"], REVIEW)
        for metric_names in metric_names_by_case.values():
            self.assertEqual(metric_names, required_metrics)

    def test_special_content_cases_cover_tables_figures_equations_and_references(self):
        tables_result = evaluate_chunk_quality_case(
            _case("tables_figures"),
            registry_root=ROOT,
        )
        equations_result = evaluate_chunk_quality_case(
            _case("equations_admonitions"),
            registry_root=ROOT,
        )
        references_result = evaluate_chunk_quality_case(
            _case("references_confidence"),
            registry_root=ROOT,
        )

        self.assertGreater(
            tables_result.special_content_summary["table_source_block_count"], 0
        )
        self.assertGreater(
            tables_result.special_content_summary["figure_source_block_count"], 0
        )
        self.assertGreater(
            equations_result.special_content_summary["equation_source_block_count"], 0
        )
        self.assertGreater(
            equations_result.special_content_summary["admonition_source_block_count"], 0
        )
        self.assertGreater(
            references_result.special_content_summary[
                "cross_reference_source_block_count"
            ],
            0,
        )

    def test_reverse_source_block_order_fails_without_mutating_document(self):
        case = _case("section_hierarchy")
        evidence = load_structured_fixture_document(ROOT / case.fixture_path)
        document_before = copy.deepcopy(evidence.document.to_dict())
        chunks = create_semantic_chunks(evidence.document)
        reversed_chunks = [
            Chunk(
                id=chunk.id,
                text=chunk.text,
                document_id=chunk.document_id,
                source_page_numbers=chunk.source_page_numbers,
                source_block_ids=list(reversed(chunk.source_block_ids)),
                source_text_block_ids=chunk.source_text_block_ids,
                chunk_type=chunk.chunk_type,
                metadata=chunk.metadata,
            )
            for chunk in chunks
        ]

        result = evaluate_chunk_quality(
            evidence,
            reversed_chunks,
            policy=ChunkQualityEvaluationPolicy(require_source_checksum_metadata=False),
        )

        self.assertEqual(result.outcome, FAIL)
        self.assertTrue(
            any(issue.code == "READING_ORDER_INVERSION" for issue in result.issues)
        )
        self.assertEqual(evidence.document.to_dict(), document_before)

    def test_report_writer_requires_explicit_permission(self):
        result = evaluate_chunk_quality_case(
            _case("basic_structured_mapping"),
            registry_root=ROOT,
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            with self.assertRaises(PermissionError):
                write_chunk_quality_reports(result, json_path=output)

            written = write_chunk_quality_reports(
                result,
                json_path=output,
                markdown_path=Path(tmp) / "report.md",
                allow_report_write=True,
            )

            self.assertEqual(len(written), 2)
            self.assertTrue(output.is_file())

    def test_cli_lists_cases_and_returns_review_exit_code(self):
        list_completed = subprocess.run(
            [sys.executable, str(TOOL), "--list-cases"],
            check=False,
            capture_output=True,
            text=True,
        )
        run_completed = subprocess.run(
            [sys.executable, str(TOOL), "--all-cases"],
            check=False,
            capture_output=True,
            text=True,
        )
        strict_completed = subprocess.run(
            [sys.executable, str(TOOL), "--all-cases", "--strict"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(list_completed.returncode, 0)
        self.assertIn("basic_structured_mapping", list_completed.stdout)
        self.assertEqual(run_completed.returncode, 2)
        self.assertIn("Outcome: REVIEW", run_completed.stdout)
        self.assertEqual(strict_completed.returncode, 1)

    def test_cli_report_writes_are_gated_and_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocked_output = Path(tmp) / "blocked.json"
            output_1 = Path(tmp) / "report-1.json"
            output_2 = Path(tmp) / "report-2.json"
            blocked = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--all-cases",
                    "--report-json",
                    str(blocked_output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            first = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--all-cases",
                    "--report-json",
                    str(output_1),
                    "--allow-report-write",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            second = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--all-cases",
                    "--report-json",
                    str(output_2),
                    "--allow-report-write",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(blocked.returncode, 1)
            self.assertFalse(blocked_output.exists())
            self.assertEqual(first.returncode, 2)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(output_1.read_bytes(), output_2.read_bytes())


def _case(case_id: str):
    for case in load_chunk_quality_cases(REGISTRY):
        if case.case_id == case_id:
            return case
    raise AssertionError(f"Unknown case: {case_id}")


if __name__ == "__main__":
    unittest.main()
