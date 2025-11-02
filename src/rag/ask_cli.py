# RAG systém pre konzultácie v oblasti vzdelávacej podpory
import os
import re
import sys
import time
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

def load_api_keys():
    """Načíta API kľúče z konfiguračného súboru"""
    env_file = Path("api_keys.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

def load_url_mapping():
    """Načíta mapovanie URL z urls.txt"""
    urls_file = Path("urls.txt")
    url_map = {}
    if urls_file.exists():
        for line in urls_file.read_text(encoding="utf-8").splitlines():
            url = line.strip()
            if not url or url.startswith("#"):
                continue
            # Vytvoríme viacero kľúčov pre mapovanie:
            # 1. Z poslednej časti URL (bez /)
            url_key = url.rstrip("/").split("/")[-1]
            if url_key and url_key not in url_map:
                url_map[url_key] = url
            # 2. Z celej cesty URL (bez https:// a bez /)
            if "podporneopatrenia.minedu.sk/" in url:
                path_part = url.split("podporneopatrenia.minedu.sk/", 1)[1].rstrip("/")
                if path_part:
                    url_map[path_part] = url
                    # 3. Aj bez posledného / ak je
                    if path_part.endswith("/"):
                        url_map[path_part[:-1]] = url
    return url_map

URL_MAP = load_url_mapping()

def resolve_url(doc_meta: dict) -> str:
    """Nájde správny URL na základe metadát dokumentu"""
    # Ak už máme správny URL (začína s https://), použijeme ho
    existing_url = doc_meta.get("url", "").strip()
    if existing_url and existing_url.startswith("https://"):
        # Odstránime index.html alebo index.htm z URL
        existing_url = existing_url.replace("/index.html", "").replace("/index.htm", "")
        # Ak URL nekončí na /, pridáme ho (alebo necháme ako je, ak je z urls.txt)
        if not existing_url.endswith("/") and "podporneopatrenia.minedu.sk" in existing_url:
            existing_url += "/"
        return existing_url
    
    source_file = doc_meta.get("source_file", "")
    if not source_file:
        return existing_url
    
    # Skúsime nájsť URL na základe cesty k súboru
    source_path = Path(source_file)
    parts = list(source_path.parts)
    
    # 1. Skúsime nájsť podporneopatrenia.minedu.sk v ceste
    if "podporneopatrenia.minedu.sk" in parts:
        idx = parts.index("podporneopatrenia.minedu.sk")
        # Zoberieme všetko po podporneopatrenia.minedu.sk
        tail_parts = parts[idx + 1:]
        # Odstránime index.md, index.html, .md, .html
        clean_parts = []
        for part in tail_parts:
            cleaned = part.replace(".md", "").replace(".html", "")
            if cleaned and cleaned != "index":
                clean_parts.append(cleaned)
        
        # Skúsime nájsť URL pre celú cestu
        path_key = "/".join(clean_parts)
        if path_key in URL_MAP:
            return URL_MAP[path_key]
        
        # Skúsime nájsť URL pre prvú časť (názov priečinka)
        if clean_parts:
            first_part = clean_parts[0]
            if first_part in URL_MAP:
                return URL_MAP[first_part]
    
    # 2. Skúsime nájsť podľa názvu súboru
    file_name = source_path.name.replace(".md", "").replace(".html", "")
    if file_name and file_name != "index":
        if file_name in URL_MAP:
            return URL_MAP[file_name]
    
    # 3. Skúsime nájsť podľa častí cesty (od konca)
    for part in reversed(parts):
        part_clean = part.replace(".md", "").replace(".html", "")
        if part_clean and part_clean != "index":
            if part_clean in URL_MAP:
                return URL_MAP[part_clean]
    
    # 4. Ak nič nefungovalo, skúsime vytvoriť URL z cesty
    if "podporneopatrenia.minedu.sk" in parts:
        idx = parts.index("podporneopatrenia.minedu.sk")
        tail_parts = parts[idx + 1:]
        clean_parts = [p.replace(".md", "").replace(".html", "") for p in tail_parts if p.replace(".md", "").replace(".html", "") != "index"]
        if clean_parts:
            constructed_path = "/".join(clean_parts)
            # Skontrolujeme, či takýto path existuje v URL_MAP
            if constructed_path in URL_MAP:
                return URL_MAP[constructed_path]
            # Alebo skúsime vytvoriť URL
            constructed = f"https://podporneopatrenia.minedu.sk/{constructed_path}/"
            # Skontrolujeme, či nejaký URL v URL_MAP obsahuje tento path
            for url in URL_MAP.values():
                if constructed_path in url:
                    return url
            return constructed
    
    # Ak nič nefungovalo, vrátime existujúci URL alebo prázdny
    return existing_url

load_api_keys()

PERSIST = "rag_index/faiss_e5"

# Získanie otázky používateľa
query = " ".join(sys.argv[1:]).strip() or \
    "Žiak s ADHD nevydrží 10 minút sústredenia – čo odporúčate na úrovni 1–2?"

# Inicializácia vektorovej databázy
EMBED_MODEL = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-small")
embedder = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL,
    encode_kwargs={"normalize_embeddings": True},
)
vs = FAISS.load_local(PERSIST, embeddings=embedder, allow_dangerous_deserialization=True)

