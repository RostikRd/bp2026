import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
if not (_PROJECT_ROOT / "rag_index").exists():
    _PROJECT_ROOT = Path(os.getcwd())
    for _ in range(5):
        if (_PROJECT_ROOT / "rag_index").exists():
            break
        _PROJECT_ROOT = _PROJECT_ROOT.parent

# Loads API keys from api_keys.env into os.environ (for local runs).
def load_api_keys():
    env_file = _PROJECT_ROOT / "api_keys.env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                try:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
                except ValueError:
                    continue

# Returns hostname (site name) from URL for display, e.g. "www.minedu.sk" -> "minedu.sk".
def url_to_site_name(url: str) -> str:
    if not url or not url.strip():
        return url
    try:
        netloc = urlparse(url.strip()).netloc
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc or url.strip()
    except Exception:
        return url.strip()


# Returns short 2-word description of page content from title, or from URL path if title empty.
def strip_trailing_source_sections(text: str) -> str:
    """Odstráni z textu odpovede modelu sekcie Zdroje/Overenie, ktoré systém doplní sám – aby sa nezdvojovali."""
    if not text or not text.strip():
        return text
    for marker in ("\n## Zdroje", "\n## Overenie", "\n## 📚 Zdroje"):
        idx = text.find(marker)
        if idx != -1:
            return text[:idx].rstrip()
    return text


# Počet webových zdrojov: zobrazovať a používať 4–6; v texte cituj 3–6.
WEB_SOURCES_MIN = 4
WEB_SOURCES_MAX = 6


def _normalize_web_url(url: str) -> str:
    """Normalizuje URL na porovnanie (odstráni trailing slash, zjednotí)."""
    if not url or not url.strip():
        return ""
    u = url.strip()
    if u.endswith("/"):
        u = u[:-1]
    return u.lower()


def dedupe_web_sources_by_url(sources: list, by_domain: bool = True) -> list:
    """Odstráni duplicitné webové zdroje: podľa URL, alebo (ak by_domain) podľa domény – ponechá prvý výskyt každého URL/domény."""
    if not sources:
        return []
    seen = set()
    out = []
    for s in sources:
        url = (s.get("url") if isinstance(s, dict) else getattr(s, "url", "")) or ""
        if not url.strip():
            continue
        if by_domain:
            try:
                key = urlparse(url.strip()).netloc.lower()
                if key.startswith("www."):
                    key = key[4:]
            except Exception:
                key = _normalize_web_url(url)
        else:
            key = _normalize_web_url(url)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def limit_web_sources(sources: list, min_sources: int = None, max_sources: int = None) -> list:
    """Obmedzí zoznam webových zdrojov na 4–6 (alebo min_sources–max_sources). Používa sa pre Zdroje (internet) aj Overenie v internete."""
    min_sources = min_sources if min_sources is not None else WEB_SOURCES_MIN
    max_sources = max_sources if max_sources is not None else WEB_SOURCES_MAX
    if not sources:
        return []
    n = min(max_sources, len(sources))
    return sources[:n]


def short_description_from_title_and_url(title: str, url: str, max_words: int = 2) -> str:
    words = (title or "").strip().split()
    if len(words) >= max_words:
        return " ".join(words[:max_words])
    if len(words) == 1 and max_words > 1:
        return words[0]
    if words:
        return " ".join(words)
    try:
        path = urlparse((url or "").strip()).path.strip("/")
        if path:
            segment = path.split("/")[-1]
            segment = segment.replace(".pdf", "").replace(".html", "").replace("-", " ").replace("_", " ")[:40]
            seg_words = segment.split()[:max_words]
            if seg_words:
                return " ".join(seg_words)
    except Exception:
        pass
    return url_to_site_name(url)

# Strips trailing .html or .html/ from a URL string.
def clean_url(url: str) -> str:
    if not url:
        return url
    if url.endswith(".html/"):
        url = url[:-6]
    elif url.endswith(".html"):
        url = url[:-5]
    return url

# Loads URL mapping from urls.txt (path keys -> canonical URLs) and applies clean_url.
def load_url_mapping():
    urls_file = _PROJECT_ROOT / "urls.txt"
    url_map = {}
    if urls_file.exists():
        for line in urls_file.read_text(encoding="utf-8").splitlines():
            url = line.strip()
            if not url or url.startswith("#"):
                continue
            url = clean_url(url)
            url_key = url.rstrip("/").split("/")[-1]
            if url_key and url_key not in url_map:
                url_map[url_key] = url
            if "podporneopatrenia.minedu.sk/" in url:
                path_part = url.split("podporneopatrenia.minedu.sk/", 1)[1].rstrip("/")
                if path_part:
                    url_map[path_part] = url
                    if path_part.endswith("/"):
                        url_map[path_part[:-1]] = url
    return url_map

URL_MAP = load_url_mapping()

