"""Reporting helpers for the read-only pilot corpus inventory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from techdoc_parser.evaluation.pilot_corpus_inventory import (
    ACCURACY_DISCLAIMER,
    PilotCorpusInventoryResult,
    PilotDocumentInventory,
    RepresentativePageSelection,
    pilot_corpus_inventory_result_to_json,
)


def pilot_corpus_inventory_result_to_markdown(
    result: PilotCorpusInventoryResult,
    *,
    include_hashes: bool = False,
) -> str:
    """Serialize inventory result to deterministic Markdown with no source text."""
    lines = [
        "# Pilot Corpus Inventory",
        "",
        "## Executive Summary",
        "",
        ACCURACY_DISCLAIMER,
        "",
        f"- Outcome: `{result.outcome}`",
        f"- Corpus path label: `{result.corpus_path_label}`",
        (
            f"- PDF count: `{result.document_count}` of expected "
            f"`{result.expected_document_count}`"
        ),
        f"- Total pages: `{result.total_pages}`",
        f"- Total size bytes: `{result.total_size_bytes}`",
        f"- Proposed representative pages: `{result.proposed_page_count}`",
        "",
        "## Corpus Count and Integrity",
        "",
        f"- Duplicate hash groups: `{len(result.duplicate_hashes)}`",
        f"- Missing expected documents: `{len(result.missing_expected_documents)}`",
        f"- Unexpected documents: `{len(result.unexpected_documents)}`",
        "",
        "## Git-Ignore Verification",
        "",
        _mapping_line(result.git_ignore_summary),
        "",
        "## Per-Document Inventory",
        "",
        (
            "| Document | Filename | Size MiB | Pages | Text Mode | "
            "Orientation | Outline | Labels | Review Burden |"
        ),
        "| --- | --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for document in result.documents:
        orientation = _dominant_key(document.orientation_summary)
        outline = (
            "present" if document.outline_summary.get("outline_present") else "absent"
        )
        labels = (
            "present" if document.page_label_summary.get("labels_present") else "absent"
        )
        lines.append(
            f"| {document.title} | `{document.filename}` | "
            f"{document.file.size_mib:.3f} | {document.page_count} | "
            f"`{document.text_mode}` | `{orientation}` | {outline} | "
            f"{labels} | `{document.review_burden}` |"
        )
        if include_hashes:
            lines.append(f"| SHA-256 | `{document.file.sha256}` |  |  |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## PDF Access and Encryption Status",
            "",
            (
                "| Filename | Access | Encrypted | Password Required | "
                "Extraction Permitted |"
            ),
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for document in result.documents:
        lines.append(
            f"| `{document.filename}` | `{document.access_status}` | "
            f"`{document.encrypted}` | `{document.password_required}` | "
            f"`{document.extraction_permitted}` |"
        )
    lines.extend(
        [
            "",
            "## Native Scanned Mixed Classification",
            "",
            _mapping_line(result.text_mode_counts),
            "",
            "## Page Geometry Summary",
            "",
            _mapping_line(result.orientation_counts),
            "",
            "## Outline Bookmark Summary",
            "",
        ]
    )
    lines.extend(_document_mapping_rows(result.documents, "outline_summary"))
    lines.extend(["", "## Page Label Summary", ""])
    lines.extend(_document_mapping_rows(result.documents, "page_label_summary"))
    lines.extend(["", "## Text Density Summary", ""])
    lines.extend(_document_mapping_rows(result.documents, "text_density_summary"))
    lines.extend(["", "## Layout Summary", ""])
    lines.extend(_document_mapping_rows(result.documents, "layout_summary"))
    lines.extend(["", "## Special Content Indicators", ""])
    for document in result.documents:
        lines.append(f"### {document.filename}")
        if document.special_content_summary:
            for key, pages in sorted(document.special_content_summary.items()):
                lines.append(f"- `{key}`: `{list(pages)}`")
        else:
            lines.append("- No candidate indicators found.")
        lines.append("")
    lines.extend(["## Proposed Representative Pages", ""])
    for document in result.documents:
        lines.append(f"### {document.filename}")
        lines.extend(_selection_lines(document.representative_pages))
        lines.append("")
    lines.extend(
        [
            "## Pilot Roles",
            "",
        ]
    )
    for document in result.documents:
        lines.append(f"- `{document.filename}`: `{list(document.pilot_roles)}`")
    lines.extend(
        [
            "",
            "## P0 P1 P2 Priorities",
            "",
            _mapping_line(result.priority_counts),
            "",
            "## Manual Review Burden",
            "",
        ]
    )
    for document in result.documents:
        lines.append(f"- `{document.filename}`: `{document.review_burden}`")
    lines.extend(
        [
            "",
            "## Known Limitations",
            "",
            "- This inventory stores counts, classifications, and page numbers only.",
            "- It does not include long excerpts, full extracted text, or images.",
            (
                "- Bookmarks and page labels are planning evidence, "
                "not authoritative structure."
            ),
            (
                "- Column and special-content indicators are heuristics "
                "for page selection only."
            ),
            "",
            "## Owner Approval Checklist",
            "",
            "- Confirm all eight documents are authorized for local evaluation.",
            "- Confirm filenames and local hashes are acceptable for inventory use.",
            "- Confirm proposed P0 pages are approved for the next phase.",
            "- Confirm no proprietary/internal wording is committed.",
            "- Confirm scanned/OCR handling, if needed, is explicitly approved later.",
            "",
            "## Accuracy Statement",
            "",
            "Source accuracy was not evaluated in Phase 13I-b1.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_pilot_corpus_inventory_reports(
    result: PilotCorpusInventoryResult,
    *,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    allow_report_write: bool = False,
    include_hashes: bool = True,
    overwrite: bool = True,
) -> tuple[Path, ...]:
    """Write JSON/Markdown reports only with explicit permission."""
    if (json_path is not None or markdown_path is not None) and not allow_report_write:
        raise PermissionError(
            "Pilot corpus report writing requires allow_report_write=True."
        )
    written: list[Path] = []
    if json_path is not None:
        path = Path(json_path)
        _write_text(
            path,
            pilot_corpus_inventory_result_to_json(
                result, include_hashes=include_hashes
            ),
            overwrite=overwrite,
        )
        written.append(path)
    if markdown_path is not None:
        path = Path(markdown_path)
        _write_text(
            path,
            pilot_corpus_inventory_result_to_markdown(
                result,
                include_hashes=include_hashes,
            ),
            overwrite=overwrite,
        )
        written.append(path)
    return tuple(written)


def _write_text(path: Path, text: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing report: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _document_mapping_rows(
    documents: tuple[PilotDocumentInventory, ...],
    field_name: str,
) -> list[str]:
    lines = ["| Filename | Summary |", "| --- | --- |"]
    for document in documents:
        mapping = getattr(document, field_name)
        lines.append(f"| `{document.filename}` | {_mapping_line(mapping)} |")
    return lines


def _selection_lines(selections: tuple[RepresentativePageSelection, ...]) -> list[str]:
    if not selections:
        return ["- No pages proposed."]
    return [
        "- "
        f"index `{selection.pdf_page_index}`, page `{selection.page_number}`, "
        f"label `{selection.printed_page_label}`, priority `{selection.priority}`, "
        f"roles `{list(selection.evaluation_roles)}`, "
        f"reasons `{list(selection.selection_reason)}`, "
        f"status `{selection.selection_status}`"
        for selection in selections
    ]


def _mapping_line(mapping: Any) -> str:
    if not isinstance(mapping, dict):
        return f"`{mapping}`"
    items = ", ".join(f"{key}: {value}" for key, value in sorted(mapping.items()))
    return f"`{items}`"


def _dominant_key(mapping: Any) -> str:
    if not isinstance(mapping, dict) or not mapping:
        return "unknown"
    return str(max(mapping.items(), key=lambda item: (item[1], item[0]))[0])


__all__ = [
    "pilot_corpus_inventory_result_to_markdown",
    "write_pilot_corpus_inventory_reports",
]
