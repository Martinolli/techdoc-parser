"""Simple semantic chunk creation for RAG-oriented output."""

from __future__ import annotations

from techdoc_parser.core import (
    Block,
    Chunk,
    Document,
    FigureBlock,
    FormulaBlock,
    HeadingBlock,
    ParagraphBlock,
    TableBlock,
    TableRegionBlock,
)
from techdoc_parser.structure import get_semantic_blocks_for_page
from techdoc_parser.structure.semantic import is_semantic_furniture_text


def create_semantic_chunks(document: Document, max_chars: int = 1200) -> list[Chunk]:
    """Create simple semantic chunks from a document."""
    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_page_numbers: list[int] = []
    current_block_ids: list[str] = []
    current_text_block_ids: list[str] = []
    heading_context: dict[int, str] = {}
    current_chunk_context: dict[int, str] = {}
    current_has_non_heading = False

    for page in document.pages:
        for block in get_semantic_blocks_for_page(page):
            block_text = block_to_chunk_text(block)
            if not block_text:
                continue

            is_heading = get_heading_level(block) is not None
            if is_heading:
                if current_parts and current_has_non_heading:
                    chunks.append(
                        _create_chunk(
                            document=document,
                            chunk_index=len(chunks) + 1,
                            text=_join_chunk_parts(current_parts),
                            source_page_numbers=current_page_numbers,
                            source_block_ids=current_block_ids,
                            source_text_block_ids=current_text_block_ids,
                            section_context=current_chunk_context,
                        )
                    )
                    current_parts = []
                    current_page_numbers = []
                    current_block_ids = []
                    current_text_block_ids = []
                    current_chunk_context = {}
                    current_has_non_heading = False
                update_heading_context(block, heading_context)

            block_context = dict(heading_context)
            candidate_text = _join_chunk_parts([*current_parts, block_text])
            if current_parts and len(candidate_text) > max_chars:
                chunks.append(
                    _create_chunk(
                        document=document,
                        chunk_index=len(chunks) + 1,
                        text=_join_chunk_parts(current_parts),
                        source_page_numbers=current_page_numbers,
                        source_block_ids=current_block_ids,
                        source_text_block_ids=current_text_block_ids,
                        section_context=current_chunk_context,
                    )
                )
                current_parts = []
                current_page_numbers = []
                current_block_ids = []
                current_text_block_ids = []
                current_chunk_context = {}
                current_has_non_heading = False

            current_chunk_context = block_context
            current_parts.append(block_text)
            current_has_non_heading = current_has_non_heading or not is_heading
            _append_unique_int(
                current_page_numbers,
                get_block_page_number(block) or page.page_number,
            )
            block_id = get_block_id(block)
            if block_id is not None:
                _append_unique_str(current_block_ids, block_id)
            for source_text_block_id in get_block_source_text_ids(block):
                _append_unique_str(current_text_block_ids, source_text_block_id)

    if current_parts:
        chunks.append(
            _create_chunk(
                document=document,
                chunk_index=len(chunks) + 1,
                text=_join_chunk_parts(current_parts),
                source_page_numbers=current_page_numbers,
                source_block_ids=current_block_ids,
                source_text_block_ids=current_text_block_ids,
                section_context=current_chunk_context,
            )
        )

    return chunks


def block_to_chunk_text(block: Block) -> str:
    """Render a semantic block as chunk text."""
    text = clean_chunk_text(_block_text(block))
    if not text:
        return ""
    if isinstance(block, TableRegionBlock):
        return f"[Table region candidate]\n{text}"
    if isinstance(block, TableBlock):
        return f"[Table candidate]\n{text}"
    if isinstance(block, FigureBlock):
        return f"[Figure candidate]\n{text}"
    if isinstance(block, FormulaBlock):
        return f"[Formula candidate]\n{text}"
    return text


def get_block_id(block: Block) -> str | None:
    """Return a block id for source tracking."""
    return block.id or None


def get_block_source_text_ids(block: Block) -> list[str]:
    """Return source text block ids for supported semantic blocks."""
    if isinstance(block, ParagraphBlock | TableBlock | TableRegionBlock | FigureBlock):
        return block.source_text_block_ids
    return []


def get_block_page_number(block: Block) -> int | None:
    """Return the source page number for a block, if available."""
    if block.source is None:
        return None
    return block.source.page_number


def update_heading_context(block: Block, context: dict[int, str]) -> None:
    """Update active heading context with a heading block."""
    level = get_heading_level(block)
    if level is None:
        return
    heading_text = get_heading_text(block)
    if not heading_text:
        return
    for existing_level in list(context):
        if existing_level >= level:
            del context[existing_level]
    context[level] = heading_text


def get_heading_level(block: Block) -> int | None:
    """Return a clamped heading level for a heading block."""
    if not isinstance(block, HeadingBlock):
        return None
    return min(max(block.level, 1), 6)


def get_heading_text(block: Block) -> str:
    """Return cleaned heading text."""
    return clean_chunk_text(_block_text(block))


def build_section_path(context: dict[int, str]) -> str:
    """Return active section path from shallowest to deepest heading."""
    return " > ".join(text for _level, text in sorted(context.items()))


def get_current_section_title(context: dict[int, str]) -> str | None:
    """Return the deepest active section title."""
    if not context:
        return None
    return context[max(context)]


def clean_chunk_text(text: str) -> str:
    """Remove standalone page/document furniture lines from chunk text."""
    cleaned_lines: list[str] = []
    previous_blank = False

    for line in text.splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            if cleaned_lines and not previous_blank:
                cleaned_lines.append("")
                previous_blank = True
            continue
        if is_semantic_furniture_text(stripped_line):
            continue
        cleaned_lines.append(line)
        previous_blank = False

    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()

    return "\n".join(cleaned_lines)


def _create_chunk(
    *,
    document: Document,
    chunk_index: int,
    text: str,
    source_page_numbers: list[int],
    source_block_ids: list[str],
    source_text_block_ids: list[str],
    section_context: dict[int, str],
) -> Chunk:
    metadata = _chunk_metadata(document, chunk_index, section_context)
    return Chunk(
        id=f"chunk-{chunk_index}",
        document_id=document.id,
        text=text,
        source_page_numbers=list(source_page_numbers),
        source_block_ids=list(source_block_ids),
        source_text_block_ids=list(source_text_block_ids),
        chunk_type="semantic",
        metadata=metadata,
    )


def _chunk_metadata(
    document: Document,
    chunk_index: int,
    section_context: dict[int, str],
) -> dict[str, str]:
    metadata = {
        "chunk_index": str(chunk_index),
        "chunk_type": "semantic",
    }
    if document.source_path:
        metadata["source_path"] = document.source_path
    if document.metadata.title:
        metadata["title"] = document.metadata.title
    section_title = get_current_section_title(section_context)
    section_path = build_section_path(section_context)
    if section_title is not None:
        metadata["section_title"] = section_title
        metadata["section_level"] = str(max(section_context))
    if section_path:
        metadata["section_path"] = section_path
    return metadata


def _block_text(block: Block) -> str:
    text = block.normalized_text or block.text
    if text is None and isinstance(block, FigureBlock):
        text = block.caption
    if text is None and isinstance(block, FormulaBlock):
        text = block.latex
    return text or ""


def _join_chunk_parts(parts: list[str]) -> str:
    return "\n\n".join(parts)


def _append_unique_str(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _append_unique_int(values: list[int], value: int) -> None:
    if value not in values:
        values.append(value)