# Vyhľadávanie relevantných dokumentov
docs_all = vs.similarity_search(query, k=20)

# Rozšírené vyhľadávanie podľa kľúčových slov
keywords = []
if "pozornosť" in query.lower() or "sústredenie" in query.lower():
    keywords.extend(["pozornosť", "sústredenie", "ADHD", "organizácia", "čas"])
if "matematika" in query.lower():
    keywords.extend(["matematika", "matematické", "počítanie", "úlohy"])
if "hodina" in query.lower():
    keywords.extend(["hodina", "vyučovanie", "organizácia", "časové"])

for keyword in keywords[:3]:
    try:
        keyword_docs = vs.similarity_search(keyword, k=5)
        docs_all.extend(keyword_docs)
    except:
        continue

# Odstránenie duplicít
seen_ids = set()
unique_docs = []
for doc in docs_all:
    doc_id = doc.metadata.get("source_file", "") + str(doc.page_content[:100])
    if doc_id not in seen_ids:
        seen_ids.add(doc_id)
        unique_docs.append(doc)

docs_all = unique_docs

# Filtrovanie podľa úrovní podpory
def level_ok(meta: dict) -> bool:
    lv = (meta or {}).get("levels", "")
    if not lv:
        return True
    return any(x in lv for x in ["1", "2"])

docs_filtered = [d for d in docs_all if level_ok(d.metadata)]
docs = docs_filtered[:12] if docs_filtered else docs_all[:12]

# Príprava kontextu pre LLM
def compact(txt: str) -> str:
    return re.sub(r"\s+", " ", txt).strip()

context_blocks = []
sources_info = []
for i, d in enumerate(docs, 1):
    title = d.metadata.get("title", "") or ""
    # Použijeme funkciu na nájdenie správneho URL
    url = resolve_url(d.metadata)
    snippet = compact(d.page_content)[:1000]
    context_blocks.append(f"[{i}] {title}\n---\n{snippet}")
    sources_info.append({"num": i, "title": title, "url": url})

context = "\n\n".join(context_blocks)

# Systémový prompt pre LLM
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

# Funkcia pre spracovanie chýb - zobrazí informácie o nájdených dokumentoch
def show_error_with_context(error_msg, docs_list):
    """Zobrazí chybu spolu s informáciami o nájdených dokumentoch"""
    print(f"❌ CHYBA: {error_msg}", file=sys.stderr)
    print("\n⚠️  Nepodarilo sa získať odpoveď od AI modelu.", file=sys.stderr)
    print(f"📄 Nájdených {len(docs_list)} relevantných dokumentov:", file=sys.stderr)
    for i, d in enumerate(docs_list[:5], 1):
        title = d.metadata.get("title", "Bez názvu")
        print(f"   [{i}] {title}", file=sys.stderr)
    print("\nSkontrolujte:", file=sys.stderr)
    print("  1. Či je správne nastavený ANTHROPIC_API_KEY v api_keys.env", file=sys.stderr)
    print("  2. Či je dostupný internet", file=sys.stderr)
    print("  3. Či je API kľúč aktívny", file=sys.stderr)
    sys.exit(1)

# Hlavný blok vykonávania s LLM
ANTHROPIC = os.environ.get("ANTHROPIC_API_KEY", "").strip()
OPENAI = os.environ.get("OPENAI_API_KEY", "").strip()

