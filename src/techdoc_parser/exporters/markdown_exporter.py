"""Markdown export helpers for parsed documents."""

from pathlib import Path

from techdoc_parser.core import BoundingBox, Document, SourceLocation


def document_to_markdown(document: Document) -> str:
    """Render a document as simple text-block-based Markdown."""
    lines: list[str] = []
    title = document.metadata.title or document.id

    lines.extend(
        [
            f"# {title}",
            "",
            f"Source path: {document.source_path}",
            "",
            "## Metadata",
            "",
        ]
    )
    lines.extend(_metadata_lines(document))

    for page in document.pages:
        lines.extend(
            [
                "",
                f"## Page {page.page_number}",
                "",
                f"- has_native_text: {page.has_native_text}",
                f"- requires_ocr: {page.requires_ocr}",
                "",
            ]
        )

        for block in page.text_blocks:
            lines.append(_source_line(block.source))
            if _has_distinct_normalized_text(block.text, block.normalized_text):
                lines.append("Normalized text available: yes")
            lines.extend(["", block.text or "", ""])

    return "\n".join(lines).rstrip() + "\n"


def export_document_markdown(document: Document, output_path: str) -> None:
    """Write a document as Markdown to an output path.

    Parent directories are created automatically. The output path is not required
    to use a `.md` extension.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document_to_markdown(document), encoding="utf-8")


def _metadata_lines(document: Document) -> list[str]:
    metadata = document.metadata
    fields = [
        ("title", metadata.title),
        ("author", metadata.author),
        ("subject", metadata.subject),
        ("keywords", ", ".join(metadata.keywords) if metadata.keywords else None),
        ("producer", metadata.producer),
        ("creator", metadata.creator),
    ]

    lines = [f"- {name}: {value}" for name, value in fields if value]
    return lines if lines else ["- none"]


def _source_line(source: SourceLocation) -> str:
    return (
        f"Source: page {source.page_number}, "
        f"bbox {_format_bbox(source.bbox)}, "
        f"method {source.extraction_method}, "
        f"confidence {source.confidence}"
    )


def _format_bbox(bbox: BoundingBox | None) -> str:
    if bbox is None:
        return "None"

    return f"({bbox.x0}, {bbox.y0}, {bbox.x1}, {bbox.y1})"


def _has_distinct_normalized_text(
    text: str | None,
    normalized_text: str | None,
) -> bool:
    return normalized_text is not None and normalized_text != (text or "")
