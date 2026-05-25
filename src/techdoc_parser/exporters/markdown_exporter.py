"""Markdown export helpers for parsed documents."""

from pathlib import Path

from techdoc_parser.core import (
    Block,
    BoundingBox,
    Document,
    FigureBlock,
    FormulaBlock,
    HeadingBlock,
    ParagraphBlock,
    SourceLocation,
    TableBlock,
    TextBlock,
)
from techdoc_parser.structure import get_semantic_blocks_for_page


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
            if block.source is not None:
                lines.append(_source_line(block.source))
            lines.extend(_page_furniture_lines(block))
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


def document_to_semantic_markdown(document: Document) -> str:
    """Render a document as semantic Markdown without raw text-block duplicates."""
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

        for block in get_semantic_blocks_for_page(page):
            rendered_block = _render_semantic_block(block)
            if rendered_block:
                lines.extend([rendered_block, ""])

    return "\n".join(lines).rstrip() + "\n"


def export_document_semantic_markdown(
    document: Document,
    output_path: str | Path,
) -> None:
    """Write semantic Markdown to an output path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document_to_semantic_markdown(document), encoding="utf-8")


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


def _page_furniture_lines(block: TextBlock) -> list[str]:
    lines: list[str] = []
    if block.is_page_furniture:
        lines.append("Page furniture: yes")
    if block.is_page_header:
        lines.append("Header: yes")
    if block.is_page_footer:
        lines.append("Footer: yes")
    if block.is_page_number:
        lines.append("Page number: yes")
    return lines


def _format_bbox(bbox: BoundingBox | None) -> str:
    if bbox is None:
        return "None"

    return f"({bbox.x0}, {bbox.y0}, {bbox.x1}, {bbox.y1})"


def _has_distinct_normalized_text(
    text: str | None,
    normalized_text: str | None,
) -> bool:
    return normalized_text is not None and normalized_text != (text or "")


def _block_text(block: Block) -> str:
    text = block.normalized_text or block.text
    if text is None and isinstance(block, FigureBlock):
        text = block.caption
    if text is None and isinstance(block, FormulaBlock):
        text = block.latex
    return text or ""


def _render_semantic_block(block: Block) -> str:
    if isinstance(block, HeadingBlock):
        return _render_heading_block(block)
    if isinstance(block, ParagraphBlock):
        return _render_paragraph_block(block)
    if isinstance(block, TableBlock):
        return _render_table_block(block)
    if isinstance(block, FigureBlock):
        return _render_figure_block(block)
    if isinstance(block, FormulaBlock):
        return _render_formula_block(block)
    return ""


def _render_heading_block(block: HeadingBlock) -> str:
    level = min(max(block.level, 1), 6)
    heading_text = _block_text(block)
    lines = [f"{'#' * level} {heading_text}"]
    lines.append(_semantic_source_line(block))
    return "\n".join(lines)


def _render_paragraph_block(block: ParagraphBlock) -> str:
    paragraph_text = _block_text(block)
    lines = [paragraph_text]
    lines.append(_semantic_source_line(block))
    return "\n".join(lines)


def _render_table_block(block: TableBlock) -> str:
    table_text = _block_text(block)
    lines = [
        "**Table candidate**",
        "",
        _semantic_source_line(block),
        "",
        "```text",
        table_text,
        "```",
    ]
    return "\n".join(lines)


def _render_figure_block(block: FigureBlock) -> str:
    figure_text = _block_text(block)
    lines = [f"**Figure candidate:** {figure_text}"]
    lines.append(_semantic_source_line(block))
    return "\n".join(lines)


def _render_formula_block(block: FormulaBlock) -> str:
    formula_text = _block_text(block)
    lines = [
        "**Formula candidate**",
        "",
        _semantic_source_line(block),
        "",
        formula_text,
    ]
    return "\n".join(lines)


def _semantic_source_line(block: Block) -> str:
    page_number = block.source.page_number if block.source is not None else None
    page = str(page_number) if page_number is not None else "unknown"
    return f"_Source: page {page}, block {block.id}_"
