import os
import re
import sys
import time
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

def load_api_keys():
    env_file = Path("api_keys.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

def load_url_mapping():
    urls_file = Path("urls.txt")
    url_map = {}
    if urls_file.exists():
        for line in urls_file.read_text(encoding="utf-8").splitlines():
            url = line.strip()
            if not url or url.startswith("#"):
                continue
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

def resolve_url(doc_meta: dict) -> str:
    existing_url = doc_meta.get("url", "").strip()
    if existing_url and existing_url.startswith("https://"):
        existing_url = existing_url.replace("/index.html", "").replace("/index.htm", "")
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
            return URL_MAP[path_key]
        
        if clean_parts:
            first_part = clean_parts[0]
            if first_part in URL_MAP:
                return URL_MAP[first_part]
    
    file_name = source_path.name.replace(".md", "").replace(".html", "")
    if file_name and file_name != "index":
        if file_name in URL_MAP:
            return URL_MAP[file_name]
    
    for part in reversed(parts):
        part_clean = part.replace(".md", "").replace(".html", "")
        if part_clean and part_clean != "index":
            if part_clean in URL_MAP:
                return URL_MAP[part_clean]
    
    if "podporneopatrenia.minedu.sk" in parts:
        idx = parts.index("podporneopatrenia.minedu.sk")
        tail_parts = parts[idx + 1:]
        clean_parts = [p.replace(".md", "").replace(".html", "") for p in tail_parts if p.replace(".md", "").replace(".html", "") != "index"]
        if clean_parts:
            constructed_path = "/".join(clean_parts)
            if constructed_path in URL_MAP:
                return URL_MAP[constructed_path]
            constructed = f"https://podporneopatrenia.minedu.sk/{constructed_path}/"
            for url in URL_MAP.values():
                if constructed_path in url:
                    return url
            return constructed
    
    return existing_url

load_api_keys()

PERSIST = "rag_index/faiss_e5"

query = " ".join(sys.argv[1:]).strip() or \
    "Žiak s ADHD nevydrží 10 minút sústredenia – čo odporúčate na úrovni 1–3?"

EMBED_MODEL = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-small")
embedder = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL,
    encode_kwargs={"normalize_embeddings": True},
)
vs = FAISS.load_local(PERSIST, embeddings=embedder, allow_dangerous_deserialization=True)

docs_all = vs.similarity_search(query, k=20)

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
        docs_all.extend(keyword_docs)
    except:
        continue

seen_ids = set()
unique_docs = []
for doc in docs_all:
    doc_id = doc.metadata.get("source_file", "") + str(doc.page_content[:100])
    if doc_id not in seen_ids:
        seen_ids.add(doc_id)
        unique_docs.append(doc)

docs_all = unique_docs

def level_ok(meta: dict) -> bool:
    lv = (meta or {}).get("levels", "")
    if not lv:
        return True
    return any(x in lv for x in ["1", "2", "3"])

docs_filtered = [d for d in docs_all if level_ok(d.metadata)]
docs = docs_filtered[:12] if docs_filtered else docs_all[:12]

def compact(txt: str) -> str:
    return re.sub(r"\s+", " ", txt).strip()

context_blocks = []
sources_info = []
for i, d in enumerate(docs, 1):
    title = d.metadata.get("title", "") or ""
    url = resolve_url(d.metadata)
    snippet = compact(d.page_content)[:1000]
    context_blocks.append(f"[{i}] {title}\n---\n{snippet}")
    sources_info.append({"num": i, "title": title, "url": url})

context = "\n\n".join(context_blocks)

system_prompt = """Si expertný asistent špeciálneho pedagóga na Slovensku s hlbokými znalosťami o podporných opatreniach a inkluzívnom vzdelávaní.

Tvoja úloha: Poskytovať konkrétne, praktické a realizovateľné riešenia na základe oficiálnych dokumentov.

ANALYTICKÝ PRÍSTUP:
1. Najprv analyzuj problém v otázke
2. Identifikuj kľúčové potreby žiaka/dieťaťa
3. Vyber najrelevantnejšie opatrenia z dokumentov
4. Navrhni konkrétne kroky pre realizáciu

FORMÁT ODPOVEDE:
## 🎯 Analýza problému
- Stručný popis identifikovaného problému
- Kľúčové potreby žiaka

## 📋 Konkrétne opatrenia na zajtra
### Pre učiteľa:
- [Učiteľ] Konkrétna činnosť s presným popisom
- [Učiteľ] Ďalšia činnosť...

### Pre asistenta pedagóga:
- [Asistent] Špecifická úloha s detajlami
- [Asistent] Ďalšia úloha...

### Pre školu/vedenie:
- [Škola] Organizačné opatrenie
- [Škola] Ďalšie opatrenie...

## ⚖️ Úpravy hodnotenia (ak relevantné)
- Konkrétne spôsoby hodnotenia
- Adaptácie pre žiaka

PRAVIDLÁ:
- Buď maximálne konkrétny a praktický
- Odpovedaj VÝLUČNE na základe poskytnutých dokumentov
- Ak informácie chýbajú, napíš "Potrebné doplniť z odborných zdrojov"
- Používaj slovenský jazyk
- Zameraj sa na realizovateľné riešenia
- NEUVÁDZAJ zdroje v texte - budú pridané automaticky"""

user_prompt = f"""Otázka: {query}

Kontekst:
{context}
"""

def show_error_with_context(error_msg, docs_list):
    print(f"❌ ERROR: {error_msg}", file=sys.stderr)
    print("\n⚠️  Failed to get response from AI model.", file=sys.stderr)
    print(f"📄 Found {len(docs_list)} relevant documents:", file=sys.stderr)
    for i, d in enumerate(docs_list[:5], 1):
        title = d.metadata.get("title", "Untitled")
        print(f"   [{i}] {title}", file=sys.stderr)
    print("\nCheck:", file=sys.stderr)
    print("  1. Whether ANTHROPIC_API_KEY is correctly set in api_keys.env", file=sys.stderr)
    print("  2. Whether internet is available", file=sys.stderr)
    print("  3. Whether API key is active", file=sys.stderr)
    sys.exit(1)

ANTHROPIC = os.environ.get("ANTHROPIC_API_KEY", "").strip()
OPENAI = os.environ.get("OPENAI_API_KEY", "").strip()

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
                    max_tokens=600,
                    api_key=ANTHROPIC
                )
                attempts = 4
                for attempt in range(attempts):
                    try:
                        resp = llm.invoke(messages)
                        used_model = model_to_try
                        print(resp.content)
                        print("\n## 📚 Zdroje\n")
                        for source in sources_info:
                            if source["url"]:
                                print(f"- [{source['num']}] {source['title']} — {source['url']}")
                            else:
                                print(f"- [{source['num']}] {source['title']}")
                        print()
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
        print(resp.content)
        print("\n## 📚 Zdroje\n")
        for source in sources_info:
            if source["url"]:
                print(f"- [{source['num']}] {source['title']} — {source['url']}")
            else:
                print(f"- [{source['num']}] {source['title']}")
        print()

    except Exception as e:
        show_error_with_context(f"OpenAI error: {e}", docs)

else:
    show_error_with_context("API keys not found. Add ANTHROPIC_API_KEY or OPENAI_API_KEY to api_keys.env", docs)
