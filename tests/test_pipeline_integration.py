"""Integration tests for the generated-PDF parsing pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import fitz

from techdoc_parser.core import HeadingBlock, ParagraphBlock, TextBlock
from techdoc_parser.exporters import export_document_json
from techdoc_parser.ingestion import PDFLoader


def _create_pipeline_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=500.0, height=800.0)
    page.insert_text((36.0, 24.0), "MIL-STD-TEST", fontsize=9.0)
    page.insert_text((36.0, 110.0), "1. SCOPE", fontsize=14.0)
    page.insert_text(
        (36.0, 145.0),
        "This test document verifies the parser pipeline.",
        fontsize=10.0,
    )
    page.insert_text((36.0, 210.0), "2. APPLICABLE DOCUMENTS", fontsize=14.0)
    page.insert_text(
        (36.0, 245.0),
        "No external documents are required for this generated test.",
        fontsize=10.0,
    )
    page.insert_text(
        (36.0, 735.0),
        "Source: https://assist.dla.mil -- Downloaded: 2026-05-03T05:52Z",
        fontsize=8.0,
    )
    page.insert_text((250.0, 780.0), "1", fontsize=9.0)
    document.save(path)
    document.close()


def test_generated_pdf_pipeline_to_document_and_json(tmp_path: Path) -> None:
    """A generated PDF should parse through text, structure, and JSON export."""
    pdf_path = tmp_path / "pipeline.pdf"
    json_path = tmp_path / "pipeline.json"
    _create_pipeline_pdf(pdf_path)

    document = PDFLoader(str(pdf_path)).load()

    assert len(document.pages) == 1
    page = document.pages[0]
    assert page.has_native_text is True
    assert page.requires_ocr is False
    assert page.text_blocks
    assert all(isinstance(block, TextBlock) for block in page.text_blocks)
    assert any(isinstance(block, TextBlock) for block in page.blocks)
    assert any(isinstance(block, HeadingBlock) for block in page.blocks)
    assert any(isinstance(block, ParagraphBlock) for block in page.blocks)

    header_blocks = [
        block for block in page.text_blocks if block.normalized_text == "MIL-STD-TEST"
    ]
    page_number_blocks = [
        block for block in page.text_blocks if block.normalized_text == "1"
    ]
    source_footer_blocks = [
        block
        for block in page.text_blocks
        if (block.normalized_text or "").startswith("Source: https://assist.dla.mil")
    ]

    assert header_blocks
    assert header_blocks[0].is_page_header
    assert header_blocks[0].is_page_furniture
    assert page_number_blocks
    assert page_number_blocks[0].is_page_number
    assert page_number_blocks[0].is_page_furniture
    assert source_footer_blocks
    assert source_footer_blocks[0].is_page_footer
    assert source_footer_blocks[0].is_page_furniture

    heading_texts = [
        block.normalized_text
        for block in page.blocks
        if isinstance(block, HeadingBlock)
    ]
    paragraph_blocks = [
        block for block in page.blocks if isinstance(block, ParagraphBlock)
    ]
    paragraph_texts = [block.normalized_text for block in paragraph_blocks]

    assert "1. SCOPE" in heading_texts
    assert "2. APPLICABLE DOCUMENTS" in heading_texts
    assert "MIL-STD-TEST" not in heading_texts
    assert "1" not in heading_texts
    assert not any((text or "").startswith("Source:") for text in heading_texts)
    assert "1. SCOPE" not in paragraph_texts
    assert "2. APPLICABLE DOCUMENTS" not in paragraph_texts
    assert "MIL-STD-TEST" not in paragraph_texts
    assert "1" not in paragraph_texts
    assert not any((text or "").startswith("Source:") for text in paragraph_texts)
    assert "This test document verifies the parser pipeline." in paragraph_texts
    assert (
        "No external documents are required for this generated test." in paragraph_texts
    )
    assert all(block.source is not None for block in paragraph_blocks)
    assert all(block.source_text_block_ids for block in paragraph_blocks)

    export_document_json(document, str(json_path))
    data = json.loads(json_path.read_text(encoding="utf-8"))
    json_page = data["pages"][0]
    block_types = [block["block_type"] for block in json_page["blocks"]]
    text_block_data = json_page["text_blocks"]
    paragraph_data = [
        block for block in json_page["blocks"] if block["block_type"] == "paragraph"
    ]

    assert "pages" in data
    assert json_page["blocks"]
    assert "text" in block_types
    assert "heading" in block_types
    assert "paragraph" in block_types
    assert any(block["is_page_furniture"] for block in text_block_data)
    assert any(block["is_page_header"] for block in text_block_data)
    assert any(block["is_page_footer"] for block in text_block_data)
    assert any(block["is_page_number"] for block in text_block_data)
    assert all(block["source_text_block_ids"] for block in paragraph_data)
