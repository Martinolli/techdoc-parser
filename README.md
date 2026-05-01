# techdoc-parser

Convert complex technical documents into structured, traceable, machine-usable knowledge while preserving source fidelity.

## Installation

For local development:

```bash
pip install -e ".[dev]"
```

## Basic Usage

```python
from techdoc_parser import parse_document
from techdoc_parser.exporters import export_document_json

document = parse_document("manual.pdf")
export_document_json(document, "output/manual.json")
```

Markdown export:

```python
from techdoc_parser import parse_document
from techdoc_parser.exporters import export_document_markdown

document = parse_document("manual.pdf")
export_document_markdown(document, "output/manual.md")
```

Markdown export is currently simple and text-block based.

## CLI Usage

```bash
techdoc-parse manual.pdf --output output/manual.json
```

The current CLI supports PDF to JSON only.

## Current Limitations

- Native-text PDFs only
- No OCR yet
- No advanced table extraction yet
- No formula recognition yet
