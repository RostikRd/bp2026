# Normalize Markdown files to JSON for RAG system
import re, json, hashlib, os
from pathlib import Path

MD_DIR = Path("data_processed/md")
OUT_DIR = Path("data_processed/json")
OUT_DIR.mkdir(parents=True, exist_ok=True)

URLS_FILE = Path("urls.txt")

def load_url_map():
    """Load URL mapping from file"""
    m = {}
    if URLS_FILE.exists():
        for ln in URLS_FILE.read_text(encoding="utf-8").splitlines():
            u = ln.strip()
            if not u or u.startswith("#"):
                continue
            base = Path(u.split("?",1)[0]).name or "index.html"
            m[base] = u
    return m

URL_MAP = load_url_map()

def clean_text(text: str) -> str:
    """Clean text from garbage and extra characters"""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[^\w\s\.,!?;:\-\(\)\[\]\"\'áčďéíľĺňóôŕšťúýžÁČĎÉÍĽĹŇÓÔŔŠŤÚÝŽ]', '', text)
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()

def extract_title_and_sections(md_text: str):
    """Extract title and sections from Markdown"""
    lines = md_text.splitlines()
    title = ""
    sections = []
    cur = {"heading": "Obsah", "text": []}
    
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
            
        if ln.startswith("# "):
            title = clean_text(ln[2:])
            continue
        if ln.startswith("## "):
            if cur["text"]:
                text_content = clean_text("\n".join(cur["text"]))
                if text_content and len(text_content) > 20:
                    sections.append({**cur, "text": text_content})
            cur = {"heading": clean_text(ln[3:]), "text": []}
        else:
            if len(ln) > 5 and not re.match(r'^[^\w]*$', ln):
                cur["text"].append(ln)
    
    if cur["text"]:
        text_content = clean_text("\n".join(cur["text"]))
        if text_content and len(text_content) > 20:
            sections.append({**cur, "text": text_content})
    
    return title or "Bez názvu", sections

def infer_levels(md_text: str):
    """Determine support levels from text"""
    patterns = [
        r"[Uu]roveň\s*(?:podpory)?\s*(\d)",
        r"úroveň\s*(\d)",
        r"level\s*(\d)",
        r"PO\s*(\d)",
        r"podporné\s+opatrenie\s*(\d)",
        r"1\.(\d)",  # 1.1, 1.2, 1.3 - витягне 1, 2, 3
    ]
    
    levels = set()
    for pattern in patterns:
        matches = re.findall(pattern, md_text, re.IGNORECASE)
        for match in matches:
            try:
                level = int(match)
                if 1 <= level <= 3:
                    levels.add(level)
            except ValueError:
                continue

    text_lower = md_text.lower()

    has_all_levels = (
        ('1.1' in text_lower or 'všeobecné podporné opatrenia' in text_lower) and
        ('1.2' in text_lower or 'cielené podporné opatrenia' in text_lower) and
        ('1.3' in text_lower or 'špecifické podporné opatrenia' in text_lower)
    )
    
    if has_all_levels:
        levels.add(1)
        levels.add(2)
        levels.add(3)
    
    if not levels:
        # Рівень 1 - všeobecné/základné/univerzálne
        if any(word in text_lower for word in ['všeobecné', 'základné', 'univerzálne']):
            levels.add(1)
        # Rівень 2 - cielené (ale не špecializované)
        if any(word in text_lower for word in ['cielené', 'cieľové']) and 'špecializované' not in text_lower:
            levels.add(2)
        # Rівень 3 - špecifické podporné opatrenia / špecializované
        if any(phrase in text_lower for phrase in ['špecifické podporné opatrenia', 'špecializované', 'špeciálne']):
            levels.add(3)
        # Якщо є "individuálne" але без інших маркерів - може бути рівень 2 або 3
        if 'individuálne' in text_lower and not levels:
            levels.add(2) 
    
    return sorted(levels) if levels else [1]

def guess_url_hint(md_path: Path):
    """Determine URL based on file path"""
    parts = md_path.parts
    if "podporneopatrenia.minedu.sk" in parts:
        i = parts.index("podporneopatrenia.minedu.sk")
        tail = "/".join(parts[i+1:])
        return "https://podporneopatrenia.minedu.sk/" + tail.replace(".md",".html")
    
    name = md_path.name[:-3] if md_path.name.endswith(".md") else md_path.name
    if name in URL_MAP:
        return URL_MAP[name]
    return ""

# Process all Markdown files
items = []
for p in MD_DIR.rglob("*.md"):
    md = p.read_text(encoding="utf-8", errors="ignore")
    if not md.strip():
        continue
    
    if len(md.strip()) < 100:
        continue
    
    if not any(word in md.lower() for word in ['podporné', 'opatrenie', 'žiak', 'dieťa', 'škola', 'vzdelávanie']):
        continue
    
    title, sections = extract_title_and_sections(md)
    
    # Špeciálna úprava pre katalog.md
    if "katalog.md" in p.as_posix() or p.name == "katalog.md":
        title = "Katalóg podporných opatrení. 2. vydanie. Bratislava: Národný inštitút vzdelávania a mládeže, 2024. Schválené Ministerstvom školstva, výskumu, vývoja a mládeže Slovenskej republiky pod číslom 2024/17370:1‑E1660, s platnosťou od 1. septembra 2024."
    
    if len(sections) < 1:
        continue
    
    url_hint = guess_url_hint(p)

    items.append({
        "id": hashlib.md5(p.as_posix().encode()).hexdigest()[:12],
        "source_file": p.as_posix(),
        "title": title,
        "levels": infer_levels(md),
        "sections": sections,
        "url_hint": url_hint
    })

# Save result
outp = OUT_DIR / "catalog.jsonl"
outp.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in items), encoding="utf-8")
print(f"✓ Normalized {len(items)} documents → {outp}")
missing = sum(1 for x in items if not x["url_hint"])
print(f"⚠ Missing URL for {missing} docs")