if ANTHROPIC:
    try:
        from langchain_anthropic import ChatAnthropic
        
        # DÔLEŽITÉ: Používame VÝLUČNE model z api_keys.env, ak je špecifikovaný
        # Ak nie je špecifikovaný alebo nefunguje, použijeme fallback modely
        user_model_from_env = os.environ.get("ANTHROPIC_MODEL", "").strip()
        
        # Zoznam modelov na skúšanie
        model_options = []
        use_only_user_model = False
        
        # 1. Ak máme model z api_keys.env, použijeme HO A LEN HO (s možným fallback na inú verziu)
        if user_model_from_env:
            model_options.append(user_model_from_env)
            use_only_user_model = True
            
            # Ak model nefunguje, skúsime alternatívne verzie
            if "sonnet" in user_model_from_env.lower():
                # Pre Sonnet skúsime rôzne verzie
                if "20241022" in user_model_from_env:
                    # Ak má dátum, skúsime bez dátumu
                    model_options.append("claude-3-5-sonnet")
                else:
                    # Ak nemá dátum, skúsime s dátumom
                    model_options.append("claude-3-5-sonnet-20241022")
                # Vždy skúsime aj Haiku ako fallback
                model_options.append("claude-3-5-haiku-20241022")
                model_options.append("claude-3-5-haiku")
            elif "haiku" in user_model_from_env.lower():
                # Pre Haiku skúsime rôzne verzie
                if "20241022" in user_model_from_env:
                    model_options.append("claude-3-5-haiku")
                else:
                    model_options.append("claude-3-5-haiku-20241022")
                # Vždy skúsime aj Sonnet ako fallback
                model_options.append("claude-3-5-sonnet-20241022")
                model_options.append("claude-3-5-sonnet")
            
            # Odstránime duplikáty
            model_options = list(dict.fromkeys(model_options))
        
        # 2. Ak nie je špecifikovaný model v api_keys.env, použijeme štandardné modely
        if not model_options:
            model_options = [
                "claude-3-5-sonnet-20241022",       # Aktuálna verzia s dátumom (najlepšia)
                "claude-3-5-sonnet",                # Verzia bez dátumu
                "claude-3-5-haiku-20241022",        # Alternatíva Haiku (rýchlejšia)
                "claude-3-5-haiku",                 # Haiku bez dátumu
            ]
        
        messages = [("system", system_prompt), ("user", user_prompt)]
        resp = None
        used_model = None
        
        # Skúsime rôzne modely s VAŠIM API kľúčom
        for model_to_try in model_options:
            try:
                llm = ChatAnthropic(
                    model=model_to_try, 
                    temperature=0, 
                    max_tokens=600,
                    api_key=ANTHROPIC  # Explicitne špecifikujeme VÁŠ API kľúč
                )
                attempts = 4
                for attempt in range(attempts):
                    try:
                        resp = llm.invoke(messages)
                        used_model = model_to_try
                        print(resp.content)
                        print("\n## 📚 Zdroje")
                        for source in sources_info:
                            if source["url"]:
                                print(f"[{source['num']}] {source['title']} — {source['url']}")
                            else:
                                print(f"[{source['num']}] {source['title']}")
                        break
                    except Exception as e:
                        emsg = str(e)
                        if "Overloaded" in emsg or "529" in emsg:
                            wait = 2 ** attempt
                            time.sleep(wait)
                            continue
                        elif "404" in emsg or "not_found" in emsg.lower():
                            # Model nebol nájdený
                            break
                        else:
                            raise  # Iná chyba, pokračujeme ďalej
                else:
                    # Všetky pokusy neúspešné kvôli preťaženiu pre tento model
                    continue
                
                if resp:  # Ak sme dostali odpoveď, ukončíme
                    break
                    
            except Exception as e:
                emsg = str(e)
                if "404" in emsg or "not_found" in emsg.lower():
                    # Model nebol nájdený, pokračujeme v skúšaní iných
                    continue
                else:
                    # Neukončujeme hneď, skúsime iné modely (alebo fallback verziu)
                    continue
        
        if not resp:
            # Všetky modely nefungovali
            if use_only_user_model:
                error_msg = f"Váš model '{user_model_from_env}' z api_keys.env nie je dostupný. "
                error_msg += f"\nSkúšané modely: {', '.join(model_options)}"
                error_msg += "\n\nMožné riešenia:"
                error_msg += "\n1. Skontrolujte, či je API kľúč aktívny a má prístup k Anthropic API"
                error_msg += "\n2. Skontrolujte názov modelu v api_keys.env (skúste: claude-3-5-sonnet alebo claude-3-5-haiku-20241022)"
                error_msg += "\n3. Prezrite si dokumentáciu Anthropic pre aktualne dostupné modely: https://docs.anthropic.com"
            else:
                error_msg = "Všetky AI modely nie sú dostupné. Skontrolujte API kľúč a internetové pripojenie."
            show_error_with_context(error_msg, docs)

    except Exception as e:
        show_error_with_context(f"Chyba inicializácie Anthropic klienta: {e}", docs)

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
        print("\n## 📚 Zdroje")
        for source in sources_info:
            if source["url"]:
                print(f"[{source['num']}] {source['title']} — {source['url']}")
            else:
                print(f"[{source['num']}] {source['title']}")

    except Exception as e:
        show_error_with_context(f"Chyba OpenAI: {e}", docs)

else:
    show_error_with_context("Nenájdené API kľúče. Pridajte ANTHROPIC_API_KEY alebo OPENAI_API_KEY do api_keys.env", docs)
