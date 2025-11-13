# BP2026 - Technická dokumentácia pre prezentáciu

## 🎯 Čo robí projekt?

Inteligentný RAG (Retrieval-Augmented Generation) systém, ktorý pomáha špeciálnym pedagógom nájsť odpovede na otázky týkajúce sa podporných opatrení na základe oficiálnych dokumentov z portálu podporneopatrenia.minedu.sk.

---

## 🏗️ Architektúra systému

### 3-vrstvová architektúra:

```
┌─────────────────┐
│   Frontend      │  HTML + JavaScript (ui/index.html)
│   (UI vrstva)   │  → Odosiela otázky cez REST API
└────────┬────────┘
         │ HTTP POST /api/ask
         ▼
┌─────────────────┐
│   Backend       │  FastAPI server (app.py)
│   (API vrstva)  │  → Prijíma otázky, volá RAG systém
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   RAG Engine    │  LangChain + FAISS (src/rag/ask_cli.py)
│   (Logika)      │  → Vyhľadáva relevantné dokumenty
│                 │  → Generuje odpoveď pomocou LLM
└─────────────────┘
```

---

## 📦 Komponenty a ich zodpovednosti

### 1. **Frontend (`ui/index.html`)**

**Čo robí:**
- Jednoduché HTML rozhranie s textarea pre otázku
- JavaScript kód odosiela otázku na `/api/ask` endpoint
- Zobrazuje odpoveď s Markdown renderovaním

**Technológie:**
- Čistý HTML/CSS/JavaScript
- Marked.js pre Markdown rendering
- Fetch API pre HTTP požiadavky

**Kľúčový kód:**
```javascript
fetch('/api/ask', {
  method: 'POST',
  body: JSON.stringify({question: q})
})
```

---

### 2. **Backend API (`app.py`)**

**Čo robí:**
- FastAPI server poskytuje REST API
- Endpoint `/api/ask` prijíma otázky
- Volá RAG systém a vracia odpovede
- Servuje statické súbory (frontend)

**Kľúčové funkcie:**

#### `run_ai(q: str) -> str`
- Pokúša sa importovať funkciu `ask` z `ask_cli.py`
- Ak zlyhá, spúšťa `ask_cli.py` ako subprocess
- Fallback mechanizmus pre robustnosť

#### `@app.post("/api/ask")`
- REST endpoint pre odosielanie otázok
- Validuje vstup cez Pydantic model `Q`
- Vracia JSON s odpoveďou

**Technológie:**
- FastAPI - moderný Python web framework
- Pydantic - validácia dát
- CORS middleware - povolenie cross-origin požiadaviek

---

### 3. **RAG Engine (`src/rag/ask_cli.py`)**

**Čo robí:**
- Načítava vektorový index (FAISS)
- Vyhľadáva relevantné dokumenty pomocou semantic search
- Filtruje dokumenty podľa úrovní podpory (1-2)
- Generuje odpoveď pomocou LLM (Claude/OpenAI)

**Kľúčové funkcie:**

#### `load_api_keys()`
- Načíta API kľúče z `api_keys.env`
- Nastaví environment premenné

#### `load_url_mapping()`
- Načíta mapovanie URL z `urls.txt`
- Vytvorí slovník pre rýchle vyhľadávanie

#### `resolve_url(doc_meta: dict) -> str`
- Nájde správny URL dokumentu na základe metadát
- Používa rôzne stratégie mapovania

#### Hlavný workflow:
1. **Semantic Search**: `vs.similarity_search(query, k=20)`
   - Používa multilingual-e5-small embeddings
   - Hľadá 20 najrelevantnejších dokumentov

2. **Rozšírené vyhľadávanie**:
   - Extrahuje kľúčové slová z otázky
   - Hľadá dodatočné dokumenty podľa kľúčových slov

3. **Filtrovanie**:
   - Filtruje dokumenty podľa úrovní podpory (1-2)
   - Odstraňuje duplikáty

4. **Generovanie odpovede**:
   - Vytvorí kontext z top 12 dokumentov
   - Pošle systémový prompt + kontext + otázku do LLM
   - Vracia formátovanú odpoveď v Markdown

**Technológie:**
- LangChain - framework pre LLM aplikácie
- FAISS - vektorová databáza (Facebook AI Similarity Search)
- HuggingFace Embeddings - multilingual-e5-small model
- Anthropic Claude / OpenAI GPT - LLM pre generovanie odpovedí

---

### 4. **Index Builder (`src/rag/build_index_e5.py`)**

**Čo robí:**
- Vytvára vektorový index z JSONL súborov
- Rozdeľuje dokumenty na chunky (1400 znakov, prekrytie 200)
- Generuje embeddings pomocou multilingual-e5-small
- Ukladá FAISS index do `rag_index/faiss_e5/`

**Proces:**
1. Načíta dokumenty z `catalog.jsonl`
2. Rozdelí na chunky pomocou `RecursiveCharacterTextSplitter`
3. Vytvorí embeddings pre každý chunk
4. Uloží do FAISS indexu

**Technológie:**
- LangChain Text Splitters
- FAISS vector store
- HuggingFace Embeddings

---

### 5. **Data Processing Pipeline**

#### `src/ingest/10_convert_docling.py`
**Čo robí:**
- Konvertuje HTML súbory na Markdown
- Používa Docling library
- Zachováva štruktúru dokumentov

#### `src/ingest/20_normalize_json.py`
**Čo robí:**
- Normalizuje Markdown súbory do JSONL formátu
- Extrahuje nadpisy a sekcie
- Určuje úrovne podpory (1, 2, 3)
- Hádže URL na základe cesty k súboru

