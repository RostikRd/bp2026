import argparse
import logging
import re
import warnings
import os
import sys
from pathlib import Path
from html.parser import HTMLParser
from tqdm import tqdm
from contextlib import contextmanager

logging.basicConfig(level=logging.ERROR, format='%(message)s')
logging.getLogger("RapidOCR").setLevel(logging.CRITICAL)
logging.getLogger("rapidocr").setLevel(logging.CRITICAL)
logging.getLogger("docling").setLevel(logging.ERROR)
logging.getLogger("docling.pipeline").setLevel(logging.CRITICAL)
logging.getLogger("docling.pipeline.pipeline").setLevel(logging.CRITICAL)

warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

# Context manager that temporarily redirects stdout and stderr to devnull (e.g. to silence Docling/OCR output).
@contextmanager
def suppress_output():
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stdout = devnull
            sys.stderr = devnull
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

try:
    from docling.datamodel.exporters import MarkdownExporter  
    HAS_EXPORTER = True
except Exception:
    MarkdownExporter = None
    HAS_EXPORTER = False

from docling.document_converter import DocumentConverter

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
if not (_PROJECT_ROOT / "data_raw").exists():
    _PROJECT_ROOT = Path(os.getcwd())
    for _ in range(5):
        if (_PROJECT_ROOT / "data_raw").exists():
            break
        _PROJECT_ROOT = _PROJECT_ROOT.parent

RAW = _PROJECT_ROOT / "data_raw"
OUT = _PROJECT_ROOT / "data_processed" / "md"
OUT.mkdir(parents=True, exist_ok=True)

converter = DocumentConverter()

md_exporter = MarkdownExporter() if HAS_EXPORTER else None

candidates = [p for p in RAW.rglob("*") if p.suffix.lower() in {".html", ".htm", ".pdf"}]
candidates = [p for p in candidates if "_ignore" not in p.parts]
candidates = [p for p in candidates if p.name != "31224.4fca50.pdf"]

# Converts a Docling conversion result to a markdown string (uses exporter or document methods).
def to_markdown(conv_result):
    if HAS_EXPORTER and hasattr(conv_result, "document") and md_exporter is not None:
        return md_exporter.export(conv_result.document)

    if hasattr(conv_result, "export_markdown"):
        return conv_result.export_markdown()

    doc = getattr(conv_result, "document", None)
    if doc is not None and hasattr(doc, "export_markdown"):
        return doc.export_markdown()
    return None


# HTML parser that extracts plain text from body content, ignoring script/style and preserving paragraph breaks.
class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.in_script = tag == "script"
            self.in_style = tag == "style"
        elif tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "li", "tr"):
            self.text_parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.in_script = self.in_style = False
        elif tag in ("p", "div", "h1", "h2", "h3", "h4", "li", "tr"):
            self.text_parts.append("\n")

    def handle_data(self, data):
        if not self.in_script and not self.in_style:
            s = data.strip()
            if s:
                self.text_parts.append(s)
                self.text_parts.append(" ")

    def get_text(self):
        text = "".join(self.text_parts)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()


# Fallback: extracts title and body text from an HTML file and returns a simple markdown string when Docling yields empty.
def html_to_markdown_fallback(html_path: Path) -> str:
    try:
        raw = html_path.read_text(encoding="utf-8", errors="replace")
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", raw, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else html_path.stem
        body_match = re.search(r"<body[^>]*>(.*?)</body>", raw, re.IGNORECASE | re.DOTALL)
        body_html = body_match.group(1) if body_match else raw
        parser = _HTMLTextExtractor()
        parser.feed(body_html)
        body_text = parser.get_text()
        if not body_text:
            body_text = re.sub(r"<[^>]+>", " ", body_html)
            body_text = re.sub(r"\s+", " ", body_text).strip()
        if not body_text:
            return ""
        return f"# {title}\n\n{body_text}"
    except Exception:
        return ""


# Main CLI: converts all HTML/PDF candidates under data_raw to markdown under data_processed/md (with optional --force).
def main():
    parser = argparse.ArgumentParser(description="Convert HTML/PDF to Markdown (Docling + fallbacks)")
    parser.add_argument("--force", action="store_true", help="Reconvert all files (do not skip existing)")
    args = parser.parse_args()
    force = args.force

    success_count = 0
    error_count = 0
    skipped_count = 0

    for inp in tqdm(candidates, desc="Docling convert"):
        try:
            rel = inp.relative_to(RAW)
            outp = (OUT / rel).with_suffix(".md")
            outp.parent.mkdir(parents=True, exist_ok=True)

            if not force and outp.exists() and outp.stat().st_size > 100:
                skipped_count += 1
                continue

            try:
                if inp.suffix.lower() == ".pdf":
                    conv_result = converter.convert(inp)
                else:
                    with suppress_output():
                        conv_result = converter.convert(inp)
                md_text = to_markdown(conv_result)
            except KeyboardInterrupt:
                raise
            except Exception as conv_error:
                error_count += 1
                continue

            if md_text and md_text.strip():
                outp.write_text(md_text, encoding="utf-8")
                success_count += 1
            else:
                if inp.suffix.lower() in (".html", ".htm"):
                    md_text = html_to_markdown_fallback(inp)
                    if md_text and len(md_text.strip()) > 100:
                        outp.write_text(md_text, encoding="utf-8")
                        success_count += 1
                    else:
                        error_count += 1
                else:
                    error_count += 1
        except KeyboardInterrupt:
            break
        except Exception as e:
            error_count += 1


if __name__ == "__main__":
    main()
    try:
        sys.exit(0)
    except SystemExit:
        pass