# Resolves document metadata (url, source_file) to a canonical URL using URL_MAP and path heuristics.
def resolve_url(doc_meta: dict) -> str:
    existing_url = doc_meta.get("url", "").strip()
    if existing_url and existing_url.startswith("https://"):
        existing_url = existing_url.replace("/index.html", "").replace("/index.htm", "")
        existing_url = clean_url(existing_url)
        if not existing_url.endswith("/") and "podporneopatrenia.minedu.sk" in existing_url:
            existing_url += "/"
        return existing_url
    
    source_file = doc_meta.get("source_file", "")
    if not source_file:
        return existing_url
    
    source_path = Path(source_file)
    parts = list(source_path.parts)
    
    if "podporneopatrenia.minedu.sk" in parts:
        idx = parts.index("podporneopatrenia.minedu.sk")
        tail_parts = parts[idx + 1:]
        clean_parts = []
        for part in tail_parts:
            cleaned = part.replace(".md", "").replace(".html", "")
            if cleaned and cleaned != "index":
                clean_parts.append(cleaned)
        
        path_key = "/".join(clean_parts)
        if path_key in URL_MAP:
            return clean_url(URL_MAP[path_key])
        
        if clean_parts:
            first_part = clean_parts[0]
            if first_part in URL_MAP:
                return clean_url(URL_MAP[first_part])
    
    file_name = source_path.name.replace(".md", "").replace(".html", "")
    if file_name and file_name != "index":
        if file_name in URL_MAP:
            return clean_url(URL_MAP[file_name])
    
    for part in reversed(parts):
        part_clean = part.replace(".md", "").replace(".html", "")
        if part_clean and part_clean != "index":
            if part_clean in URL_MAP:
                return clean_url(URL_MAP[part_clean])
    
    if "podporneopatrenia.minedu.sk" in parts:
        idx = parts.index("podporneopatrenia.minedu.sk")
        tail_parts = parts[idx + 1:]
        clean_parts = [p.replace(".md", "").replace(".html", "") for p in tail_parts if p.replace(".md", "").replace(".html", "") != "index"]
        if clean_parts:
            constructed_path = "/".join(clean_parts)
            if constructed_path in URL_MAP:
                return clean_url(URL_MAP[constructed_path])
            constructed = f"https://podporneopatrenia.minedu.sk/{constructed_path}/"
            for url in URL_MAP.values():
                if constructed_path in url:
                    return clean_url(url)
            return clean_url(constructed)
    
    return existing_url

load_api_keys()

PERSIST = str(_PROJECT_ROOT / "rag_index" / "faiss_e5")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-small")

_embedder = None
_vs = None

# Lazy-loads and returns the FAISS vector store (and embeddings) from PERSIST.
def get_vectorstore():
    global _embedder, _vs
    if _vs is None:
        if not Path(PERSIST).exists():
            raise FileNotFoundError(
                f"RAG index neexistuje: {PERSIST}\n"
                "Najprv zostavte index z koreňa projektu: bash scripts/bootstrap.sh\n"
                "Alebo: python src/ingest/10_convert_docling.py && python src/ingest/20_normalize_json.py && python src/rag/build_index_e5.py"
            )
        if _embedder is None:
            _embedder = HuggingFaceEmbeddings(
                model_name=EMBED_MODEL,
                encode_kwargs={"normalize_embeddings": True},
            )
        _vs = FAISS.load_local(PERSIST, embeddings=_embedder, allow_dangerous_deserialization=True)
    return _vs

# Returns True if document metadata has support level 1, 2 or 3 (or no level).
def level_ok(meta: dict) -> bool:
    lv = (meta or {}).get("levels", "")
    if not lv:
        return True
    return any(x in lv for x in ["1", "2", "3"])

# Collapses whitespace in text to single spaces and strips leading/trailing.
def compact(txt: str) -> str:
    return re.sub(r"\s+", " ", txt).strip()

# Raises RuntimeError with the given message (used when AI or API fails).
def show_error_with_context(error_msg, docs_list):
    raise RuntimeError(error_msg)

MAX_L2_DISTANCE = 0.92
TOP_DOCS_MAX = 12
# FAISS "má odpoveď" len ak aspoň toľko relevantných chunkov a najlepší score nie je horší než threshold.
FAISS_MIN_CHUNKS = 2
FAISS_MAX_BEST_L2 = 0.90
# When agent decides to use web search (NEED_WEB_SEARCH). Claude built-in web_search_20250305 only.
WEB_SEARCH_MAX_USES = int(os.environ.get("WEB_SEARCH_MAX_USES", "3"))
# Models that support Claude web_search_20250305 (use first available when need_second_call).
CLAUDE_WEB_SEARCH_MODELS = [
    "claude-sonnet-4-5-20250929",
    "claude-sonnet-4-5",
    "claude-sonnet-4-20250514",
    "claude-sonnet-4",
    "claude-3-5-haiku-20241022",
]
NEED_WEB_MARKER = "NEED_WEB_SEARCH"


def _strip_need_web_from_answer(text: str) -> str:
    """Remove any trailing NEED_WEB_SEARCH line and the following line (search query) from answer text."""
    if not text or NEED_WEB_MARKER not in text:
        return text
    idx = text.rfind(NEED_WEB_MARKER)
    if idx == -1:
        return text
    return text[:idx].rstrip()


