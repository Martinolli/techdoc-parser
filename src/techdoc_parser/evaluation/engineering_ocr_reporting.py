"""Reporting and local package writers for engineering OCR-fidelity evaluation."""

from __future__ import annotations

import html
import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from techdoc_parser.evaluation.engineering_ocr_fidelity import (
    EngineeringOcrEvaluationResult,
    EngineeringOcrPageEvidence,
    default_owner_review_decision,
    engineering_ocr_result_to_json,
    engineering_ocr_result_to_markdown,
    owner_review_decision_to_dict,
)


def write_engineering_ocr_reports(
    result: EngineeringOcrEvaluationResult,
    *,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    allow_report_write: bool = False,
    overwrite: bool = True,
) -> tuple[Path, ...]:
    """Write sanitized aggregate reports only with explicit permission."""
    if (json_path is not None or markdown_path is not None) and not allow_report_write:
        raise PermissionError(
            "Engineering OCR-fidelity report writing requires allow_report_write=True."
        )
    written: list[Path] = []
    if json_path is not None:
        path = Path(json_path)
        _write_text(path, engineering_ocr_result_to_json(result), overwrite=overwrite)
        written.append(path)
    if markdown_path is not None:
        path = Path(markdown_path)
        _write_text(
            path,
            engineering_ocr_result_to_markdown(result),
            overwrite=overwrite,
        )
        written.append(path)
    return tuple(written)


def write_engineering_ocr_review_package(
    *,
    output_dir: str | Path,
    source_path: str | Path | None,
    page_results: tuple[EngineeringOcrPageEvidence, ...],
    native_text_by_page: dict[int, str] | None = None,
    ocr_text_by_page: dict[int, str] | None = None,
    allow_local_write: bool = False,
    overwrite: bool = True,
) -> tuple[Path, ...]:
    """Write local review assets only when explicitly allowed."""
    if not allow_local_write:
        raise PermissionError(
            "Engineering OCR-fidelity review package requires allow_local_write=True."
        )
    root = Path(output_dir)
    source = Path(source_path) if source_path is not None else None
    written: list[Path] = []
    for page in page_results:
        page_dir = _safe_child(root, page.document_key, f"page_{page.page_number}")
        page_dir.mkdir(parents=True, exist_ok=True)
        summary_path = page_dir / "automated_summary.json"
        _write_text(
            summary_path,
            json.dumps(_page_summary(page), indent=2, sort_keys=True) + "\n",
            overwrite=overwrite,
        )
        written.append(summary_path)
        checklist_path = page_dir / "review_checklist.json"
        if not checklist_path.exists():
            decision = default_owner_review_decision(
                document_key=page.document_key,
                pdf_page_index=page.pdf_page_index,
                page_number=page.page_number,
            )
            _write_text(
                checklist_path,
                json.dumps(
                    owner_review_decision_to_dict(decision),
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                overwrite=False,
            )
            written.append(checklist_path)
        if source is not None and source.exists():
            png_path = page_dir / "page.png"
            _render_page_png(
                source_path=source,
                pdf_page_index=page.pdf_page_index,
                output_path=png_path,
                overwrite=overwrite,
            )
            written.append(png_path)
        if native_text_by_page is not None and page.page_number in native_text_by_page:
            native_path = page_dir / "native_text_baseline.txt"
            _write_text(
                native_path,
                native_text_by_page[page.page_number],
                overwrite=overwrite,
            )
            written.append(native_path)
        if ocr_text_by_page is not None and page.page_number in ocr_text_by_page:
            ocr_path = page_dir / "ocr_candidate.txt"
            _write_text(
                ocr_path,
                ocr_text_by_page[page.page_number],
                overwrite=overwrite,
            )
            written.append(ocr_path)
        html_path = page_dir / "review.html"
        _write_text(html_path, _review_html(page), overwrite=overwrite)
        written.append(html_path)
    return tuple(written)


def _page_summary(page: EngineeringOcrPageEvidence) -> dict[str, object]:
    return {
        "document_key": page.document_key,
        "filename": page.filename,
        "pdf_page_index": page.pdf_page_index,
        "page_number": page.page_number,
        "source_page_image_reference": page.source_page_image_reference,
        "native_text_baseline_reference": page.native_text_baseline_reference,
        "ocr_text_candidate_reference": page.ocr_text_candidate_reference,
        "source_profiles": list(page.source_profiles),
        "native_text_character_count": page.native_text_character_count,
        "ocr_text_character_count": page.ocr_text_character_count,
        "reading_order_warnings": list(page.reading_order_warnings),
        "symbol_normalization_warnings": list(page.symbol_normalization_warnings),
        "symbol_substitution_warnings": list(page.symbol_substitution_warnings),
        "owner_checklist_status": page.owner_checklist_status,
        "automated_outcome": page.automated_outcome,
        "final_page_outcome": page.final_page_outcome,
        "needs_second_review": page.needs_second_review,
        "privacy": {
            "sanitized": True,
            "contains_source_text": False,
            "contains_rendered_image": False,
        },
    }


def _review_html(page: EngineeringOcrPageEvidence) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(metric.name)}</td>"
        f"<td>{html.escape(metric.status)}</td>"
        f"<td>{html.escape(str(metric.value))}</td>"
        "</tr>"
        for metric in page.metrics
    )
    findings = "\n".join(
        "<tr>"
        f"<td>{html.escape(finding.code)}</td>"
        f"<td>{html.escape(finding.category)}</td>"
        f"<td>{html.escape(finding.severity)}</td>"
        f"<td>{html.escape(finding.message)}</td>"
        "</tr>"
        for finding in page.findings
    )
    return (
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8">'
        f"<title>D.7a page {page.page_number}</title>"
        "<style>body{font-family:Arial,sans-serif;margin:1rem;}"
        "img{max-width:46vw;border:1px solid #999;}"
        ".grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;}"
        "table{border-collapse:collapse;width:100%;}"
        "td,th{border:1px solid #ccc;padding:.3rem;vertical-align:top;}"
        "</style></head><body>\n"
        f"<h1>D.7a OCR Fidelity Review - page {page.page_number}</h1>\n"
        "<p>Owner checklist starts pending. Automated findings are review aids.</p>\n"
        '<div class="grid"><div><img src="page.png" alt="source page"></div>'
        "<div><h2>Metrics</h2><table>"
        "<tr><th>Name</th><th>Status</th><th>Value</th></tr>"
        f"{rows}</table><h2>Findings</h2><table>"
        "<tr><th>Code</th><th>Category</th><th>Severity</th><th>Message</th></tr>"
        f"{findings}</table></div></div>\n"
        "</body></html>\n"
    )


def _render_page_png(
    *,
    source_path: Path,
    pdf_page_index: int,
    output_path: Path,
    overwrite: bool,
) -> None:
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {output_path}")
    with fitz.open(source_path) as document:
        page = document.load_page(pdf_page_index)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        pixmap.save(output_path)


def _write_text(path: Path, text: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_child(root: Path, *parts: str) -> Path:
    base = root.resolve()
    target = base.joinpath(*parts).resolve()
    target.relative_to(base)
    return target


__all__ = [
    "write_engineering_ocr_reports",
    "write_engineering_ocr_review_package",
]
