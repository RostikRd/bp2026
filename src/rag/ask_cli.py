# RAG system for educational support consultations
import os
import re
import sys
import time
from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

def load_api_keys():
    """Load API keys from configuration file"""
    env_file = Path("api_keys.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

load_api_keys()

PERSIST = "rag_index/faiss_e5"

# Get user query
query = " ".join(sys.argv[1:]).strip() or \
    "Žiak s ADHD nevydrží 10 minút sústredenia – čo odporúčate na úrovni 1–2?"

# Initialize vector database
EMBED_MODEL = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-small")
embedder = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL,
    encode_kwargs={"normalize_embeddings": True},
)
vs = FAISS.load_local(PERSIST, embeddings=embedder, allow_dangerous_deserialization=True)

# Search for relevant documents
docs_all = vs.similarity_search(query, k=20)

# Extended search by keywords
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

# Remove duplicates
seen_ids = set()
unique_docs = []
for doc in docs_all:
    doc_id = doc.metadata.get("source_file", "") + str(doc.page_content[:100])
    if doc_id not in seen_ids:
        seen_ids.add(doc_id)
        unique_docs.append(doc)

docs_all = unique_docs

# Filter by support levels
def level_ok(meta: dict) -> bool:
    lv = (meta or {}).get("levels", "")
    if not lv:
        return True
    return any(x in lv for x in ["1", "2"])

docs_filtered = [d for d in docs_all if level_ok(d.metadata)]
docs = docs_filtered[:12] if docs_filtered else docs_all[:12]

# Prepare context for LLM
def compact(txt: str) -> str:
    return re.sub(r"\s+", " ", txt).strip()

context_blocks = []
sources_info = []
for i, d in enumerate(docs, 1):
    title = d.metadata.get("title", "") or ""
    url = d.metadata.get("url", "") or ""
    snippet = compact(d.page_content)[:1000]
    context_blocks.append(f"[{i}] {title}\n---\n{snippet}")
    sources_info.append({"num": i, "title": title, "url": url})

context = "\n\n".join(context_blocks)

# System prompt for LLM
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
- NEUVÁDZAJ zdroje v тексті - budú pridané automaticky"""

user_prompt = f"""Otázka: {query}

Kontekst:
{context}
"""

# Offline mode for cases without API
def offline_reply(docs_list):
    print("## 🎯 Analýza problému")
    print("- Identifikovaný problém: Potreba podpory pre žiaka s problémami sústredenia")
    print("- Kľúčové potreby: Organizácia hodiny, časové signály, rozdelenie úloh")
    print()
    
    print("## 📋 Konkrétne opatrenia na zajtra")
    print("### Pre učiteľa:")
    
    teacher_actions = []
    assistant_actions = []
    school_actions = []
    
    for d in docs_list:
        content = d.page_content.lower()
        sentences = re.split(r'(?<=[.!?])\s+', d.page_content)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 30 or len(sentence) > 400:
                continue
                
            if any(word in sentence.lower() for word in ['učiteľ', 'pedagóg', 'vyučovanie', 'hodina', 'trieda', 'organizácia']):
                if any(action in sentence.lower() for action in ['upraviť', 'zmeniť', 'použiť', 'zabezpečiť', 'poskytnúť', 'rozdeliť', 'čas']):
                    teacher_actions.append(f"- [Učiteľ] {sentence.strip()}")
            
            elif any(word in sentence.lower() for word in ['asistent', 'pedagogický asistent', 'podpora']):
                if any(action in sentence.lower() for action in ['pomôcť', 'podporiť', 'asistovať', 'spolupracovať']):
                    assistant_actions.append(f"- [Asistent] {sentence.strip()}")
            
            elif any(word in sentence.lower() for word in ['škola', 'vedenie', 'riaditeľ', 'zariadenie']):
                if any(action in sentence.lower() for action in ['zabezpečiť', 'poskytnúť', 'upraviť', 'zmeniť']):
                    school_actions.append(f"- [Škola] {sentence.strip()}")
    
    all_actions = teacher_actions[:4] + assistant_actions[:2] + school_actions[:2]
    
    if all_actions:
        for action in all_actions[:6]:
            print(action)
    else:
        print("- [Učiteľ] Rozdeliť hodinu na kratšie časové úseky (10-15 min)")
        print("- [Učiteľ] Použiť vizuálne signály pre zmeny aktivít")
        print("- [Učiteľ] Poskytnúť časté prestávky na pohyb")
        print("- [Asistent] Pomôcť žiakovi s organizáciou pracovného miesta")
        print("- [Škola] Zabezpečiť vhodné prostredie pre sústredenie")
    
    print("\n## 📚 Zdroje")
    for i, d in enumerate(docs_list, 1):
        title = d.metadata.get("title", "")
        url = d.metadata.get("url", "")
        if url:
            print(f"[{i}] {title} — {url}")
        else:
            print(f"[{i}] {title}")

# Main execution block with LLM
ANTHROPIC = os.environ.get("ANTHROPIC_API_KEY", "").strip()
OPENAI = os.environ.get("OPENAI_API_KEY", "").strip()

if ANTHROPIC:
    try:
        from langchain_anthropic import ChatAnthropic
        model_name = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
        llm = ChatAnthropic(model=model_name, temperature=0, max_tokens=600)

        messages = [("system", system_prompt), ("user", user_prompt)]

        attempts = 4
        for attempt in range(attempts):
            try:
                resp = llm.invoke(messages)
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
                    print(f"WARN: Anthropic overloaded (529). Retry in {wait}s…", file=sys.stderr)
                    time.sleep(wait)
                    continue
                else:
                    print(f"WARN: Anthropic error: {e}. Falling back offline.", file=sys.stderr)
                    offline_reply(docs)
                    break
        else:
            print("WARN: Anthropic still overloaded after retries. Offline fallback.", file=sys.stderr)
            offline_reply(docs)

    except Exception as e:
        print(f"WARN: Anthropic client import/use failed: {e}. Offline fallback.", file=sys.stderr)
        offline_reply(docs)

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
        print(f"WARN: OpenAI error: {e}. Offline fallback.", file=sys.stderr)
        offline_reply(docs)

else:
    offline_reply(docs)