def _call_claude_with_web_search(system_prompt: str, user_prompt: str, model: str, api_key: str):
    """Call Anthropic Messages API with web_search_20250305 tool. Returns (answer_text, web_sources_list)."""
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": WEB_SEARCH_MAX_USES}],
    )
    text_parts = []
    web_sources = []
    for block in getattr(resp, "content", []) or []:
        block_type = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
        if block_type == "text":
            t = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else "")
            if t:
                text_parts.append(t)
        elif block_type == "web_search_tool_result":
            content = getattr(block, "content", None) or (block.get("content") if isinstance(block, dict) else None)
            if not isinstance(content, list):
                continue
            for item in content:
                itype = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
                if itype != "web_search_result":
                    continue
                url = item.get("url", "") if isinstance(item, dict) else getattr(item, "url", "")
                title = (item.get("title") or url) if isinstance(item, dict) else (getattr(item, "title", None) or url)
                if url:
                    web_sources.append({"title": title or url, "url": url})
    answer_text = "\n".join(text_parts).strip() if text_parts else ""
    return answer_text, web_sources

OFF_TOPIC_MESSAGE = (
    "Otázka nesúvisí so špeciálnym vzdelávaním ani s podpornými opatreniami. "
    "Odpovedám výhradne na témy z oblasti špeciálnej pedagogiky, podporných opatrení a súvisiacich otázok."
)

# Returns True if the query asks for contacts, addresses, phone numbers, or similar lookup info (answer should come from web only).
def is_contact_or_lookup_query(query: str) -> bool:
    q = query.lower().strip()
    terms = (
        "kontakt", "kontakty", "telefón", "telefónne", "e-mail", "email", "adresa", "sídlo",
        "kde nájdem", "aký je kontakt", "ako kontaktovať", "číslo na ", "kontakt na ",
        "štátny pedagogický ústav", "špú", "núvam", "nivam", "núcem", "nucem",
    )
    return any(t in q for t in terms)


# Returns True if the query appears to be about special education, supportive measures, or related institutions.
def is_query_about_special_education(query: str) -> bool:
    q = query.lower().strip()
    if len(q) < 3:
        return False
    topic_terms = (
        "podporn", "špeciál", "vzdeláv", "žiak", "žiakov", "žiaka", "škola", "školsk",
        "inklúz", "inkluz", "katalóg", "vyhláška", "mšvv", "ministerstvo školstva",
        "nivam", "špi", "pedagogick", "poradenstvo", "asistent", "pedagóg",
        "adhd", "autizmus", "asd", "dyslex", "dysgraf", "potreby žiaka",
        "podporných opatrení", "špeciálne vzdelávanie", "špeciálna pedagogika",
        "výchovno-vzdelávacie", "zpp", "úroveň podpory", "individualiz", "čítanie s porozumením", 
        "pravopis", "pravopisné chyby", "čítanie textu", "porozumenie textu", "jazykové vzdelávanie",
        "jazyková výučba", "hodnotenie", "úpravy hodnotenia", "hodnotenie výsledkov", "písomka", "test", "skúška",
        "hypersenzitivita", "hluk", "citlivý", "citlivá", "úpravy priestoru", "prostredie", "senzorické prestávky",
        "priestor", "prostredie", "triedne pravidlá", "organizácia priestoru", "trieda", "absencia", "reintegrácia", "návrat do školy",
        "komunikácia s rodičmi", "rodičia", "domáce úlohy", "domáce čítanie", "rutiny pre rodičov", "písanie", "tempo písania",
        "dysgrafia", "písomný prejav", "grafomotorika", "ASD", "autizmus", "autistický", "zmeny režimu", "vizuálne rozvrhy", "vizuálne pomôcky",
        "prechodové rituály", "struktúra", "režim", "OSŽ", "odlišný slovenčina jazyk", "slovenčina ako druhý jazyk", "jazyková podpora",
        "prírodoveda", "prírodopis", "prírodovedné predmety", "porozumenie textu", "čítanie s porozumením", "práca s textom", "kroky", "postup", "realizácia", "praktické riešenia",
        "skúšky","hypersenzitivita", "hluk", "citlivý", "citlivá", "úpravy priestoru", "prostredie", "senzorické prestávky", "priestor", "prostredie", "triedne pravidlá", "organizácia priestoru", "trieda", "absencia", "reintegrácia", "návrat do školy",
        "komunikácia s rodičmi", "rodičia", "domáce úlohy", "domáce čítanie", "rutiny pre rodičov", "písanie", "tempo písania", "dysgrafia", "písomný prejav", "grafomotorika", "ASD", "autizmus", "autistický", "zmeny režimu", "vizuálne rozvrhy", "vizuálne pomôcky",
        "prechodové rituály", "struktúra", "režim", "OSŽ", "odlišný slovenčina jazyk", "slovenčina ako druhý jazyk", "jazyková podpora", "prírodoveda", "prírodopis", "prírodovedné predmety", "porozumenie textu", "čítanie s porozumením", "práca s textom", "kroky", "postup", "realizácia", "praktické riešenia",
        "skúška", "test", "písomka", "úlohy", "matematika", "matematické", "počítanie", "úlohy", "matematické úlohy", "hodnotenie", "úpravy hodnotenia", "hodnotenie výsledkov", "písomka", "test", "skúška",
        "hypersenzitivita", "hluk", "citlivý", "citlivá", "úpravy priestoru", "prostredie", "senzorické prestávky", "priestor", "prostredie", "triedne pravidlá", "organizácia priestoru", "trieda", "absencia", "reintegrácia", "návrat do školy",
        "komunikácia s rodičmi", "rodičia", "domáce úlohy", "domáce čítanie", "rutiny pre rodičov", "písanie", "tempo písania", "dysgrafia", "písomný prejav", "grafomotorika", "ASD", "autizmus", "autistický", "zmeny režimu", "vizuálne rozvrhy", "vizuálne pomôcky",
        "prechodové rituály", "struktúra", "režim", "OSŽ", "odlišný slovenčina jazyk", "slovenčina ako druhý jazyk", "jazyková podpora", "prírodoveda", "prírodopis", "prírodovedné predmety", "porozumenie textu", "čítanie s porozumením", "práca s textom", "kroky", "postup", "realizácia", "praktické riešenia",
    )
    return any(term in q for term in topic_terms)

