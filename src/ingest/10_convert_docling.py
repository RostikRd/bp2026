# src/ingest/10_convert_docling.py
import logging
import warnings
from pathlib import Path
from tqdm import tqdm

from docling.document_converter import DocumentConverter

# Придушення попереджень від RapidOCR та інших бібліотек
# RapidOCR може видавати багато попереджень, якщо не може розпізнати текст
# Це нормально для PDF файлів, які вже містять текст
logging.getLogger("RapidOCR").setLevel(logging.CRITICAL)
logging.getLogger("docling").setLevel(logging.WARNING)
logging.getLogger("docling.pipeline").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*RapidOCR.*")
warnings.filterwarnings("ignore", message=".*empty result.*")

try:
    from docling.datamodel.exporters import MarkdownExporter  
    HAS_EXPORTER = True
except Exception:
    MarkdownExporter = None
    HAS_EXPORTER = False

RAW = Path("data_raw")
OUT = Path("data_processed/md")
OUT.mkdir(parents=True, exist_ok=True)

# Створюємо конвертер
# Docling спочатку спробує витягнути текст з PDF без OCR
# OCR використовується тільки якщо текст не знайдено
# Попередження про порожні результати OCR - це нормально для PDF з текстом
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


success_count = 0
error_count = 0
skipped_count = 0

for inp in tqdm(candidates, desc="Docling convert"):
    try:
        rel = inp.relative_to(RAW)
        outp = (OUT / rel).with_suffix(".md")
        outp.parent.mkdir(parents=True, exist_ok=True)
        
        # Перевірка чи файл вже існує
        if outp.exists() and outp.stat().st_size > 100:
            skipped_count += 1
            continue

        # Conversion with error handling
        try:
            conv_result = converter.convert(inp)
            md_text = to_markdown(conv_result)
        except KeyboardInterrupt:
            print(f"\n⚠ Interrupted by user. Processed {success_count} files.")
            raise
        except Exception as conv_error:
            error_count += 1
            print(f"\n⚠ Conversion error for {inp.name}: {conv_error}")
            continue

        if md_text and md_text.strip():
            outp.write_text(md_text, encoding="utf-8")
            success_count += 1
        else:
            error_count += 1
            print(f"\n⚠ Empty markdown for {inp.name}")
    except KeyboardInterrupt:
        print(f"\n⚠ Interrupted by user. Processed {success_count} files.")
        break
    except Exception as e:
        error_count += 1
        print(f"\n⚠ Processing error for {inp.name}: {e}")

print(f"\n✓ Conversion completed:")
print(f"  Success: {success_count}")
print(f"  Errors: {error_count}")
print(f"  Skipped: {skipped_count}")
print(f"✓ Markdown saved to {OUT}")
