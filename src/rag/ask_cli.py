import os
import re
import sys
import time
from pathlib import Path

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


# Main RAG entry: retrieves relevant docs, builds context, calls LLM (Anthropic/OpenAI), appends sources section and returns full answer.
def ask(query: str) -> str:
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
    
    context_blocks = []
    sources_info = []
    for i, d in enumerate(docs, 1):
        title = d.metadata.get("title", "") or ""
        if title == "Kniha katalóg podporných opatrení":
            title = "Katalóg podporných opatrení. 2. vydanie. Bratislava: Národný inštitút vzdelávania a mládeže, 2024. Schválené Ministerstvom školstva, výskumu, vývoja a mládeže Slovenskej republiky pod číslom 2024/17370:1‑E1660, s platnosťou od 1. septembra 2024."
        if not title:
            title = d.metadata.get("source_file", "").split("/")[-1] or f"Dokument {i}"
        url = resolve_url(d.metadata)
        snippet = compact(d.page_content)[:1000]
        context_blocks.append(f"[{i}] {title}\n---\n{snippet}")
        sources_info.append({"num": i, "title": title, "url": url})
    
    if not sources_info:
        sources_info.append({"num": 1, "title": "Katalóg podporných opatrení", "url": "https://podporneopatrenia.minedu.sk/katalog-podpornych-opatreni/"})

    context = "\n\n".join(context_blocks)
    
    system_prompt = """Si expertný asistent špeciálneho pedagóga na Slovensku s hlbokými znalosťami o podporných opatreniach a inkluzívnom vzdelávaní.

Tvoja úloha: Poskytovať konkrétne, praktické a realizovateľné riešenia na základe oficiálnych dokumentov.

KRÍTICKY DÔLEŽITÉ - VYSVETLITEĽNOSŤ A ODKAZY:
1. PRE KAŽDÉ OPATRENIE MUSÍŠ UVIESŤ "Prečo toto opatrenie:" s 2-3 vetami:
   - Akú konkrétnu potrebu žiaka rieši
   - Prečo je toto opatrenie vhodné pre danú situáciu
   - Odkaz na dokument [N] z ktorého toto opatrenie pochádza
2. PRI KAŽDEJ ČINNOSTI MUSÍŠ UVIESŤ ODKAZ [N] na dokument:
   - Ak navrhuješ niečo z dokumentu [1], napíš [1]
   - Ak kombinuješ z [2] a [3], napíš [2], [3]
   - BEZ ODKAZOV [N] NEPÍŠ ŽIADNE OPATRENIA
3. Vždy zdôvodni výber opatrenia – prečo práve toto, nie iné

ANALYTICKÝ PRÍSTUP:
1. Analyzuj problém v otázke a identifikuj kľúčové potreby žiaka.
2. Pre každú potrebu nájdi relevantné opatrenia v dokumentoch [1], [2], [3]...
3. Pre každé opatrenie vysvetli PREČO je vhodné (2-3 vety) a uveď odkaz [N].

FORMÁT ODPOVEDE:
## 🎯 Analýza problému
- Stručný popis identifikovaného problému
- Kľúčové potreby žiaka

## 📋 Konkrétne opatrenia

### [Názov opatrenia alebo kategórie]
**Prečo toto opatrenie:**
- 2-3 vety vysvetľujúce akú potrebu rieši a prečo je vhodné
- Odkaz na dokument [N] z ktorého pochádza

**Realizácia:**
- [Učiteľ] Konkrétna činnosť s odkazom [N]
- [Asistent] Konkrétna úloha s odkazom [N]
- [Škola] Organizačné opatrenie s odkazom [N]

### Pre učiteľa:
- [Učiteľ] Činnosť – odkaz [N] (napr. "Podľa [1] a [3]...")

### Pre asistenta pedagóga:
- [Asistent] Úloha – odkaz [N]

### Pre školu/vedenie:
- [Škola] Opatrenie – odkaz [N]

## Úpravy hodnotenia (ak relevantné)
- Konkrétne spôsoby hodnotenia s odôvodnením a odkazmi [N]

PRAVIDLÁ:
- VŽDY používaj odkazy [1], [2], [3]... pri každom opatrení a činnosti
- VŽDY vysvetli "Prečo toto opatrenie" (2-3 vety) pre každé opatrenie
- Odpovedaj VÝLUČNE na základe poskytnutých dokumentov
- Používaj len NAJRELEVANTNEJŠIE dokumenty – nie всі, len tie ktoré skutočne potrebuješ (zvyčajne 3-7)
- Ak informácie chýbajú, napíš "Potrebné doplniť z odborných zdrojov"
- Používaj slovenský jazyk
- NEUVÁDZAJ zoznam zdrojov ani URL – zdroje sa doplnia automaticky na konci
- NEUVÁDZAJ zákony, legislatívu ani odkazy na slov-lex – odpoveď len z dokumentov podporných opatrení
- DÔLEŽITÉ: Odpoveď musí byť úplná – nepíš "..." або обрізай текст, vždy dokonči všetky sekcie"""

    # Формуємо список доступних документів для моделі
    available_docs = "\n".join([f"[{s['num']}] {s['title']}" for s in sources_info])
    
    user_prompt = f"""Otázka: {query}

Dostupné dokumenty (používaj ich čísla v odkazoch [N]):
{available_docs}

Kontekst z dokumentov:
{context}

DÔLEŽITÉ: Pri každom opatrení a činnosti MUSÍŠ uviest odkaz na dokument [N] z ktorého informácia pochádza. Napríklad: "Podľa [1] a [3]..." alebo "Toto opatrenie je opísané v [2]...".
"""
    
    ANTHROPIC = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    OPENAI = os.environ.get("OPENAI_API_KEY", "").strip()
    
    result_parts = []
    
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
            
            messages = [("system", system_prompt), ("user", user_prompt)]
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
                    attempts = 4
                    for attempt in range(attempts):
                        try:
                            resp = llm.invoke(messages)
                            used_model = model_to_try
                            result_parts.append(resp.content)
                            break
                        except Exception as e:
                            emsg = str(e)
                            if "Overloaded" in emsg or "529" in emsg:
                                wait = 2 ** attempt
                                time.sleep(wait)
                                continue
                            elif "404" in emsg or "not_found" in emsg.lower():
                                break
                            else:
                                raise
                    else:
                        continue
                    
                    if resp:
                        break
                        
                except Exception as e:
                    emsg = str(e)
                    if "404" in emsg or "not_found" in emsg.lower():
                        continue
                    else:
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

    elif OPENAI:
        try:
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_openai import ChatOpenAI

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", "{up}")
            ])
            llm = ChatOpenAI(model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"), temperature=0)
            resp = llm.invoke(prompt.format_messages(up=user_prompt))
            result_parts.append(resp.content)

        except Exception as e:
            show_error_with_context(f"OpenAI error: {e}", docs)

    else:
        show_error_with_context("API keys not found. Add ANTHROPIC_API_KEY or OPENAI_API_KEY to api_keys.env", docs)
    
    model_answer = "\n".join(result_parts) if result_parts else ""

    if not sources_info:
        sources_info.append({"num": 1, "title": "Katalóg podporných opatrení", "url": "https://podporneopatrenia.minedu.sk/katalog-podpornych-opatreni/"})

    # Extracts document numbers [1], [2], [3]... cited in the answer text (before Zdroje section).
    def extract_used_source_numbers(answer_text: str) -> set:
        import re
        zdroje_start = answer_text.find("## 📚 Zdroje")
        if zdroje_start != -1:
            answer_text = answer_text[:zdroje_start]
        matches = re.findall(r'\[(\d+)\]', answer_text)
        used_numbers = set()
        for match in matches:
            try:
                num = int(match)
                if 1 <= num <= len(sources_info):
                    used_numbers.add(num)
            except ValueError:
                continue
        return used_numbers

    used_source_numbers = extract_used_source_numbers(model_answer)
    used_sources = [s for s in sources_info if s["num"] in used_source_numbers]
    if used_sources:
        used_sources.sort(key=lambda x: x["num"])
    
    result_parts.append("\n## 📚 Zdroje\n")
    result_parts.append("### 📄 Dokumenty podporných opatrení\n")

    sources_added = False
    if used_sources:
        for source in used_sources:
            if source.get("url"):
                result_parts.append(f"- **[{source['num']}]** {source['title']}  \n  🔗 {source['url']}")
            else:
                result_parts.append(f"- **[{source['num']}]** {source['title']}")
            sources_added = True
    elif sources_info:
        seen_urls_fallback = set()
        unique_fallback_sources = []
        for source in sources_info:
            url = source.get("url", "").strip()
            if url and url in seen_urls_fallback:
                continue
            unique_fallback_sources.append(source)
            if url:
                seen_urls_fallback.add(url)
        for source in unique_fallback_sources:
            if source.get("url"):
                result_parts.append(f"- **[{source['num']}]** {source['title']}  \n  🔗 {source['url']}")
            else:
                result_parts.append(f"- **[{source['num']}]** {source['title']}")
            sources_added = True

    if not sources_added:
        result_parts.append("- *Zdroje sa pripravujú...*")

    final_result = "\n".join(result_parts)

    if "## 📚 Zdroje" not in final_result:
        final_result += "\n## 📚 Zdroje\n"
        final_result += "### 📄 Dokumenty podporných opatrení\n"
        
        if sources_info:
            for source in sources_info:
                if source.get("url"):
                    final_result += f"- **[{source['num']}]** {source['title']}  \n  🔗 {source['url']}\n"
                else:
                    final_result += f"- **[{source['num']}]** {source['title']}\n"
        else:
            final_result += "- *Zdroje sa pripravujú...*\n"

    if "## 📚 Zdroje" not in final_result:
        final_result = final_result.rstrip() + "\n\n## 📚 Zdroje\n### 📄 Dokumenty podporných opatrení\n- *Kontaktujte administrátora systému*\n"
    
    return final_result


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]).strip() or \
        "Žiak s ADHD nevydrží 10 minút sústredenia – čo odporúčate na úrovni 1–3?"
    try:
        result = ask(query)
        print(result)
    except Exception as e:
        sys.exit(1)
