import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from techdoc_parser.evaluation import load_engineering_ocr_text_artifact  # noqa: E402
from techdoc_parser.ocr import (  # noqa: E402
    FAIL,
    OCR_SELECTED_PAGES,
    PASS_WITH_WARNINGS,
    ControlledOcrRequest,
    TesseractProcessResult,
    controlled_ocr_result_to_json,
    load_ocr_document_artifact,
    ocr_artifact_to_page_texts,
    run_controlled_tesseract_ocr,
    validate_ocr_artifact,
    validate_ocr_manifest,
    write_controlled_ocr_artifacts,
)
from techdoc_parser.ocr.tesseract_adapter import _run_subprocess  # noqa: E402

TOOL = ROOT / "tools" / "ocr" / "run-controlled-tesseract-ocr.py"


class FakeTesseract:
    def __init__(
        self,
        *,
        languages: tuple[str, ...] = ("eng", "osd"),
        ocr_returncode: int = 0,
        ocr_stdout: str = "Fictional lift note β = 2\r\n\f",
        ocr_stderr: str = "",
        timeout_on_ocr: bool = False,
    ) -> None:
        self.languages = languages
        self.ocr_returncode = ocr_returncode
        self.ocr_stdout = ocr_stdout
        self.ocr_stderr = ocr_stderr
        self.timeout_on_ocr = timeout_on_ocr
        self.commands: list[tuple[str, ...]] = []

    def resolver(self, name: str) -> str | None:
        return "tesseract" if name == "tesseract" else None

    def runner(
        self,
        command: Sequence[str],
        timeout_seconds: int,
    ) -> TesseractProcessResult:
        del timeout_seconds
        self.commands.append(tuple(command))
        if tuple(command) == ("tesseract", "--version"):
            return TesseractProcessResult(0, "tesseract 5.3.0\n", "")
        if tuple(command) == ("tesseract", "--list-langs"):
            stdout = "List of available languages in synthetic tessdata:\n"
            stdout += "\n".join(self.languages)
            return TesseractProcessResult(0, stdout, "")
        if self.timeout_on_ocr:
            raise subprocess.TimeoutExpired(command, 1)
        return TesseractProcessResult(
            self.ocr_returncode,
            self.ocr_stdout,
            self.ocr_stderr,
        )


def test_controlled_adapter_records_raw_normalized_provenance_and_limitations(
    tmp_path: Path,
) -> None:
    source = tmp_path / "synthetic.pdf"
    _write_pdf(source, ["Fictional native text only."])
    fake = FakeTesseract()
    request = ControlledOcrRequest(
        source_path=source,
        document_id="synthetic_controlled_ocr",
        languages=("eng",),
        strict=True,
    )

    result = run_controlled_tesseract_ocr(
        request,
        command_resolver=fake.resolver,
        command_runner=fake.runner,
    )
    artifact_json = controlled_ocr_result_to_json(result)
    artifact = json.loads(artifact_json)

    assert result.outcome == PASS_WITH_WARNINGS
    assert result.processed_pages == (1,)
    assert result.page_results[0].raw_ocr_text == "Fictional lift note β = 2\r\n\f"
    assert result.page_results[0].normalized_ocr_text == "Fictional lift note β = 2\n"
    assert result.page_results[0].provenance.rendered_image_sha256 is not None
    assert result.page_results[0].provenance.raw_ocr_sha256 is not None
    assert result.page_results[0].provenance.normalized_ocr_sha256 is not None
    assert "GREEK_LANGUAGE_MODEL_UNAVAILABLE" in result.warnings
    assert not result.default_parser_behavior_changed
    assert not result.structured_document_schema_changed
    assert not result.aviationrag_activity
    assert not result.embeddings_or_vector_store_activity
    assert str(tmp_path) not in artifact_json
    assert validate_ocr_artifact(artifact).valid


def test_requested_eng_plus_ell_fails_without_fallback_or_rendering(
    tmp_path: Path,
) -> None:
    source = tmp_path / "synthetic.pdf"
    _write_pdf(source, ["Fictional text."])
    fake = FakeTesseract(languages=("eng", "osd"))
    request = ControlledOcrRequest(
        source_path=source,
        document_id="synthetic_controlled_ocr",
        languages=("eng", "ell"),
    )

    result = run_controlled_tesseract_ocr(
        request,
        command_resolver=fake.resolver,
        command_runner=fake.runner,
    )

    assert result.outcome == FAIL
    assert result.errors == ("REQUESTED_OCR_LANGUAGE_UNAVAILABLE",)
    assert result.page_results == ()
    assert not any("stdout" in command for command in fake.commands)


def test_selected_pages_are_one_based_and_do_not_process_other_pages(
    tmp_path: Path,
) -> None:
    source = tmp_path / "synthetic.pdf"
    _write_pdf(source, ["Page 1", "Page 2"])
    fake = FakeTesseract()
    request = ControlledOcrRequest(
        source_path=source,
        document_id="synthetic_controlled_ocr",
        mode=OCR_SELECTED_PAGES,
        selected_pages=(2,),
        languages=("eng",),
    )

    result = run_controlled_tesseract_ocr(
        request,
        command_resolver=fake.resolver,
        command_runner=fake.runner,
    )

    assert result.requested_pages == (2,)
    assert result.processed_pages == (2,)
    ocr_commands = [command for command in fake.commands if "stdout" in command]
    assert len(ocr_commands) == 1


