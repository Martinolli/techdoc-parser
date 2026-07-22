import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation import (  # noqa: E402
    FAIL,
    PASS,
    REVIEW,
    inventory_pilot_corpus,
    pilot_corpus_inventory_result_to_dict,
    pilot_corpus_inventory_result_to_json,
    pilot_corpus_inventory_result_to_markdown,
    write_pilot_corpus_inventory_reports,
)

TOOL = ROOT / "tools" / "evaluation" / "run-pilot-corpus-inventory.py"

EXPECTED_SYNTHETIC_FILENAMES = (
    "FAA_Order_4040_26B.pdf",
    "Flight_Test_RM_AG_300_V32.pdf",
    "Introduction_Flight_Test_Engineering_RTO-AGARDograph_300_V14.pdf",
    "MIL-STD-882E.pdf",
    "Airplane_Maintenance_Manual_CIRRUS_Design_SR22.pdf",
    "Airworthiness_An_Introduction_Aircraft_Certification_And_Operations.pdf",
    "Aircraft_System_Safety_Military_Civil_Aeronautical_Applications.pdf",
    "Introduction_Aircraft_Stability_And_Control_Course_Notes_MAE_5070.pdf",
)


class PilotCorpusInventoryTests(unittest.TestCase):
    def test_missing_input_directory_fails_without_side_effect_flags(self):
        result = inventory_pilot_corpus(ROOT / "does-not-exist")

        self.assertEqual(result.outcome, FAIL)
        self.assertEqual(result.document_count, 0)
        self.assertEqual(result.total_pages, 0)
        self.assertEqual(result.issues[0].code, "INPUT_DIR_MISSING")
        self.assertFalse(result.accuracy_evaluated)
        self.assertFalse(result.ocr_performed)
        self.assertFalse(result.pdfs_modified)
        self.assertFalse(result.aviationrag_modified)
        self.assertTrue(result.owner_approval_required)

    def test_expected_ignored_native_documents_pass_inventory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for filename in EXPECTED_SYNTHETIC_FILENAMES:
                _write_pdf(root / filename, [_text_page(filename)])

            result = _inventory_with_git_protection(root)

        self.assertEqual(result.outcome, PASS)
        self.assertEqual(result.document_count, 8)
        self.assertEqual(result.expected_document_count, 8)
        self.assertEqual(result.git_ignore_summary["ignored"], 8)
        self.assertEqual(result.git_ignore_summary["tracked"], 0)
        self.assertEqual(result.text_mode_counts, {"native_text": 8})
        self.assertEqual(result.issues, ())

    def test_duplicate_unexpected_and_missing_documents_are_review_findings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "Unexpected_One.pdf"
            second = root / "Unexpected_Two.pdf"
            _write_pdf(first, [_text_page("duplicate source")])
            shutil.copyfile(first, second)

            result = _inventory_with_git_protection(root, expected_document_count=2)

        issue_codes = {issue.code for issue in result.issues}
        self.assertEqual(result.outcome, REVIEW)
        self.assertIn("DUPLICATE_HASH", issue_codes)
        self.assertIn("UNEXPECTED_DOCUMENT", issue_codes)
        self.assertIn("EXPECTED_DOCUMENT_MISSING", issue_codes)
        self.assertEqual(len(result.duplicate_hashes), 1)

    def test_unreadable_pdf_is_a_fail_finding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "MIL-STD-882E.pdf").write_bytes(b"%PDF-1.7\nnot a valid pdf")

            result = _inventory_with_git_protection(root, expected_document_count=1)

        self.assertEqual(result.outcome, FAIL)
        self.assertIn("PDF_UNREADABLE", {issue.code for issue in result.issues})

    def test_blank_and_image_only_documents_require_review_without_ocr(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pdf(root / "MIL-STD-882E.pdf", [{}])
            _write_pdf(
                root / "FAA_Order_4040_26B.pdf",
                [{"image": True, "width": 612, "height": 792}],
            )

            result = _inventory_with_git_protection(root, expected_document_count=2)

        by_name = {document.filename: document for document in result.documents}
        self.assertEqual(by_name["MIL-STD-882E.pdf"].text_mode, "uncertain")
        self.assertEqual(by_name["FAA_Order_4040_26B.pdf"].text_mode, "scanned_image")
        self.assertFalse(result.ocr_performed)
        self.assertIn("UNCERTAIN_TEXT_MODE", {issue.code for issue in result.issues})
        self.assertIn("SCANNED_IMAGE_LIKELY", {issue.code for issue in result.issues})

    def test_page_geometry_outline_labels_and_representative_roles_are_profiled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pdf(
                root / "MIL-STD-882E.pdf",
                [
                    _text_page("ordinary baseline shall refer to section 1"),
                    _two_column_page(),
                    _text_page("rotated warning procedure", rotation=90),
                    _text_page("landscape figure appendix", width=900, height=500),
                ],
                toc=((1, "Overview", 1), (2, "Details", 2)),
                page_labels=True,
            )

            result = _inventory_with_git_protection(root, expected_document_count=1)

        document = result.documents[0]
        roles = {
            role
            for page in document.representative_pages
            for role in page.evaluation_roles
        }
        self.assertTrue(document.outline_summary["outline_present"])
        self.assertTrue(document.page_label_summary["labels_present"])
        self.assertGreaterEqual(document.orientation_summary["rotated_page"], 1)
        self.assertGreaterEqual(document.orientation_summary["landscape"], 1)
        self.assertIn("two_column_likely", document.layout_summary)
        self.assertIn("reading_order", roles)
        self.assertIn("rotated_page", roles)
        self.assertIn("landscape", roles)
        self.assertLessEqual(len(document.representative_pages), 10)

    def test_sanitized_serialization_excludes_hashes_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pdf(root / "MIL-STD-882E.pdf", [_text_page("serialization")])

            result = _inventory_with_git_protection(root, expected_document_count=1)
            data = pilot_corpus_inventory_result_to_dict(result, include_hashes=False)
            json_text = pilot_corpus_inventory_result_to_json(
                result,
                include_hashes=False,
            )

        self.assertNotIn("sha256", data["documents"][0]["file"])
        self.assertNotIn(str(root), json_text)
        self.assertTrue(json_text.endswith("\n"))
        self.assertEqual(json.loads(json_text)["accuracy_evaluated"], False)

    def test_report_write_requires_explicit_permission(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pdf(root / "MIL-STD-882E.pdf", [_text_page("report")])
            result = _inventory_with_git_protection(root, expected_document_count=1)
            report_path = root / "report.json"

            with self.assertRaises(PermissionError):
                write_pilot_corpus_inventory_reports(result, json_path=report_path)

            written = write_pilot_corpus_inventory_reports(
                result,
                json_path=report_path,
                allow_report_write=True,
                include_hashes=False,
            )

            self.assertEqual(len(written), 1)
            self.assertTrue(report_path.exists())
            self.assertNotIn("sha256", report_path.read_text(encoding="utf-8"))

    def test_markdown_report_is_planning_only_and_sanitizable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pdf(root / "MIL-STD-882E.pdf", [_text_page("markdown")])
            result = _inventory_with_git_protection(root, expected_document_count=1)

        markdown = pilot_corpus_inventory_result_to_markdown(
            result,
            include_hashes=False,
        )

        self.assertIn("Source accuracy was not evaluated", markdown)
        self.assertIn("OCR was not run", markdown)
        self.assertNotIn("SHA-256", markdown)

    def test_cli_lists_documents_without_report_write(self):
        output_root = ROOT / "output"
        output_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_root) as temp_dir:
            root = Path(temp_dir)
            _write_pdf(root / "MIL-STD-882E.pdf", [_text_page("cli list")])

            completed = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--input-dir",
                    str(root),
                    "--expected-count",
                    "1",
                    "--list-documents",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("MIL-STD-882E.pdf", completed.stdout)
        self.assertNotIn("Wrote report", completed.stdout)

    def test_cli_writes_reports_only_with_allow_report_write(self):
        output_root = ROOT / "output"
        output_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_root) as temp_dir:
            root = Path(temp_dir)
            _write_pdf(root / "MIL-STD-882E.pdf", [_text_page("cli write")])
            report_path = root / "inventory.json"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--input-dir",
                    str(root),
                    "--expected-count",
                    "1",
                    "--report-json",
                    str(report_path),
                    "--allow-report-write",
                ],
                check=False,
                capture_output=True,
                text=True,
                cwd=ROOT,
            )

            self.assertTrue(report_path.exists())

        self.assertEqual(completed.returncode, 2)
        self.assertIn("Wrote report", completed.stdout)


