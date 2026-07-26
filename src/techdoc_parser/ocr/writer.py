"""File writer for explicit controlled OCR artifacts."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from techdoc_parser.ocr.artifact import controlled_ocr_result_to_json
from techdoc_parser.ocr.manifest import (
    controlled_ocr_manifest_to_json,
    create_controlled_ocr_manifest,
)
from techdoc_parser.ocr.models import (
    ControlledOcrDocumentResult,
    ControlledOcrPageResult,
    ControlledOcrWriteResult,
)


def write_controlled_ocr_artifacts(
    result: ControlledOcrDocumentResult,
    output_dir: str | Path,
    *,
    allow_write: bool = False,
    overwrite: bool = False,
    preserve_rendered_pages: bool = False,
) -> ControlledOcrWriteResult:
    """Write OCR artifacts only when explicitly permitted."""
    if not allow_write:
        raise PermissionError("Controlled OCR artifact writing requires allow_write.")
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    artifact_path = _contained_path(root, "ocr_document.json")
    manifest_path = _contained_path(root, "ocr_manifest.json")
    artifact_bytes = controlled_ocr_result_to_json(result).encode("utf-8")
    manifest = create_controlled_ocr_manifest(
        result,
        artifact_path=artifact_path.name,
        artifact_bytes=artifact_bytes,
    )
    manifest_bytes = controlled_ocr_manifest_to_json(manifest).encode("utf-8")

    page_paths: list[Path] = []
    rendered_paths: list[Path] = []
    _atomic_write(artifact_path, artifact_bytes, overwrite=overwrite)
    _atomic_write(manifest_path, manifest_bytes, overwrite=overwrite)
    for page in result.page_results:
        page_dir = _contained_path(root, f"pages/page_{page.page_number:03d}")
        page_dir.mkdir(parents=True, exist_ok=True)
        raw_path = page_dir / "raw_ocr.txt"
        normalized_path = page_dir / "normalized_ocr.txt"
        provenance_path = page_dir / "provenance.json"
        _atomic_write(
            raw_path,
            page.raw_ocr_text.encode("utf-8"),
            overwrite=overwrite,
        )
        _atomic_write(
            normalized_path,
            page.normalized_ocr_text.encode("utf-8"),
            overwrite=overwrite,
        )
        _atomic_write(
            provenance_path,
            (
                json.dumps(
                    result_page_provenance_dict(page),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8"),
            overwrite=overwrite,
        )
        page_paths.extend((raw_path, normalized_path, provenance_path))
        if preserve_rendered_pages and page.rendered_image_png is not None:
            rendered_path = page_dir / "rendered_page.png"
            _atomic_write(rendered_path, page.rendered_image_png, overwrite=overwrite)
            rendered_paths.append(rendered_path)

    return ControlledOcrWriteResult(
        output_dir=root,
        artifact_path=artifact_path,
        manifest_path=manifest_path,
        page_artifact_paths=tuple(page_paths),
        rendered_page_paths=tuple(rendered_paths),
        artifact_sha256=sha256(artifact_bytes).hexdigest(),
        manifest_sha256=sha256(manifest_bytes).hexdigest(),
    )


def result_page_provenance_dict(page: ControlledOcrPageResult) -> dict[str, object]:
    """Return provenance dictionary for a page result without OCR text."""
    provenance = page.provenance
    return {
        "page_number": provenance.page_number,
        "pdf_page_index": provenance.pdf_page_index,
        "source_sha256": provenance.source_sha256,
        "source_size_bytes": provenance.source_size_bytes,
        "rendered_image_sha256": provenance.rendered_image_sha256,
        "raw_ocr_sha256": provenance.raw_ocr_sha256,
        "normalized_ocr_sha256": provenance.normalized_ocr_sha256,
        "rendering_engine": provenance.rendering_engine,
        "rendering_dpi": provenance.rendering_dpi,
        "ocr_engine": provenance.ocr_engine,
        "ocr_engine_version": provenance.ocr_engine_version,
        "ocr_languages": list(provenance.ocr_languages),
        "ocr_mode": provenance.ocr_mode,
        "psm": provenance.psm,
        "oem": provenance.oem,
    }


def _contained_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    path.relative_to(root)
    return path


def _atomic_write(path: Path, data: bytes, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing OCR artifact: {path}")
    temp = path.with_name(f".{path.name}.tmp")
    if temp.exists():
        temp.unlink()
    temp.write_bytes(data)
    temp.replace(path)


__all__ = [
    "write_controlled_ocr_artifacts",
]