**Funkcie:**
- `extract_title_and_sections()` - extrahuje štruktúru
- `infer_levels()` - určuje úrovne podpory z textu
- `guess_url_hint()` - hádže URL

#### `scripts/bootstrap.sh`
**Čo robí:**
- Automatizuje celý pipeline
- Kontroluje, či je potrebné prestavať index
- Spúšťa všetky kroky v správnom poradí

---

## 🔄 Tok dát (Data Flow)

```
1. HTML súbory (data_raw/)
   ↓
2. Docling konverzia → Markdown (data_processed/md/)
   ↓
3. Normalizácia → JSONL (data_processed/json/catalog.jsonl)
   ↓
4. Vytvorenie embeddings → FAISS index (rag_index/faiss_e5/)
   ↓
5. Semantic search → Relevantné dokumenty
   ↓
6. LLM generovanie → Odpoveď
```

---

## 🎨 Kľúčové technické riešenia

### 1. **Semantic Search**
- Používa multilingual embeddings (e5-small)
- Podporuje slovenčinu a iné jazyky
- Cosine similarity pre vyhľadávanie

### 2. **Chunking Strategy**
- Veľkosť chunku: 1400 znakov
- Prekrytie: 200 znakov
- Zachováva kontext medzi chunkmi

### 3. **Fallback Mechanizmus**
- Ak import funkcie zlyhá, použije subprocess
- Robustnosť pri rôznych prostrediach

### 4. **URL Resolution**
- Viacnásobné stratégie mapovania
- Fallback na konštrukciu URL z cesty

### 5. **Level Filtering**
- Filtruje dokumenty podľa úrovní podpory
- Zameranie na úrovne 1-2 (základné opatrenia)

---

## 🐳 Docker Architektúra

### Multi-stage Build:
1. **builder** - Inštaluje Python závislosti
2. **backend** - Kopíruje backend kód
3. **frontend** - Kopíruje frontend súbory
4. **final** - Spája backend + frontend

### Výhody:
- Menšia veľkosť obrazu
- Rýchlejšia zostava (cache vrstiev)
- Možnosť zostaviť len backend alebo frontend

---

## 📊 Použité technológie

### Backend:
- **Python 3.11**
- **FastAPI** - web framework
- **LangChain** - LLM framework
- **FAISS** - vektorová databáza
- **HuggingFace** - embeddings modely

### Frontend:
- **HTML5** - štruktúra
- **CSS3** - štýly
- **JavaScript (ES6+)** - logika
- **Marked.js** - Markdown rendering

### AI/ML:
- **multilingual-e5-small** - embeddings model
- **Claude 3.5 Sonnet** / **GPT-4o-mini** - LLM modely

### DevOps:
- **Docker** - kontajnerizácia
- **Docker Compose** - orchesterácia

---

## 🔑 Kľúčové súbory a ich úlohy

| Súbor | Úloha |
|-------|-------|
| `app.py` | FastAPI server, REST API endpoint |
| `src/rag/ask_cli.py` | RAG logika, semantic search, LLM generovanie |
| `src/rag/build_index_e5.py` | Vytvorenie vektorového indexu |
| `src/ingest/10_convert_docling.py` | HTML → Markdown konverzia |
| `src/ingest/20_normalize_json.py` | Markdown → JSONL normalizácia |
| `ui/index.html` | Frontend rozhranie |
| `scripts/bootstrap.sh` | Automatizácia pipeline |
| `docker/Dockerfile` | Docker konfigurácia |
| `docker/docker-compose.yml` | Docker Compose konfigurácia |

---

## 💡 Hlavné výhody riešenia

1. **RAG prístup** - Odpovede sú založené na oficiálnych dokumentoch
2. **Multilingual podpora** - Funguje so slovenčinou
3. **Semantic search** - Rozumie významu, nie len kľúčovým slovám
4. **Filtrovanie úrovní** - Zameranie na relevantné opatrenia
5. **Docker kontajnerizácia** - Jednoduché nasadenie
6. **Modulárna architektúra** - Ľahko rozšíriteľné

---

## 🚀 Ako to funguje v praxi

1. **Používateľ zadá otázku** v HTML formulári
2. **Frontend pošle POST request** na `/api/ask`
3. **Backend prijme otázku** a zavolá RAG systém
4. **RAG systém:**
   - Vytvorí embedding otázky
   - Nájde 20 najrelevantnejších dokumentov
   - Filtruje podľa úrovní podpory
   - Vytvorí kontext z top dokumentov
5. **LLM generuje odpoveď** na základe kontextu
6. **Odpoveď sa vráti** ako Markdown a zobrazí sa používateľovi

---

## 📈 Metriky a výkon

- **Embeddings model**: multilingual-e5-small (384 dimenzií)
- **Chunk size**: 1400 znakov
- **Top documents**: 20 → filtrovanie → 12
- **LLM timeout**: 120 sekúnd
- **API response time**: ~5-15 sekúnd (závisí od LLM)

---

## 🎓 Pre prezentáciu

### Čo zdôrazniť:

1. **RAG architektúra** - Kombinácia retrieval + generation
2. **Semantic search** - Rozumie významu, nie len kľúčovým slovám
3. **Multilingual podpora** - Funguje so slovenčinou
4. **Modulárny dizajn** - Každá časť má jasnú úlohu
5. **Docker kontajnerizácia** - Profesionálne nasadenie
6. **Robustnosť** - Fallback mechanizmy

### Demo scenár:

1. Ukážte frontend rozhranie
2. Zadajte otázku o podporných opatreniach
3. Ukážte odpoveď s odkazmi na zdroje
4. Vysvetlite, ako systém našiel relevantné dokumenty
5. Ukážte Docker kontajner v akcii

---

**Pripravené pre prezentáciu:** ✅

