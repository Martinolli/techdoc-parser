"""Report and local evidence writers for the P0 source-accuracy pilot."""

from __future__ import annotations

import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]

from techdoc_parser.evaluation.source_accuracy import (
    LocalPageEvidence,
    SourceAccuracyPageResult,
    SourceAccuracyPilotResult,
    build_local_page_evidence,
    default_visual_review_checklist,
    source_accuracy_pilot_result_to_json,
    source_accuracy_pilot_result_to_markdown,
)
from techdoc_parser.ingestion import PDFLoader


def write_source_accuracy_reports(
    result: SourceAccuracyPilotResult,
    *,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    allow_report_write: bool = False,
    overwrite: bool = True,
) -> tuple[Path, ...]:
    """Write sanitized aggregate reports only with explicit permission."""
    if (json_path is not None or markdown_path is not None) and not allow_report_write:
        raise PermissionError(
            "Source-accuracy report writing requires allow_report_write=True."
        )
    written: list[Path] = []
    if json_path is not None:
        path = Path(json_path)
        _write_text(
            path,
            source_accuracy_pilot_result_to_json(result),
            overwrite=overwrite,
        )
        written.append(path)
    if markdown_path is not None:
        path = Path(markdown_path)
        _write_text(
            path,
            source_accuracy_pilot_result_to_markdown(result),
            overwrite=overwrite,
        )
        written.append(path)
    return tuple(written)


def write_local_page_evidence_package(
    *,
    output_dir: str | Path,
    source_path: str | Path,
    page_results: tuple[SourceAccuracyPageResult, ...],
    allow_local_write: bool = False,
    overwrite: bool = True,
) -> tuple[Path, ...]:
    """Write local full evidence package only when explicitly allowed."""
    if not allow_local_write:
        raise PermissionError(
            "Local source-accuracy evidence writing requires allow_local_write=True."
        )
    root = Path(output_dir)
    written: list[Path] = []
    for result in page_results:
        evidence = build_local_page_evidence(source_path=source_path, result=result)
        page_dir = _safe_child(root, result.document_key, f"page_{result.page_number}")
        page_dir.mkdir(parents=True, exist_ok=True)
        written.extend(
            _write_page_evidence_files(
                page_dir=page_dir,
                source_path=Path(source_path),
                evidence=evidence,
                overwrite=overwrite,
            )
        )
    return tuple(written)


def write_local_pilot_evidence_package(
    *,
    output_dir: str | Path,
    input_dir: str | Path,
    result: SourceAccuracyPilotResult,
    allow_local_write: bool = False,
    overwrite: bool = True,
) -> tuple[Path, ...]:
    """Write local evidence package for all page results in a pilot result."""
    if not allow_local_write:
        raise PermissionError(
            "Local source-accuracy evidence writing requires allow_local_write=True."
        )
    input_root = Path(input_dir)
    root = Path(output_dir)
    written: list[Path] = []
    by_source: dict[Path, list[SourceAccuracyPageResult]] = {}
    for page in result.page_results:
        by_source.setdefault(input_root / page.filename, []).append(page)
    for source_path, pages in sorted(by_source.items(), key=lambda item: item[0].name):
        parser_document = PDFLoader(str(source_path)).load()
        for page in sorted(pages, key=lambda item: item.pdf_page_index):
            evidence = build_local_page_evidence(
                source_path=source_path,
                result=page,
                parser_document=parser_document,
            )
            page_dir = _safe_child(root, page.document_key, f"page_{page.page_number}")
            page_dir.mkdir(parents=True, exist_ok=True)
            written.extend(
                _write_page_evidence_files(
                    page_dir=page_dir,
                    source_path=source_path,
                    evidence=evidence,
                    overwrite=overwrite,
                )
            )
    return tuple(written)


def _write_page_evidence_files(
    *,
    page_dir: Path,
    source_path: Path,
    evidence: LocalPageEvidence,
    overwrite: bool,
) -> tuple[Path, ...]:
    result = evidence.page_result
    written: list[Path] = []
    payloads = {
        "source_proxy.json": evidence.source_proxy,
        "parser_blocks.json": list(evidence.parser_blocks),
        "parser_sections.json": list(evidence.parser_sections),
        "parser_entities.json": evidence.parser_entities,
        "parser_chunks.json": list(evidence.parser_chunks),
        "review_checklist.json": default_visual_review_checklist(
            f"{result.document_key}:p{result.pdf_page_index}"
        ),
    }
    for filename, payload in payloads.items():
        path = page_dir / filename
        _write_text(
            path,
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            overwrite=overwrite,
        )
        written.append(path)
    png_path = page_dir / "page.png"
    _render_page_png(
        source_path=source_path,
        pdf_page_index=result.pdf_page_index,
        output_path=png_path,
        overwrite=overwrite,
    )
    written.append(png_path)
    html_path = page_dir / "review.html"
    _write_text(html_path, _review_html(result), overwrite=overwrite)
    written.append(html_path)
    return tuple(written)


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


def _review_html(result: SourceAccuracyPageResult) -> str:
    checklist = default_visual_review_checklist(
        f"{result.document_key}:p{result.pdf_page_index}"
    )
    checks = checklist["checks"]
    assert isinstance(checks, dict)
    check_rows = "\n".join(
        f"<tr><td>{name}</td><td>{value}</td></tr>"
        for name, value in sorted(checks.items())
    )
    metric_rows = "\n".join(
        f"<tr><td>{metric.name}</td><td>{metric.status}</td><td>{metric.value}</td></tr>"
        for metric in result.metrics
    )
    finding_rows = "\n".join(
        (
            f"<tr><td>{finding.code}</td><td>{finding.category}</td>"
            f"<td>{finding.severity}</td><td>{finding.message}</td></tr>"
        )
        for finding in result.findings
    )
    return (
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8"><title>P0 Review</title>'
        "<style>body{font-family:Arial,sans-serif;margin:1rem;}"
        "img{max-width:48vw;border:1px solid #aaa;}"
        ".grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;}"
        "table{border-collapse:collapse;width:100%;}"
        "td,th{border:1px solid #ccc;padding:.25rem;vertical-align:top;}"
        "</style></head><body>\n"
        f"<h1>{result.document_key} page {result.page_number}</h1>\n"
        "<p>Local evidence only. Visual checks default to pending.</p>\n"
        '<div class="grid"><div><img src="page.png" alt="source page"></div>'
        "<div><h2>Metrics</h2><table>"
        "<tr><th>Name</th><th>Status</th><th>Value</th></tr>"
        f"{metric_rows}</table><h2>Findings</h2><table>"
        "<tr><th>Code</th><th>Category</th><th>Severity</th><th>Message</th></tr>"
        f"{finding_rows}</table></div></div>\n"
        "<h2>Review Checklist</h2><table>"
        "<tr><th>Check</th><th>Status</th></tr>"
        f"{check_rows}</table>\n"
        "</body></html>\n"
    )


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
    "write_local_page_evidence_package",
    "write_local_pilot_evidence_package",
    "write_source_accuracy_reports",
]
