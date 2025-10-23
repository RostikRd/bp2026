# src/ingest/10_convert_docling.py
from pathlib import Path
from tqdm import tqdm

from docling.document_converter import DocumentConverter

# Спроба імпорту нового експортера (Docling 2.x).
# Якщо немає — працюватимемо через старий метод export_markdown().
try:
    from docling.datamodel.exporters import MarkdownExporter  # Docling >= 2.0
    HAS_EXPORTER = True
except Exception:
    MarkdownExporter = None
    HAS_EXPORTER = False

RAW = Path("data_raw")
OUT = Path("data_processed/md")
OUT.mkdir(parents=True, exist_ok=True)

converter = DocumentConverter()
md_exporter = MarkdownExporter() if HAS_EXPORTER else None

candidates = [p for p in RAW.rglob("*") if p.suffix.lower() in {".html", ".htm"}]  # PDF вимкнено
print("Files to convert:", len(candidates))

def to_markdown(conv_result):
    """
    Повертає markdown з урахуванням версії Docling.
    - Docling 2.x: conv_result.document + MarkdownExporter
    - Docling 1.x: conv_result.export_markdown()
    """
    # Новий шлях (2.x)
    if HAS_EXPORTER and hasattr(conv_result, "document") and md_exporter is not None:
        return md_exporter.export(conv_result.document)

    # Старий шлях (1.x)
    if hasattr(conv_result, "export_markdown"):
        return conv_result.export_markdown()

    # Іноді у 1.x markdown доступний як метод у .document
    doc = getattr(conv_result, "document", None)
    if doc is not None and hasattr(doc, "export_markdown"):
        return doc.export_markdown()

    raise RuntimeError(
        "Docling: не знайдено способу експорту в Markdown. "
        "Онови пакет (рекомендовано: pip install -U 'docling>=2.1.0')."
    )

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
