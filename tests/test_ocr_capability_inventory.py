import importlib.metadata
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation.ocr_capability_inventory import (  # noqa: E402
    AVAILABLE_NOT_INTEGRATED,
    BLOCKED,
    ENGINE_INSTALLED_BUT_NOT_INTEGRATED,
    EXISTING_INTEGRATION_INCOMPLETE,
    EXISTING_SUPPORTED_ENGINE_AVAILABLE,
    FORCED_OCR_NOT_SUPPORTED,
    GREEK_LANGUAGE_MODEL_UNAVAILABLE,
    IMPLEMENT_ADAPTER_FOR_INSTALLED_ENGINE,
    INTEGRATION_INCOMPLETE,
    NETWORK_MODEL_DOWNLOAD_REQUIRED,
    NO_ENGINE_INSTALLED,
    NO_OCR_ENGINE_AVAILABLE,
    NOT_AVAILABLE,
    OCR_ENGINE_NOT_INTEGRATED,
    OCR_ENGINE_VERSION_NOT_RECORDED,
    OCR_MANIFEST_METADATA_MISSING,
    OCR_PAGE_PROVENANCE_NOT_RECORDED,
    OCR_WRAPPER_WITHOUT_ENGINE,
    PDF_RENDERING_UNAVAILABLE,
    REPAIR_EXISTING_INTEGRATION,
    REQUEST_ENGINE_INSTALLATION_APPROVAL,
    SELECTIVE_PAGE_OCR_NOT_SUPPORTED,
    SUPPORTED_AND_AVAILABLE,
    OcrEngineCandidateAssessment,
    OcrExecutableCapability,
    OcrPythonPackageCapability,
    OcrRepositoryCapability,
    ProbeCompletedProcess,
    assess_ocr_engine_candidates,
    assess_pdf_rendering_capability,
    classify_repository_ocr_references,
    determine_overall_outcome,
    inspect_executable_capabilities,
    inspect_python_package_capabilities,
    inspect_repository_ocr_capabilities,
)
from techdoc_parser.evaluation.ocr_capability_reporting import (  # noqa: E402
    ocr_capability_inventory_to_json,
    ocr_capability_inventory_to_markdown,
    ocr_capability_inventory_to_sanitized_dict,
    write_ocr_capability_inventory_report,
)

TOOL = ROOT / "tools" / "evaluation" / "run-ocr-capability-inventory.py"


