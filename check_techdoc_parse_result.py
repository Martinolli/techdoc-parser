from techdoc_parser import parse_document
from techdoc_parser.exporters import export_document_json, export_document_markdown

document = parse_document("MIL-STD-882E.pdf")
export_document_json(document, "output/mil-std-882e.json")
export_document_markdown(document, "output/mil-std-882e.md")

heading_count = sum(
    1
    for page in document.pages
    for block in page.blocks
    if block.block_type == "heading"
)

text_count = sum(len(page.text_blocks) for page in document.pages)

print("Pages:", len(document.pages))
print("Text blocks:", text_count)
print("Heading blocks:", heading_count)

for page in document.pages[:30]:
    print(f"\nPAGE {page.page_number}")
    for block in page.blocks:
        if block.block_type == "heading":
            print(
                f"  H{getattr(block, 'level', '?')}: "
                f"{block.normalized_text or block.text}"
            )