def _inventory_with_git_protection(
    root: Path,
    *,
    expected_document_count: int = 8,
):
    with (
        patch(
            "techdoc_parser.evaluation.pilot_corpus_inventory._git_check_ignore",
            return_value=True,
        ),
        patch(
            "techdoc_parser.evaluation.pilot_corpus_inventory._git_is_tracked",
            return_value=False,
        ),
    ):
        return inventory_pilot_corpus(
            root,
            expected_document_count=expected_document_count,
        )


def _write_pdf(
    path: Path,
    pages: list[dict[str, object]],
    *,
    toc: tuple[tuple[int, str, int], ...] = (),
    page_labels: bool = False,
) -> None:
    document = fitz.open()
    try:
        for page_spec in pages:
            width = float(page_spec.get("width", 612))
            height = float(page_spec.get("height", 792))
            page = document.new_page(width=width, height=height)
            rotation = int(page_spec.get("rotation", 0))
            if rotation:
                page.set_rotation(rotation)
            if page_spec.get("image"):
                _insert_image(page)
            text_items = page_spec.get("texts", ())
            for x, y, text in text_items:
                page.insert_text((float(x), float(y)), str(text), fontsize=10)
        if toc:
            document.set_toc([list(item) for item in toc])
        if page_labels and hasattr(document, "set_page_labels"):
            document.set_page_labels(
                [{"startpage": 0, "prefix": "P-", "style": "D", "firstpagenum": 1}]
            )
        document.save(path)
    finally:
        document.close()


def _text_page(
    seed: str,
    *,
    width: int = 612,
    height: int = 792,
    rotation: int = 0,
) -> dict[str, object]:
    text = (
        f"{seed} table 1 figure 1 warning procedure shall refer to section 2. "
        "This synthetic page contains enough native text for inventory tests. "
        "It avoids source corpus wording and exists only as a temporary fixture."
    )
    return {
        "width": width,
        "height": height,
        "rotation": rotation,
        "texts": ((72, 72, text),),
    }


def _two_column_page() -> dict[str, object]:
    return {
        "texts": (
            (55, 72, "left column table alpha shall section"),
            (55, 92, "left column procedure warning"),
            (330, 72, "right column figure appendix"),
            (330, 92, "right column cross reference"),
        ),
    }


def _insert_image(page: fitz.Page) -> None:
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), False)
    pixmap.clear_with(0xCCCCCC)
    page.insert_image(page.rect, pixmap=pixmap)
