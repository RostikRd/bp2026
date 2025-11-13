# src/ingest/10_convert_docling.py
from pathlib import Path
from tqdm import tqdm

from docling.document_converter import DocumentConverter

try:
    from docling.datamodel.exporters import MarkdownExporter  
    HAS_EXPORTER = True
except Exception:
    MarkdownExporter = None
    HAS_EXPORTER = False

RAW = Path("data_raw")
OUT = Path("data_processed/md")
OUT.mkdir(parents=True, exist_ok=True)

converter = DocumentConverter()
md_exporter = MarkdownExporter() if HAS_EXPORTER else None

candidates = [p for p in RAW.rglob("*") if p.suffix.lower() in {".html", ".htm", ".pdf"}]

candidates = [p for p in candidates if "_ignore" not in p.parts]
print("Files to convert:", len(candidates))

def to_markdown(conv_result):
    if HAS_EXPORTER and hasattr(conv_result, "document") and md_exporter is not None:
        return md_exporter.export(conv_result.document)

    if hasattr(conv_result, "export_markdown"):
        return conv_result.export_markdown()

    doc = getattr(conv_result, "document", None)
    if doc is not None and hasattr(doc, "export_markdown"):
        return doc.export_markdown()


for inp in tqdm(candidates, desc="Docling convert"):
    try:
        rel = inp.relative_to(RAW)
        outp = (OUT / rel).with_suffix(".md")
        outp.parent.mkdir(parents=True, exist_ok=True)

        conv_result = converter.convert(inp)
        md_text = to_markdown(conv_result)

        if md_text and md_text.strip():
            outp.write_text(md_text, encoding="utf-8")
        else:
            print("WARN: empty markdown for", inp)
    except Exception as e:
        print("WARN:", inp, e)

print("✓ Markdown saved to", OUT)
