import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("bp2026")

# Suppress noisy loggers during conversion
for _name in ("RapidOCR", "rapidocr", "docling", "docling.pipeline", "docling.pipeline.pipeline"):
    try:
        logging.getLogger(_name).setLevel(logging.CRITICAL)
    except Exception:
        pass

try:
    from docling.document_converter import DocumentConverter
    HAS_DOCLING = True
except Exception:
    DocumentConverter = None
    HAS_DOCLING = False

try:
    from docling.datamodel.exporters import MarkdownExporter
    HAS_EXPORTER = True
except Exception:
    MarkdownExporter = None
    HAS_EXPORTER = False


# Converts a Docling conversion result to a Markdown string.
def _to_markdown(conv_result) -> str | None:
    if conv_result is None:
        return None
    if HAS_EXPORTER and hasattr(conv_result, "document") and MarkdownExporter is not None:
        try:
            return MarkdownExporter().export(conv_result.document)
        except Exception:
            pass
    if hasattr(conv_result, "export_markdown"):
        try:
            return conv_result.export_markdown()
        except Exception:
            pass
    doc = getattr(conv_result, "document", None)
    if doc is not None and hasattr(doc, "export_to_markdown"):
        try:
            return doc.export_to_markdown()
        except Exception:
            pass
    if doc is not None and hasattr(doc, "export_markdown"):
        try:
            return doc.export_markdown()
        except Exception:
            pass
    return None


# Extracts text from a PDF or image file using Docling OCR and returns it as a string.
def extract_text_with_docling(file_path: str | Path, mime_type: str) -> str:
    if not HAS_DOCLING or DocumentConverter is None:
        raise RuntimeError("Docling is not available. Install docling.")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Docling accepts path or path string; it supports PDF and images (OCR)
    converter = DocumentConverter()
    try:
        result = converter.convert(str(path))
    except Exception as e:
        logger.exception("Docling convert failed for %s: %s", path, e)
        raise

    text = _to_markdown(result)
    if not text or not text.strip():
        raise ValueError("Docling produced empty text")
    return text.strip()