def test_page_failure_and_timeout_are_preserved(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.pdf"
    _write_pdf(source, ["Page 1"])
    failing = FakeTesseract(ocr_returncode=1, ocr_stderr="fictional OCR warning")
    request = ControlledOcrRequest(
        source_path=source,
        document_id="synthetic_controlled_ocr",
        languages=("eng",),
    )

    failed = run_controlled_tesseract_ocr(
        request,
        command_resolver=failing.resolver,
        command_runner=failing.runner,
    )
    timing_out = FakeTesseract(timeout_on_ocr=True)
    timed_out = run_controlled_tesseract_ocr(
        request,
        command_resolver=timing_out.resolver,
        command_runner=timing_out.runner,
    )

    assert failed.outcome == FAIL
    assert failed.page_results[0].status == "failed"
    assert failed.page_results[0].errors == ("OCR_PAGE_FAILED",)
    assert failed.page_results[0].stderr_excerpt == "fictional OCR warning"
    assert timed_out.outcome == FAIL
    assert timed_out.page_results[0].status == "timed_out"
    assert timed_out.page_results[0].errors == ("OCR_PAGE_TIMED_OUT",)


def test_writer_requires_permission_and_writes_manifest_artifacts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "synthetic.pdf"
    _write_pdf(source, ["Fictional text."])
    fake = FakeTesseract()
    request = ControlledOcrRequest(
        source_path=source,
        document_id="synthetic_controlled_ocr",
        languages=("eng",),
    )
    result = run_controlled_tesseract_ocr(
        request,
        command_resolver=fake.resolver,
        command_runner=fake.runner,
    )
    output_dir = tmp_path / "ocr_output"

    with pytest.raises(PermissionError):
        write_controlled_ocr_artifacts(result, output_dir)

    written = write_controlled_ocr_artifacts(
        result,
        output_dir,
        allow_write=True,
    )
    artifact = json.loads(written.artifact_path.read_text(encoding="utf-8"))
    manifest = json.loads(written.manifest_path.read_text(encoding="utf-8"))

    assert written.artifact_path.exists()
    assert written.manifest_path.exists()
    assert (output_dir / "pages" / "page_001" / "raw_ocr.txt").exists()
    assert (output_dir / "pages" / "page_001" / "normalized_ocr.txt").exists()
    assert validate_ocr_artifact(artifact).valid
    assert validate_ocr_manifest(manifest).valid
    assert manifest["artifact"]["sha256"] == written.artifact_sha256
    assert not (output_dir / "pages" / "page_001" / "rendered_page.png").exists()


def test_d7a_can_load_controlled_ocr_artifact_without_running_ocr(
    tmp_path: Path,
) -> None:
    source = tmp_path / "synthetic.pdf"
    _write_pdf(source, ["Fictional native text."])
    fake = FakeTesseract(ocr_stdout="Fictional native text.\n")
    request = ControlledOcrRequest(
        source_path=source,
        document_id="synthetic_controlled_ocr",
        languages=("eng",),
    )
    result = run_controlled_tesseract_ocr(
        request,
        command_resolver=fake.resolver,
        command_runner=fake.runner,
    )
    output_dir = tmp_path / "ocr_output"
    written = write_controlled_ocr_artifacts(
        result,
        output_dir,
        allow_write=True,
    )

    d7a_text = load_engineering_ocr_text_artifact(written.artifact_path)
    controlled_artifact = load_ocr_document_artifact(written.artifact_path)

    assert d7a_text == {1: "Fictional native text.\n"}
    assert ocr_artifact_to_page_texts(controlled_artifact) == {
        1: "Fictional native text.\n"
    }
    assert controlled_artifact["engine"]["name"] == "tesseract"
    assert controlled_artifact["pages"][0]["provenance"]["ocr_engine"] == "tesseract"


def test_subprocess_runner_uses_shell_false(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> object:
        captured["command"] = command
        captured["shell"] = kwargs.get("shell")
        captured["text"] = kwargs.get("text")
        return TesseractProcessResult(0, "ok", "")

    monkeypatch.setattr("techdoc_parser.ocr.tesseract_adapter.subprocess.run", fake_run)

    completed = _run_subprocess(("tesseract", "--version"), 5)

    assert completed.stdout == "ok"
    assert captured["command"] == ["tesseract", "--version"]
    assert captured["shell"] is False
    assert captured["text"] is True


def test_committed_expected_ocr_fixtures_are_valid() -> None:
    fixture_root = ROOT / "tests" / "fixtures" / "controlled_ocr"
    artifact = json.loads(
        (fixture_root / "expected_ocr_artifact.json").read_text(encoding="utf-8")
    )
    manifest = json.loads(
        (fixture_root / "expected_ocr_manifest.json").read_text(encoding="utf-8")
    )

    assert validate_ocr_artifact(artifact).valid
    assert validate_ocr_manifest(manifest).valid


def test_cli_requires_explicit_output_write_flag(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.pdf"
    _write_pdf(source, ["Fictional text."])

    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--source",
            str(source),
            "--document-id",
            "synthetic_controlled_ocr",
            "--language",
            "eng",
            "--output-dir",
            str(tmp_path / "ocr_output"),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert completed.returncode == 1
    assert "Controlled OCR execution only." in completed.stdout
    assert "--output-dir requires --allow-output-write" in completed.stderr


def _write_pdf(path: Path, pages: list[str]) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 72), text, fontsize=11)
    document.save(path)
    document.close()