class OcrCapabilityInventoryTests(unittest.TestCase):
    def test_repository_reference_classification_distinguishes_non_execution(self):
        refs = classify_repository_ocr_references(
            ".",
            file_texts={
                "src/loader.py": "page.requires_ocr = True",
                "src/adapter.py": "pytesseract.image_to_string(image)",
                "docs/plan.md": "OCR is planned only.",
                "tests/fixtures/case.json": '{"ocr_text": ""}',
                "README.md": "OCR support is documented as absent.",
                "src/old.py": "obsolete OCR note",
            },
        )

        self.assertIn("src/loader.py", refs["warning_or_detection_only"])
        self.assertIn("src/adapter.py", refs["implemented_adapter"])
        self.assertIn("docs/plan.md", refs["documentation_only"])
        self.assertIn("tests/fixtures/case.json", refs["test_fixture_only"])
        self.assertIn("src/old.py", refs["obsolete_or_unused"])

    def test_repository_capabilities_cover_declared_adapter_absent_and_no_refs(self):
        refs = {
            "warning_or_detection_only": ("src/loader.py",),
            "declared_integration": ("src/evaluation/engineering_ocr_fidelity.py",),
            "implemented_adapter": ("src/ocr_runner.py",),
        }
        capabilities = inspect_repository_ocr_capabilities(".", reference_classes=refs)
        by_id = {item.capability_id: item for item in capabilities}

        self.assertEqual(
            by_id["ocr_need_detection"].implementation_status,
            "detection_only",
        )
        self.assertEqual(
            by_id["engineering_ocr_fidelity_evaluator"].implementation_status,
            "partial",
        )
        self.assertEqual(
            by_id["parser_ocr_execution_adapter"].implementation_status,
            "implemented",
        )

        absent = inspect_repository_ocr_capabilities(".", reference_classes={})
        self.assertEqual(
            absent[0].capability_id,
            "parser_ocr_execution_adapter",
        )
        self.assertEqual(absent[0].implementation_status, "absent")

    def test_python_package_inventory_records_versions_and_missing_packages(self):
        imported: list[str] = []

        def fake_find_spec(name: str) -> object | None:
            imported.append(name)
            return object() if name == "pytesseract" else None

        def fake_version(name: str) -> str:
            if name == "pytesseract":
                return "0.3.13"
            raise importlib.metadata.PackageNotFoundError(name)

        def fake_metadata(name: str) -> dict[str, str]:
            self.assertEqual(name, "pytesseract")
            return {"License": "Apache-2.0"}

        packages = inspect_python_package_capabilities(
            package_specs=(
                ("pytesseract", "pytesseract", "OCR wrapper"),
                ("easyocr", "easyocr", "OCR engine"),
            ),
            find_spec=fake_find_spec,
            version_reader=fake_version,
            metadata_reader=fake_metadata,
        )
        by_name = {item.distribution_name: item for item in packages}

        self.assertEqual(by_name["pytesseract"].version, "0.3.13")
        self.assertTrue(by_name["pytesseract"].module_discoverable)
        self.assertEqual(by_name["pytesseract"].declared_license, "Apache-2.0")
        self.assertFalse(by_name["easyocr"].installed)
        self.assertIsNone(by_name["easyocr"].declared_license)
        self.assertEqual(imported, ["easyocr", "pytesseract"])
        self.assertNotIn("easyocr", sys.modules)

    def test_executable_inventory_handles_installed_missing_timeout_failure(self):
        calls: list[tuple[str, ...]] = []

        def resolver(name: str) -> str | None:
            return name if name in {"tesseract", "pdftoppm", "mutool"} else None

        def runner(command: tuple[str, ...], timeout: int) -> ProbeCompletedProcess:
            del timeout
            calls.append(command)
            if command == ("tesseract", "--version"):
                return ProbeCompletedProcess(0, "tesseract 5.5.0\n", "")
            if command == ("tesseract", "--list-langs"):
                return ProbeCompletedProcess(
                    0,
                    "List of available languages\neng\nell\nosd\n",
                    "",
                )
            if command == ("pdftoppm", "-v"):
                raise subprocess.TimeoutExpired(command, 1)
            return ProbeCompletedProcess(2, "", "failed")

        executables = inspect_executable_capabilities(
            executable_specs={
                "tesseract": (("--version",), "OCR engine"),
                "pdftoppm": (("-v",), "rendering"),
                "mutool": (("-v",), "rendering"),
                "ocrmypdf": (("--version",), "OCR wrapper"),
            },
            command_resolver=resolver,
            command_runner=runner,
        )
        by_name = {item.executable_name: item for item in executables}

        self.assertTrue(by_name["tesseract"].installed)
        self.assertEqual(by_name["tesseract"].version, "tesseract 5.5.0")
        self.assertEqual(
            by_name["tesseract"].supported_languages,
            ("ell", "eng", "osd"),
        )
        self.assertEqual(by_name["pdftoppm"].version_probe_status, "timeout")
        self.assertEqual(by_name["mutool"].version_probe_status, "failed")
        self.assertFalse(by_name["ocrmypdf"].installed)
        self.assertIn(("tesseract", "--version"), calls)

    def test_non_allowlisted_executable_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not allowlisted"):
            inspect_executable_capabilities(
                executable_specs={"not_allowed": (("--version",), "OCR engine")},
                command_resolver=lambda name: name,
            )

    def test_tesseract_language_gaps_and_no_fidelity_claim(self):
        tesseract = OcrExecutableCapability(
            executable_name="tesseract",
            installed=True,
            version="tesseract 5.5.0",
            version_probe_status="ok",
            capability_role="OCR engine",
            supported_languages=("eng", "osd"),
        )
        candidates = assess_ocr_engine_candidates(
            repository_capabilities=(_repo_adapter(implemented=False),),
            python_packages=(),
            executables=(tesseract,),
        )
        candidate = candidates[0]

        self.assertEqual(candidate.engine_id, "tesseract")
        self.assertEqual(candidate.candidate_status, AVAILABLE_NOT_INTEGRATED)
        self.assertIn(GREEK_LANGUAGE_MODEL_UNAVAILABLE, candidate.blocking_gap_codes)
        self.assertIn(FORCED_OCR_NOT_SUPPORTED, candidate.blocking_gap_codes)
        self.assertFalse(candidate.forced_ocr_supported)

    def test_language_listing_failure_keeps_greek_unknown(self):
        tesseract = OcrExecutableCapability(
            executable_name="tesseract",
            installed=True,
            version="tesseract 5.5.0",
            version_probe_status="ok",
            capability_role="OCR engine",
            supported_languages=(),
        )
        candidate = assess_ocr_engine_candidates(
            repository_capabilities=(_repo_adapter(implemented=False),),
            python_packages=(),
            executables=(tesseract,),
        )[0]

        self.assertEqual(candidate.greek_support_status, "unknown")
        self.assertNotEqual(candidate.greek_support_status, "fidelity_proven")

    def test_wrapper_without_engine_is_incomplete(self):
        wrapper = OcrPythonPackageCapability(
            distribution_name="pytesseract",
            module_name="pytesseract",
            installed=True,
            version="0.3.13",
            module_discoverable=True,
            declared_license="Apache-2.0",
            capability_role="OCR wrapper",
            repository_integration_present=False,
        )
        tesseract = OcrExecutableCapability(
            executable_name="tesseract",
            installed=False,
            version=None,
            version_probe_status="not_found",
            capability_role="OCR engine",
            supported_languages=(),
        )
        candidate = assess_ocr_engine_candidates(
            repository_capabilities=(_repo_adapter(implemented=False),),
            python_packages=(wrapper,),
            executables=(tesseract,),
        )[0]

        self.assertEqual(candidate.candidate_status, INTEGRATION_INCOMPLETE)
        self.assertIn(OCR_WRAPPER_WITHOUT_ENGINE, candidate.blocking_gap_codes)

    def test_rendering_capability_records_backend_controls_and_gap(self):
        rendering = assess_pdf_rendering_capability(
            python_packages=(
                OcrPythonPackageCapability(
                    "PyMuPDF",
                    "fitz",
                    True,
                    "1.26.3",
                    True,
                    "AGPL-3.0",
                    "rendering",
                    False,
                ),
            ),
            executables=(),
        )
        missing = assess_pdf_rendering_capability(python_packages=(), executables=())

        self.assertTrue(rendering["page_rendering_available"])
        self.assertTrue(rendering["deterministic_dpi_control_available"])
        self.assertTrue(rendering["page_range_control_available"])
        self.assertFalse(missing["page_rendering_available"])

    def test_engine_assessment_supported_installed_unintegrated_and_no_engine(self):
        supported = OcrEngineCandidateAssessment(
            "supported",
            "OCR engine",
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            "yes",
            "yes",
            "yes",
            "no",
            "MIT",
            SUPPORTED_AND_AVAILABLE,
            (),
        )
        installed = OcrEngineCandidateAssessment(
            "installed",
            "OCR engine",
            True,
            False,
            False,
            False,
            False,
            False,
            False,
            "yes",
            "unknown",
            "partial",
            "no",
            None,
            AVAILABLE_NOT_INTEGRATED,
            (OCR_ENGINE_NOT_INTEGRATED,),
        )
        missing = OcrEngineCandidateAssessment(
            "none",
            "none",
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            None,
            NOT_AVAILABLE,
            (NO_OCR_ENGINE_AVAILABLE,),
        )

        self.assertEqual(
            determine_overall_outcome(
                repository_capabilities=(_repo_adapter(implemented=True),),
                engine_candidates=(supported,),
                page_rendering_available=True,
            )[0],
            EXISTING_SUPPORTED_ENGINE_AVAILABLE,
        )
        self.assertEqual(
            determine_overall_outcome(
                repository_capabilities=(_repo_adapter(implemented=False),),
                engine_candidates=(installed,),
                page_rendering_available=True,
            )[1],
            IMPLEMENT_ADAPTER_FOR_INSTALLED_ENGINE,
        )
        self.assertEqual(
            determine_overall_outcome(
                repository_capabilities=(_repo_adapter(implemented=False),),
                engine_candidates=(missing,),
                page_rendering_available=True,
            )[0],
            NO_ENGINE_INSTALLED,
        )

    def test_missing_manifest_provenance_version_forced_and_selective_block(self):
        tesseract = OcrExecutableCapability(
            executable_name="tesseract",
            installed=True,
            version=None,
            version_probe_status="no_version_output",
            capability_role="OCR engine",
            supported_languages=("eng", "ell"),
        )
        candidate = assess_ocr_engine_candidates(
            repository_capabilities=(_repo_adapter(implemented=False),),
            python_packages=(),
            executables=(tesseract,),
        )[0]

        self.assertIn(OCR_MANIFEST_METADATA_MISSING, candidate.blocking_gap_codes)
        self.assertIn(OCR_PAGE_PROVENANCE_NOT_RECORDED, candidate.blocking_gap_codes)
        self.assertIn(OCR_ENGINE_VERSION_NOT_RECORDED, candidate.blocking_gap_codes)
        self.assertIn(SELECTIVE_PAGE_OCR_NOT_SUPPORTED, candidate.blocking_gap_codes)

    def test_incomplete_adapter_and_network_model_outcome(self):
        network_candidate = OcrEngineCandidateAssessment(
            "model_engine",
            "OCR engine",
            True,
            True,
            False,
            False,
            False,
            False,
            False,
            "unknown",
            "unknown",
            "unknown",
            "yes",
            None,
            INTEGRATION_INCOMPLETE,
            (NETWORK_MODEL_DOWNLOAD_REQUIRED,),
        )
        outcome, action, gaps = determine_overall_outcome(
            repository_capabilities=(_repo_adapter(implemented=True),),
            engine_candidates=(network_candidate,),
            page_rendering_available=True,
        )

        self.assertEqual(outcome, EXISTING_INTEGRATION_INCOMPLETE)
        self.assertEqual(action, REPAIR_EXISTING_INTEGRATION)
        self.assertIn(NETWORK_MODEL_DOWNLOAD_REQUIRED, gaps)

    def test_probe_failure_can_produce_blocked_result(self):
        from techdoc_parser.evaluation.ocr_capability_inventory import (
            inventory_ocr_capabilities,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "bad").write_text("x", encoding="utf-8")
            result = inventory_ocr_capabilities(repository_root=root / "missing")

        self.assertIn(result.outcome, {BLOCKED, NO_ENGINE_INSTALLED})

    def test_results_are_deterministic(self):
        refs = {
            "warning_or_detection_only": ("b.py", "a.py"),
            "implemented_adapter": ("z.py",),
        }
        first = inspect_repository_ocr_capabilities(".", reference_classes=refs)
        second = inspect_repository_ocr_capabilities(".", reference_classes=refs)

        self.assertEqual(first, second)

    def test_reporting_excludes_paths_username_path_and_secret_values(self):
        result = _sample_result()
        payload = ocr_capability_inventory_to_sanitized_dict(result)
        text = json.dumps(payload, sort_keys=True)

        self.assertNotIn(str(Path.home()), text)
        self.assertNotIn("C:\\", text)
        self.assertNotIn("PATH=", text)
        self.assertNotIn("top-secret-value", text)

    def test_json_markdown_are_deterministic_and_end_with_newline(self):
        result = _sample_result()
        first_json = ocr_capability_inventory_to_json(result)
        second_json = ocr_capability_inventory_to_json(result)
        first_markdown = ocr_capability_inventory_to_markdown(result)
        second_markdown = ocr_capability_inventory_to_markdown(result)

        self.assertEqual(first_json, second_json)
        self.assertEqual(first_markdown, second_markdown)
        self.assertTrue(first_json.endswith("\n"))
        self.assertTrue(first_markdown.endswith("\n"))

    def test_report_write_requires_permission(self):
        result = _sample_result()
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "inventory.json"
            markdown_path = Path(temp_dir) / "inventory.md"
            with self.assertRaises(PermissionError):
                write_ocr_capability_inventory_report(
                    result,
                    json_path=json_path,
                    markdown_path=markdown_path,
                )
            write_ocr_capability_inventory_report(
                result,
                json_path=json_path,
                markdown_path=markdown_path,
                allow_write=True,
            )
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())

    def test_cli_exists_exit_mapping_and_statement(self):
        spec = importlib.util.spec_from_file_location("ocr_inventory_cli", TOOL)
        self.assertIsNotNone(spec)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        self.assertTrue(TOOL.exists())
        self.assertEqual(module._exit_code(EXISTING_SUPPORTED_ENGINE_AVAILABLE), 0)
        self.assertEqual(module._exit_code(ENGINE_INSTALLED_BUT_NOT_INTEGRATED), 2)
        self.assertEqual(module._exit_code(EXISTING_INTEGRATION_INCOMPLETE), 2)
        self.assertEqual(module._exit_code(NO_ENGINE_INSTALLED), 3)
        self.assertEqual(module._exit_code(BLOCKED), 1)

        completed = subprocess.run(
            [sys.executable, str(TOOL), "--help"],
            check=False,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("read-only OCR capability inventory", completed.stdout)

    def test_regression_no_dependency_added_and_aviationrag_not_imported(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

        self.assertNotIn("pytesseract", pyproject)
        self.assertNotIn("ocrmypdf", pyproject)
        self.assertNotIn("AviationRAG", sys.modules)


def _repo_adapter(*, implemented: bool) -> OcrRepositoryCapability:
    return OcrRepositoryCapability(
        capability_id="parser_ocr_execution_adapter",
        capability_type="implemented_adapter",
        evidence_locations=("src/ocr.py",) if implemented else (),
        implementation_status="implemented" if implemented else "absent",
        supported_modes=("ocr_execution",) if implemented else (),
        manifest_support=implemented,
        page_provenance_support=implemented,
        notes=(),
    )


def _sample_result():
    from techdoc_parser.evaluation.ocr_capability_inventory import (
        OcrCapabilityInventoryResult,
    )

    return OcrCapabilityInventoryResult(
        outcome=NO_ENGINE_INSTALLED,
        repository_capabilities=(_repo_adapter(implemented=False),),
        python_packages=(),
        executables=(),
        engine_candidates=(
            OcrEngineCandidateAssessment(
                "none",
                "none",
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                "unknown",
                "unknown",
                "unknown",
                "unknown",
                None,
                NOT_AVAILABLE,
                (NO_OCR_ENGINE_AVAILABLE, PDF_RENDERING_UNAVAILABLE),
            ),
        ),
        page_rendering_available=False,
        supported_execution_path_available=False,
        inventory_complete=True,
        blocking_gap_codes=(NO_OCR_ENGINE_AVAILABLE, PDF_RENDERING_UNAVAILABLE),
        recommended_next_action=REQUEST_ENGINE_INSTALLATION_APPROVAL,
        summary={
            "rendering": {"rendering_backend_candidates": ()},
            "probe_note": "C:\\Users\\Name\\path PATH redacted",
            "secret_value": "top-secret-value",
        },
    )


if __name__ == "__main__":
    unittest.main()