# Main RAG entry: retrieves relevant docs, builds context, calls Anthropic (Claude), appends sources section and returns full answer.
def ask(query: str) -> str:
    if not is_query_about_special_education(query):
        return OFF_TOPIC_MESSAGE

    vs = get_vectorstore()

   
    docs_with_scores = vs.similarity_search_with_score(query, k=25)
    doc_to_score = {}
    for doc, score in docs_with_scores:
        doc_id = doc.metadata.get("source_file", "") + str(doc.page_content[:100])
        if doc_id not in doc_to_score or score < doc_to_score[doc_id]:
            doc_to_score[doc_id] = (score, doc)

    docs_all = []
    for doc_id, (score, doc) in doc_to_score.items():
        docs_all.append((doc, score))

    keywords = []
    query_lower = query.lower()
    
    if "adhd" in query_lower or "pozornosť" in query_lower or "sústredenie" in query_lower:
        keywords.extend(["pozornosť", "sústredenie", "ADHD", "organizácia", "čas", "časové signály", "časový", "časové"])
    
    if "matematika" in query_lower or "matematické" in query_lower:
        keywords.extend(["matematika", "matematické", "počítanie", "úlohy", "matematické úlohy"])
    
    if "hodina" in query_lower or "organizácia" in query_lower:
        keywords.extend(["hodina", "vyučovanie", "organizácia", "časové", "organizácia hodiny", "časový plán"])
    
    if "číta" in query_lower or "čítanie" in query_lower or "pravopis" in query_lower or "pravopisné" in query_lower:
        keywords.extend(["čítanie", "čítanie s porozumením", "pravopis", "pravopisné chyby", "čítanie textu", "porozumenie textu"])
    
    if "sjl" in query_lower or "slovenský jazyk" in query_lower:
        keywords.extend(["slovenský jazyk", "SJL", "jazykové vzdelávanie", "jazyková výučba"])
    
    if "hodnotenie" in query_lower or "úpravy hodnotenia" in query_lower or "písomka" in query_lower:
        keywords.extend(["hodnotenie", "úpravy hodnotenia", "hodnotenie výsledkov", "písomka", "test", "skúška"])
    
    if "hypersenzitivita" in query_lower or "hluk" in query_lower or "citlivý" in query_lower or "citlivá" in query_lower:
        keywords.extend(["hypersenzitivita", "senzorické", "hluk", "úpravy priestoru", "prostredie", "senzorické prestávky"])
    
    if "priestor" in query_lower or "prostredie" in query_lower or "triedne pravidlá" in query_lower:
        keywords.extend(["úpravy priestoru", "prostredie", "triedne pravidlá", "organizácia priestoru", "trieda"])
    
    if "absencia" in query_lower or "reintegrácia" in query_lower or "návrat" in query_lower:
        keywords.extend(["absencia", "reintegrácia", "návrat do školy", "komunikácia s rodičmi", "rodičia"])
    
    if "rodič" in query_lower or "rodičia" in query_lower or "domáce" in query_lower:
        keywords.extend(["komunikácia s rodičmi", "rodičia", "domáce úlohy", "domáce čítanie", "rutiny pre rodičov"])
    
    if "písanie" in query_lower or "tempo písania" in query_lower or "dysgrafia" in query_lower:
        keywords.extend(["písanie", "tempo písania", "dysgrafia", "písomný prejav", "grafomotorika"])
    
    if "asd" in query_lower or "autizmus" in query_lower or "autistický" in query_lower:
        keywords.extend(["ASD", "autizmus", "autistický", "zmeny režimu", "vizuálne rozvrhy", "prechodové rituály", "senzorické prestávky"])
    
    if "vizuálne" in query_lower or "rozvrh" in query_lower or "rituály" in query_lower:
        keywords.extend(["vizuálne rozvrhy", "vizuálne pomôcky", "prechodové rituály", "struktúra", "režim"])
    
    if "osž" in query_lower or "odlišný sj" in query_lower or "odlišný slovenčina" in query_lower:
        keywords.extend(["OSŽ", "odlišný slovenčina jazyk", "slovenčina ako druhý jazyk", "jazyková podpora"])
    
    if "prírodoveda" in query_lower or "prírodopis" in query_lower:
        keywords.extend(["prírodoveda", "prírodopis", "prírodovedné predmety"])
    
    if "porozumenie" in query_lower or "text" in query_lower:
        keywords.extend(["porozumenie textu", "čítanie s porozumením", "práca s textom"])
    
    if "kroky" in query_lower or "zajtra" in query_lower or "quick" in query_lower:
        keywords.extend(["kroky", "postup", "realizácia", "praktické riešenia"])
    
    if "senzorické" in query_lower or "senzorický" in query_lower:
        keywords.extend(["senzorické", "senzorické prestávky", "senzorické potreby"])

    if "opatrenia" in query_lower or "opatrenie" in query_lower:
        keywords.extend(["opatrenia", "opatrenie", "opatrenia pre žiaka", "opatrenia pre učiteľa", "opatrenia pre rodičov"])

    if "podporné" in query_lower or "podpora" in query_lower:
        keywords.extend(["podporné opatrenia", "podpora", "podpora žiaka", "podpora učiteľa", "podpora rodičov"])
    
    for keyword in keywords[:5]:
        try:
            keyword_docs = vs.similarity_search(keyword, k=5)
            for doc in keyword_docs:
                doc_id = doc.metadata.get("source_file", "") + str(doc.page_content[:100])
                if doc_id not in doc_to_score:
                    doc_to_score[doc_id] = (1.0, doc)
                    docs_all.append((doc, 1.0))
        except Exception:
            continue

    seen_ids = set()
    unique_scored = []
    for doc, score in docs_all:
        doc_id = doc.metadata.get("source_file", "") + str(doc.page_content[:100])
        if doc_id not in seen_ids:
            seen_ids.add(doc_id)
            unique_scored.append((doc, score))

    unique_scored.sort(key=lambda x: x[1])
    docs_filtered = [(d, s) for d, s in unique_scored if level_ok(d.metadata) and s <= MAX_L2_DISTANCE]
    if not docs_filtered:
        docs_filtered = [(d, s) for d, s in unique_scored if level_ok(d.metadata)]
    docs_with_scores_final = docs_filtered[:TOP_DOCS_MAX] if docs_filtered else unique_scored[:TOP_DOCS_MAX]
    docs = [d for d, _ in docs_with_scores_final]
    best_l2 = docs_with_scores_final[0][1] if docs_with_scores_final else 1.0
    faiss_has_answer = len(docs_with_scores_final) >= FAISS_MIN_CHUNKS and best_l2 <= FAISS_MAX_BEST_L2

    context_blocks = []
    sources_info = []
    for i, d in enumerate(docs, 1):
        label = f"D{i}"
        title = d.metadata.get("title", "") or ""
        if title == "Kniha katalóg podporných opatrení":
            title = "Katalóg podporných opatrení (NÚVaV 2024)"
        if not title:
            title = d.metadata.get("source_file", "").split("/")[-1] or f"Dokument {i}"
        url = resolve_url(d.metadata)
        snippet = compact(d.page_content)[:1000]
        url_line = f"URL: {url}\n" if url else ""
        context_blocks.append(f"[{label}] {title}\n{url_line}---\n{snippet}")
        sources_info.append({"num": i, "label": label, "title": title, "url": url})
    
    if not sources_info:
        sources_info.append({"num": 1, "label": "D1", "title": "Katalóg podporných opatrení", "url": "https://podporneopatrenia.minedu.sk/katalog-podpornych-opatreni/"})

    context = "\n\n".join(context_blocks)

    # --- Režim: FAISS má odpoveď (answer + verify) alebo len internet (internet_only) ---
    # Ak FAISS má odpoveď: odpoveď z dokumentov, cituj len [D#], VŽDY web na overenie/doplnenie → na konci Zdroje (dokumenty) + Overenie v internete.
    # Ak FAISS nemá odpoveď alebo ide o kontakty/vyhľadávanie: odpoveď len z webu, cituj [W#] → na konci Zdroje (internet).
    need_web_only = not faiss_has_answer or is_contact_or_lookup_query(query)
    if faiss_has_answer:
        router_system = """Si asistent. Hľadáš odpoveď VÝLUČNE v poskytnutých dokumentoch z katalógu (číslované [D1], [D2], ...).

Ak v dokumentoch NÁJDEŠ dostatočnú odpoveď – napíš PLNÚ odpoveď v slovenčine s citáciami [D1], [D2], ... Nič iné.
Ak odpoveď v dokumentoch NENÁJDEŠ alebo je len čiastočná – NEPÍŠ že nemáš informácie. Namiesto toho napíš IBA dva riadky: prvý riadok presne NEED_WEB_SEARCH, druhý riadok jeden vyhľadávací dotaz v slovenčine. Systém potom vyhľadá na webe a ty odpovieš z webových zdrojov."""
        router_user = f"""Otázka: {query}

Dokumenty (kontext [D1], [D2], ...):
{context}

Odpoveď v dokumentoch? Ak áno – plná odpoveď s [D1], [D2]. Ak nie – NEED_WEB_SEARCH a dotaz."""

    system_prompt = """Si expertný asistent špeciálneho pedagóga na Slovensku s hlbokými znalosťami o podporných opatreniach a inkluzívnom vzdelávaní.

Tvoja úloha: Poskytovať konkrétne, praktické a realizovateľné riešenia na základe oficiálnych dokumentov.

KRÍTICKY DÔLEŽITÉ - VYSVETLITEĽNOSŤ A ODKAZY:
1. PRE KAŽDÉ OPATRENIE MUSÍŠ UVIESŤ "Prečo toto opatrenie:" s 2-3 vetami:
   - Akú konkrétnu potrebu žiaka rieši
   - Prečo je toto opatrenie vhodné pre danú situáciu
   - Odkaz na dokument [D1], [D2], … z ktorého opatrenie pochádza
2. PRI KAŽDEJ ČINNOSTI MUSÍŠ UVIESŤ ODKAZ na dokument: [D1], [D2], [D3] – nikdy [1], [2], [10], [11].
   - Ak z dokumentu D1, napíš [D1]; ak z D2 a D3, napíš [D2], [D3]
   - BEZ ODKAZOV [D#] NEPÍŠ ŽIADNE OPATRENIA
3. Vždy zdôvodni výber opatrenia – prečo práve toto, nie iné

ANALYTICKÝ PRÍSTUP:
1. Analyzuj problém v otázke a identifikuj kľúčové potreby žiaka.
2. Pre každú potrebu nájdi relevantné opatrenia v dokumentoch [1], [2], [3]...
3. Pre každé opatrenie vysvetli PREČO je vhodné (2-3 vety) a uveď odkaz [D1], [D2], …
4. Režim „odpoveď z dokumentov (FAISS)“: odpoveď zakladaj na dokumentoch, v texte cituj VÝHRADNE [D1], [D2], [D3]. Informáciu VŽDY over a dopĺňaj cez internet (systém ti dá webové výsledky), ale v texte NEPÍŠ [W1], [W2] – webové zdroje sa zobrazia na konci v sekcii „Overenie v internete“. Režim „odpoveď len z webu“: keď FAISS nemá odpoveď, odpovedaj z internetu a cituj [W1], [W2] pri každom fakte.

FORMÁT ODPOVEDE:
- Odpoveď štruktúruj JASNE: používaj LEN nadpisy ## (sekcia) a ### (podsekcia). Telo textu píš ako obyčajný text.
- Vizuálne zvýrazni LEN nadpisy (##, ###). Adresy, telefóny, e-maily, čísla píš ako bežný text – NEPOUŽÍVAJ ** (tučné) ani iné zvýraznenie pre kontaktné údaje ani pre odseky textu. Nadpis = ## alebo ###; zvyšok = normálny text.
- Príklad: napíš "Adresa: Ševčenkova 11, Bratislava [W1]." nie "**Adresa:** **Ševčenkova 11**". Telefón a e-mail tiež bez **.

## 🎯 Analýza problému
- Stručný popis identifikovaného problému
- Kľúčové potreby žiaka

## 📋 Konkrétne opatrenia

Pri každej aktivite/kroku uviesť [D1], [D2], … alebo [W1], [W2] – podľa režimu (dokumenty vs. len web). ZAKAZANÉ čísla typu [10], [11] bez D alebo W.

### [Názov opatrenia]
Realizácia: … s odkazom [D1] / [D2]. Prečo toto opatrenie: … [D#]. (Nadpisy sekcií môžu byť ### ; vnútorný text nie je tučný.)

PRAVIDLÁ:
- Dokumenty z katalógu cituj LEN ako [D1], [D2], [D3]. Webové zdroje cituj LEN ako [W1], [W2], [W3]. Nikdy [1], [2], [10], [11].
- Odpoveď z dokumentov (FAISS): v texte cituj VÝHRADNE [D#]. Web sa VŽDY používa na overenie/doplnenie, ale v texte sa [W#] neuvádza – na konci bude sekcia „Zdroje (dokumenty)“ a „Overenie v internete“ so zoznamom URL.
- Odpoveď len z webu (keď FAISS nenašiel): cituj 3 až 6 zdrojov [W1]–[W6] pri dôležitých faktoch; v zozname sa zobrazí 4–6 zdrojov.
- NEUVÁDZAJ zoznam zdrojov ani URL v texte – doplnia sa na konci. NEPÍŠ sekcie „## Zdroje (dokumenty)“ ani „## Overenie v internete“ ani „## Zdroje (internet)“ – systém ich doplní automaticky.
- Štruktúra a vzhľad: zvýraznené sú LEN nadpisy (##, ###). Adresy, telefóny, e-maily a bežné odseky píš bez ** (bez tučného). Cieľ: čitateľná štruktúra, bez „polovice textu zvýraznenej“.
- DÔLEŽITÉ: Odpoveď musí byť úplná – nepíš "..." ani neorezávaj text, vždy dokonči všetky sekcie. Každé vetu vždy dopíš do konca – nikdy nekonč v polovici vety ani nevynechávaj koniec myšlienky.
- ZAKAZANÉ: Ponechávať prázdne odrážky alebo prázdne položky zoznamu. Každá odrážka (•) alebo číslovaný bod MUSÍ mať za sebou text. Ak nemáš čo napísať k bodu, vynechaj ho – nikdy nepíš len „•“ alebo „-“ bez textu.
- KRITICKÉ: NIKDY nepíš, že nemáš informácie, že nemôžeš odpovedať, že v dokumentoch to nie je alebo že zdroje sú nedostatočné. Vždy poskytni konkrétnu odpoveď na základe dostupných dokumentov [D#] alebo webových zdrojov [W#]. Ak máš k dispozícii webové výsledky – odpovedaj z nich; ak dokumenty – z nich. Odmietnutie odpovede je ZAKAZANÉ."""

    def _build_user_prompt(context: str, sources_info: list, query: str, internet_only: bool = False) -> str:
        doc_sources = [s for s in sources_info if s.get("source") != "web"]
        available_docs = "\n".join([f"[{s.get('label', 'D'+str(s['num']))}] {s['title']}" for s in doc_sources])
        if internet_only:
            return f"""Otázka: {query}

Režim „odpoveď len z webu“: odpovedaj VÝLUČNE z výsledkov webového vyhľadávania. Cituj 3 až 6 zdrojov [W1]–[W6] pri každom dôležitom fakte (čísla, adresy, telefóny, názvy). Na konci sa zobrazí „Zdroje (internet)“ so 4–6 zdrojmi.
NIKDY nepíš, že informácia chýba – vždy sformuluj odpoveď z nižšie poskytnutých webových výsledkov."""
        return f"""Otázka: {query}

Dostupné dokumenty (cituj ako [D1], [D2], …):
{available_docs}

Kontekst z dokumentov:
{context}

Odpoveď zakladaj na dokumentoch a cituj VÝHRADNE [D1], [D2], [D3]. Systém ti zároveň poskytne výsledky z internetu na overenie a doplnenie – použi ich na overenie/doplnenie informácií, ale v texte NEPÍŠ [W1], [W2]; webové zdroje sa zobrazia na konci v sekcii „Overenie v internete“. V texte teda len [D#].
NEPÍŠ, že v dokumentoch informácia chýba – vždy sformuluj odpoveď z dokumentov a over/dopĺňaj cez web.
"""

    ANTHROPIC = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    result_parts = []
    answer_mode = None  # "faiss_verify" | "internet_only"
    web_verify_sources = []  # list of {"title", "url"} for Overenie v internete
    web_sources_internet = []

    if not ANTHROPIC:
        show_error_with_context("API key not found. Add ANTHROPIC_API_KEY to api_keys.env", docs)

    if ANTHROPIC:
        try:
            from langchain_anthropic import ChatAnthropic
            
            user_model_from_env = os.environ.get("ANTHROPIC_MODEL", "").strip()
            
            model_options = []
            use_only_user_model = False
            
            if user_model_from_env:
                model_options.append(user_model_from_env)
                use_only_user_model = True
                
                if "sonnet" in user_model_from_env.lower():
                    if "20241022" in user_model_from_env:
                        model_options.append("claude-3-5-sonnet")
                    else:
                        model_options.append("claude-3-5-sonnet-20241022")
                    model_options.append("claude-3-5-haiku-20241022")
                    model_options.append("claude-3-5-haiku")
                elif "haiku" in user_model_from_env.lower():
                    if "20241022" in user_model_from_env:
                        model_options.append("claude-3-5-haiku")
                    else:
                        model_options.append("claude-3-5-haiku-20241022")
                    model_options.append("claude-3-5-sonnet-20241022")
                    model_options.append("claude-3-5-sonnet")
                
                model_options = list(dict.fromkeys(model_options))
            
            if not model_options:
                model_options = [
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-sonnet",
                    "claude-3-5-haiku-20241022",
                    "claude-3-5-haiku",
                ]
            
            resp = None
            used_model = None

            for model_to_try in model_options:
                try:
                    llm = ChatAnthropic(
                        model=model_to_try,
                        temperature=0,
                        max_tokens=2000,
                        api_key=ANTHROPIC
                    )
                    need_second_call = need_web_only
                    if not need_web_only:
                        router_resp = None
                        attempts = 2  # max 2 retries (529/Overloaded) – zníži počet platených volaní
                        for attempt in range(attempts):
                            try:
                                router_resp = llm.invoke([("system", router_system), ("user", router_user)])
                                break
                            except Exception as e:
                                emsg = str(e)
                                if "Overloaded" in emsg or "529" in emsg:
                                    time.sleep(2 ** attempt)
                                    continue
                                elif "404" in emsg or "not_found" in emsg.lower():
                                    break
                                raise
                        if router_resp is not None:
                            router_content = (router_resp.content if hasattr(router_resp, "content") else str(router_resp)).strip()
                            lines = router_content.split("\n")
                            need_second_call = bool(lines and lines[0].strip() == NEED_WEB_MARKER)

                    web_model = model_to_try if model_to_try in CLAUDE_WEB_SEARCH_MODELS else CLAUDE_WEB_SEARCH_MODELS[0]

                    if need_second_call:
                        answer_mode = "internet_only"
                        user_prompt = _build_user_prompt(context, sources_info, query, internet_only=True)
                        try:
                            answer_text, web_sources = _call_claude_with_web_search(
                                system_prompt, user_prompt, web_model, ANTHROPIC
                            )
                            if answer_text:
                                result_parts.append(strip_trailing_source_sections(answer_text))
                                resp = True
                                raw_web = [ws for ws in web_sources if ws.get("url")]
                                limited_web = limit_web_sources(dedupe_web_sources_by_url(raw_web))
                                for i, ws in enumerate(limited_web, 1):
                                    web_sources_internet.append({
                                        "label": f"W{i}", "title": ws.get("title", ""), "url": ws.get("url", "")
                                    })
                            else:
                                result_parts.append("Odpoveď z webu nevrátila text. Skúste znova alebo overte Web Search v Anthropic Console.")
                                resp = True
                        except Exception as e:
                            result_parts.append(f"Vyhľadávanie na webe zlyhalo: {e}. Overte ANTHROPIC_API_KEY a Web Search.")
                            resp = True
                    else:
                        answer_mode = "faiss_verify"
                        user_prompt = _build_user_prompt(context, sources_info, query, internet_only=False)
                        try:
                            answer_text, web_sources = _call_claude_with_web_search(
                                system_prompt, user_prompt, web_model, ANTHROPIC
                            )
                            if answer_text:
                                result_parts.append(strip_trailing_source_sections(answer_text))
                                resp = True
                                raw_verify = [{"title": ws.get("title", ""), "url": ws.get("url", "")} for ws in web_sources if ws.get("url")]
                                web_verify_sources.extend(limit_web_sources(dedupe_web_sources_by_url(raw_verify)))
                            else:
                                resp = llm.invoke([("system", system_prompt), ("user", user_prompt)])
                                result_parts.append(strip_trailing_source_sections(resp.content if hasattr(resp, "content") else str(resp)))
                        except Exception as e:
                            resp = llm.invoke([("system", system_prompt), ("user", user_prompt)])
                            result_parts.append(strip_trailing_source_sections(resp.content if hasattr(resp, "content") else str(resp)))
                    break

                except Exception as e:
                    emsg = str(e)
                    if "404" in emsg or "not_found" in emsg.lower():
                        continue
                    continue

            if not resp:
                if use_only_user_model:
                    error_msg = f"Your model '{user_model_from_env}' from api_keys.env is not available. "
                    error_msg += f"\nTried models: {', '.join(model_options)}"
                    error_msg += "\n\nPossible solutions:"
                    error_msg += "\n1. Check if API key is active and has access to Anthropic API"
                    error_msg += "\n2. Check model name in api_keys.env (try: claude-3-5-sonnet or claude-3-5-haiku-20241022)"
                    error_msg += "\n3. Review Anthropic documentation for currently available models: https://docs.anthropic.com"
                else:
                    error_msg = "All AI models are unavailable. Check API key and internet connection."
                show_error_with_context(error_msg, docs)

        except Exception as e:
            show_error_with_context(f"Error initializing Anthropic client: {e}", docs)

    model_answer = "\n".join(result_parts) if result_parts else ""

    def extract_cited_labels(answer_text: str, prefix: str) -> set:
        text = answer_text
        for sep in ("## Zdroje", "## 📚 Zdroje"):
            idx = text.find(sep)
            if idx != -1:
                text = text[:idx]
        matches = re.findall(r'\[' + prefix + r'(\d+)\]', text)
        return set(int(m) for m in matches if m.isdigit())

    if answer_mode == "faiss_verify":
        cited_d = extract_cited_labels(model_answer, "D")
        doc_candidates = [s for s in sources_info if s.get("source") != "web" and s.get("label") and s["label"][1:].isdigit()]
        doc_list = [s for s in doc_candidates if int(s["label"][1:]) in cited_d] if cited_d else doc_candidates
        doc_list.sort(key=lambda s: int(s["label"][1:]))
        # Zlúčiť duplikáty: jeden dokument (rovnaký URL) môže mať viac chunkov [D1], [D2], … → jeden riadok so všetkými [D#]
        by_url = {}
        for s in doc_list:
            url = (s.get("url") or "").strip()
            if url not in by_url:
                by_url[url] = {"labels": [], "title": s.get("title", "").strip()}
            by_url[url]["labels"].append(s["label"])
            if (s.get("title") or "").strip() and len((s.get("title") or "").strip()) > len(by_url[url]["title"]):
                by_url[url]["title"] = (s.get("title") or "").strip()
        result_parts.append("\n## Zdroje (dokumenty)\n")
        for url, data in by_url.items():
            labels = sorted(data["labels"], key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)
            labels_str = ", ".join(f"[{l}]" for l in labels)
            title = data["title"] or "Katalóg podporných opatrení"
            result_parts.append(f"- **{labels_str}** {title} — {url}")
        if web_verify_sources:
            result_parts.append("\n## Overenie v internete\n")
            result_parts.append("Informácia z dokumentov bola overená alebo doplnená na:")
            for ws in limit_web_sources(web_verify_sources):
                desc = short_description_from_title_and_url(ws.get("title", ""), ws.get("url", ""))
                url = (ws.get("url") or "").strip()
                result_parts.append(f"- **{desc}** — {url}")
    elif answer_mode == "internet_only":
        web_list = list(web_sources_internet)
        web_list.sort(key=lambda s: int(s["label"][1:]) if s.get("label") and s["label"][1:].isdigit() else 0)
        result_parts.append("\n## Zdroje (internet)\n")
        for s in web_list:
            result_parts.append(f"- **[{s.get('label', '')}]** {s.get('title', '')} — {s.get('url', '')}")
    else:
        result_parts.append("\n## Zdroje\n")
        result_parts.append("- Katalóg podporných opatrení — https://podporneopatrenia.minedu.sk/katalog-podpornych-opatreni/")

    final_result = "\n".join(result_parts)
    return final_result


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]).strip() or \
        "Žiak s ADHD nevydrží 10 minút sústredenia – čo odporúčate na úrovni 1–3?"
    try:
        result = ask(query)
        print(result)
    except Exception as e:
        sys.exit(1)
