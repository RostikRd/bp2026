# BP2026 - Kompletná dokumentácia projektu

## 📋 Obsah

1. [Opis projektu](#opis-projektu)
2. [Architektúra systému](#architektúra-systému)
3. [Inštalácia a spustenie](#inštalácia-a-spustenie)
4. [Pipeline spracovania dát](#pipeline-spracovania-dát)
5. [Technické detaily](#technické-detaily)
6. [Použité technológie](#použité-technológie)
7. [Štruktúra projektu](#štruktúra-projektu)
8. [Použitie systému](#použitie-systému)
9. [Riešenie problémov](#riešenie-problémov)

---

## Opis projektu

**Názov:** BP2026 - Inteligentný agent pre podporu práce špeciálneho pedagóga

**Typ projektu:** RAG (Retrieval-Augmented Generation) systém pre konzultácie v oblasti vzdelávacej podpory na Slovensku

**Účel:** Systém používa umelú inteligenciu na základe oficiálnych dokumentov o podporných opatreniach na poskytovanie konzultácií špeciálnym pedagógom. Systém pracuje s katalógom podporných opatrení z portálu podporneopatrenia.minedu.sk a poskytuje overiteľné odpovede na základe týchto dokumentov.

**Kľúčové vlastnosti:**
- Sémantické vyhľadávanie dokumentov
- Generovanie odpovedí na základe oficiálnych zdrojov
- Podpora slovenčiny
- Filtrovanie podľa úrovní podpory (1-3)
- Docker kontajnerizácia
- REST API pre integráciu

---

## Architektúra systému

### 3-vrstvová architektúra

```
┌─────────────────────┐
│   Frontend Layer    │  HTML + JavaScript (ui/index.html)
│   (UI vrstva)       │  → Odosiela požiadavky cez REST API
└──────────┬──────────┘
           │ HTTP POST /api/ask
           ▼
┌─────────────────────┐
│   Backend Layer     │  FastAPI server (app.py)
│   (API vrstva)      │  → Prijíma požiadavky, volá RAG systém
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   RAG Engine        │  LangChain + FAISS (src/rag/ask_cli.py)
│   (Logika)          │  → Hľadá relevantné dokumenty
│                     │  → Generuje odpoveď pomocou LLM
└─────────────────────┘
```

### Komponenty systému

#### 1. Frontend (`ui/index.html`)
- Jednoduché HTML rozhranie s textarea pre požiadavky
- JavaScript kód odosiela požiadavky na `/api/ask` endpoint
- Zobrazovanie odpovedí s Markdown renderovaním
- Používa Marked.js pre renderovanie Markdown

#### 2. Backend API (`app.py`)
- FastAPI server poskytuje REST API
- Endpoint `/api/ask` prijíma požiadavky
- Volá RAG systém a vracia odpovede
- Obsluhuje statické súbory (frontend)

**Kľúčové funkcie:**
- `run_ai(q: str) -> str` - spracovanie požiadaviek cez RAG systém
- `@app.post("/api/ask")` - REST endpoint pre odosielanie požiadaviek

#### 3. RAG Engine (`src/rag/ask_cli.py`)
- Načítava vektorový index (FAISS)
- Hľadá relevantné dokumenty cez sémantické vyhľadávanie
- Filtruje dokumenty podľa úrovní podpory (1-3)
- Generuje odpovede pomocou LLM (Claude/OpenAI)

**Proces práce:**
1. **Semantic Search**: Vytvorí embedding požiadavky, hľadá 20 najrelevantnejších dokumentov
2. **Rozšírené vyhľadávanie**: Automaticky pridáva kľúčové slová na základe požiadavky
3. **Filtrovanie**: Filtruje dokumenty podľa úrovní podpory, odstraňuje duplikáty
4. **Generovanie**: Vytvorí kontext z top-12 dokumentov, odošle do LLM
5. **Formátovanie**: Vráti štruktúrovanú odpoveď so zdrojmi

**Kľúčové funkcie:**
- `load_api_keys()` - načítava API kľúče z `api_keys.env`
- `load_url_mapping()` - načítava mapovanie URL z `urls.txt`
- `resolve_url(doc_meta: dict) -> str` - nájde správny URL dokumentu
- `level_ok(meta: dict) -> bool` - filtruje dokumenty podľa úrovní podpory

---

## Inštalácia a spustenie

### Požiadavky

- Python 3.11 alebo novší
- Docker a Docker Compose (pre Docker spustenie)
- Git

### Variant 1: Spustenie cez Docker (odporúčané)

#### Krok 1: Inštalácia Docker

**Pre WSL Ubuntu:**

**Variant A: Docker Desktop for Windows (odporúčané)**
1. Stiahnite Docker Desktop: https://www.docker.com/products/docker-desktop
2. Nainštalujte na Windows
3. Otvorte Docker Desktop → Settings → Resources → WSL Integration
4. Povolte pre váš Ubuntu distributív
5. Reštartujte WSL: `wsl --shutdown` (v PowerShell na Windows)

**Variant B: Docker Engine priamo v WSL**
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker $USER
# Reštartujte WSL po tomto
```

**Kontrola:**
```bash
docker --version
docker compose version
```

#### Krok 2: Konfigurácia API kľúčov

Vytvorte súbor `docker/.env` s vašimi API kľúčmi:

```bash
cd docker
nano .env
```

Pridajte vaše kľúče:
```env
ANTHROPIC_API_KEY=vaš_kľúč_tu
# alebo použite OpenAI:
# OPENAI_API_KEY=vaš_kľúč_tu

# Voliteľné nastavenia modelov
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
OPENAI_MODEL=gpt-4o-mini
EMBED_MODEL=intfloat/multilingual-e5-small
```

#### Krok 3: Spustenie

```bash
# Z koreňovej adresára projektu
bash docker/start.sh
```

Skript automaticky:
- Skontroluje prítomnosť Docker
- Vytvorí `.env` súbor (ak je potrebné)
- Zostaví Docker obraz
- Spustí kontajner

#### Krok 4: Prístup k aplikácii

Otvorte v prehliadači:
- **Hlavná stránka**: http://localhost:8000
- **API dokumentácia**: http://localhost:8000/docs

### Variant 2: Lokálne spustenie (bez Docker)

#### Krok 1: Vytvorenie virtuálneho prostredia

```bash
python3 -m venv .venv
source .venv/bin/activate  # Na Windows: .venv\Scripts\activate
```

#### Krok 2: Inštalácia závislostí

```bash
pip install -r requirements.txt
```

#### Krok 3: Konfigurácia API kľúčov

Vytvorte súbor `api_keys.env` v koreňovom adresári:

```env
ANTHROPIC_API_KEY=vaš_kľúč_tu
# alebo
OPENAI_API_KEY=vaš_kľúč_tu
```

#### Krok 4: Spustenie servera

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

---

## Pipeline spracovania dát

### Úplný pipeline

```
urls.txt → 00_wget.sh → HTML/PDF súbory (data_raw/)
    ↓
10_convert_docling.py → Markdown súbory (data_processed/md/)
    ↓
20_normalize_json.py → catalog.jsonl (normalizované dáta)
    ↓
build_index_e5.py → FAISS index (vektorová databáza)
    ↓
app.py → FastAPI server → Web rozhranie
    ↓
Používateľ → Otázka → Semantic search → AI → Odpoveď
```

### Detailný opis krokov

#### Krok 1: Príprava dát

**Pridanie URL do `urls.txt`**
- Pridajte URL adresy stránok, ktoré chcete spracovať
- Každý URL na samostatný riadok
- Môžete pridať komentáre (riadky začínajúce s `#`)

#### Krok 2: Sťahovanie dát (`00_wget.sh`)

```bash
bash src/ingest/00_wget.sh
```

**Čo robí:**
- Číta URL z `urls.txt`
- Používa `wget` na rekurzívne sťahovanie
- Ukladá HTML a PDF súbory do `data_raw/manual/`
- Ignoruje obrázky, CSS, JS súbory
- Podporuje HTML, HTM a PDF formáty

#### Krok 3: Konverzia na Markdown (`10_convert_docling.py`)

```bash
python src/ingest/10_convert_docling.py
```

**Čo robí:**
- Nájde všetky HTML a PDF súbory v `data_raw/`
- Konvertuje ich na Markdown pomocou Docling
- Uloží Markdown súbory do `data_processed/md/`
- Zachováva štruktúru adresárov

#### Krok 4: Normalizácia do JSONL (`20_normalize_json.py`)

```bash
python src/ingest/20_normalize_json.py
```

**Čo robí:**
- Načíta všetky Markdown súbory z `data_processed/md/`
- Rozdelí na sekcie
- Vytvorí JSONL súbor (`catalog.jsonl`) s normalizovanými dátami
- Automaticky určí úrovne podpory (1, 2, 3) pre každý dokument
- Hádže URL na základe cesty k súboru

**Hlavné funkcie:**
- `clean_text(text: str) -> str` - čistí text od nepotrebných znakov
- `extract_title_and_sections(md_text: str)` - extrahuje nadpis a sekcie
- `infer_levels(md_text: str)` - určuje úrovne podpory z textu
- `guess_url_hint(md_path: Path)` - hádže URL na základe cesty

#### Krok 5: Vytvorenie vektorového indexu (`build_index_e5.py`)

```bash
python src/rag/build_index_e5.py
```

**Čo robí:**
- Načíta dokumenty z `data_processed/json/catalog.jsonl`
- Rozdelí dokumenty na menšie chunks (1400 znakov, prekrytie 200)
- Vytvorí embeddings (vektorové reprezentácie) textu pomocou multilingual-e5-small modelu
- Vytvorí FAISS vektorový index v `rag_index/faiss_e5/`

**Technické parametre:**
- Embeddings model: `intfloat/multilingual-e5-small` (384 dimenzie)
- Veľkosť chunk: 1400 znakov
- Prekrytie chunk: 200 znakov

#### Krok 6: Spustenie aplikácie

**Lokálne:**
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

**Cez Docker:**
```bash
bash docker/start.sh
```

### Automatizácia

Namiesto manuálneho spúšťania krokov 3-5 môžete použiť:

```bash
bash scripts/bootstrap.sh
```

Tento skript automaticky:
- Skontroluje, či je potrebné prestavať index
- Odstráni nepotrebné súbory z `data_raw` (fonty, statické assety)
- Spustí všetky potrebné konverzie
- Vytvorí nový FAISS index

---

## Technické detaily

### RAG architektúra

**Retrieval-Augmented Generation (RAG)** - architektúra, ktorá kombinuje vyhľadávanie v znalostnej báze s generovaním textu pomocou veľkých jazykových modelov (LLM).

**Hlavné komponenty RAG:**

1. **Indexing (Indexácia)**
   - Príprava dokumentov
   - Chunking (rozdelenie na časti)
   - Vytvorenie embeddings
   - Uloženie do vektorovej databázy

2. **Retrieval (Vyhľadávanie)**
   - Vytvorenie embedding požiadavky
   - Sémantické vyhľadávanie podobných dokumentov
   - Filtrovanie podľa metadát
   - Rozšírené vyhľadávanie podľa kľúčových slov

3. **Generation (Generovanie)**
   - Príprava kontextu z top dokumentov
   - Vytvorenie systémového promptu
   - Generovanie odpovede cez LLM
   - Post-processing a pridanie citácií

### Sémantické vyhľadávanie

**Dense Retrieval** používa vektorové reprezentácie textu, kde požiadavka aj dokumenty sú reprezentované ako vektory vo vysokorozmernom priestore. Podobnosť medzi požiadavkou a dokumentmi sa meria pomocou cosine similarity.

**Proces:**
1. Vytvorenie embedding požiadavky pomocou embedding modelu
2. Vyhľadanie k najpodobnejších chunks z vektorovej databázy
3. Rozšírenie vyhľadávania podľa kľúčových slov
4. Filtrovanie podľa metadát (úrovne podpory)
5. Výber top-12 najrelevantnejších dokumentov

### Stratégia chunking

- **Veľkosť chunk**: 1400 znakov
- **Prekrytie**: 200 znakov
- **Cieľ**: Zachovanie kontextu medzi chunks

### Filtrovanie podľa úrovní podpory

Systém filtruje dokumenty podľa úrovní podpory (1, 2, 3):
- Úroveň 1: Základné opatrenia podpory
- Úroveň 2: Špecializované opatrenia
- Úroveň 3: Intenzívne opatrenia

Funkcia `level_ok()` kontroluje, či dokument zodpovedá potrebným úrovniam.

### Rozšírené vyhľadávanie

Systém automaticky pridáva relevantné termíny na základe požiadavky:
- **ADHD** → pozornosť, sústredenie, organizácia, časové signály
- **Matematika** → matematické úlohy, počítanie
- **Čítanie** → čítanie s porozumením, pravopis
- **ASD** → vizuálne rozvrhy, prechodové rituály
- A ďalšie kategórie...

### Generovanie odpovedí

**Proces:**
1. Vytvorenie kontextu z top-12 dokumentov (chunks do 1000 znakov)
2. Nájdenie správnych URL pre každý dokument cez `resolve_url()`
3. Odoslanie systémového promptu + kontextu + požiadavky do AI (Claude/GPT)
4. Vrátenie štruktúrovanej odpovede so zdrojmi (číslo, názov, URL)

**AI modely:**
- Podporuje Anthropic Claude (3.5 Sonnet, Haiku)
- Podporuje OpenAI GPT (gpt-4o-mini)
- Automatický fallback na alternatívne modely pri chybách
- Retry logika pri preťažení API

---

## Použité technológie

### Backend

- **Python 3.11+** - hlavný jazykový stack
- **FastAPI** - moderný web framework pre Python
- **Uvicorn** - ASGI server pre spustenie FastAPI
- **LangChain** - framework pre prácu s LLM
  - `langchain` - hlavný framework
  - `langchain-community` - dodatočné integrácie
  - `langchain-huggingface` - integrácia s HuggingFace modelmi
  - `langchain-text-splitters` - rozdelenie textov na chunks
  - `langchain-anthropic` - integrácia s Anthropic Claude
  - `langchain-openai` - integrácia s OpenAI GPT
- **FAISS** (faiss-cpu) - vektorová databáza pre sémantické vyhľadávanie
- **HuggingFace Embeddings** - model `intfloat/multilingual-e5-small` (384 dimenzie)
- **LLM cez API:**
  - Anthropic Claude 3.5 Sonnet/Haiku
  - OpenAI GPT-4o-mini/GPT-4o
- **Docling** (>= 2.1.0) - konverzia HTML/PDF → Markdown
- **Pydantic** - validácia dát pre FastAPI
- **Dodatočné knižnice:**
  - `rich` - formátovanie výstupu
  - `numpy` - matematické operácie
  - `tqdm` - progress bary
  - `python-dotenv` - práca s .env súbormi
  - `sentence-transformers` - embeddings modely

### Frontend

- **HTML5** - štruktúra webového rozhrania
- **CSS3** - štýlovanie rozhrania
- **JavaScript (ES6+)** - klientska logika
- **Marked.js** - renderovanie Markdown (cez CDN)

### DevOps

- **Docker** - kontajnerizácia aplikácie
- **Docker Compose** - orchestrácia kontajnerov
- **Shell skripty** - automatizácia procesov

### Spracovanie dát

- **Wget** - sťahovanie HTML/PDF súborov
- **JSONL formát** - ukladanie normalizovaných dát
- **Markdown** - medziformát pre spracovanie dokumentov

---

## Štruktúra projektu

```
bp2026/
├── app.py                      # Hlavný FastAPI server
├── requirements.txt            # Python závislosti
├── urls.txt                    # Zoznam URL pre sťahovanie dát
├── api_keys.env               # API kľúče (lokálne spustenie)
│
├── src/
│   ├── rag/
│   │   ├── ask_cli.py         # Hlavná RAG logika
│   │   └── build_index_e5.py  # Skript na vytvorenie vektorového indexu
│   └── ingest/
│       ├── 00_wget.sh         # Sťahovanie dát z webových stránok
│       ├── 10_convert_docling.py  # Konverzia HTML → Markdown
│       └── 20_normalize_json.py  # Normalizácia → JSONL
│
├── ui/
│   └── index.html             # Frontend rozhranie
│
├── docker/
│   ├── Dockerfile             # Docker konfigurácia
│   ├── docker-compose.yml     # Docker Compose konfigurácia
│   ├── start.sh               # Skript na spustenie
│   ├── stop.sh                # Skript na zastavenie
│   ├── build-backend.sh       # Zostavenie len backend
│   ├── build-frontend.sh      # Zostavenie len frontend
│   └── build-all.sh           # Zostavenie celého projektu
│
├── scripts/
│   └── bootstrap.sh           # Automatická zostava indexu
│
├── data_raw/                  # Surové dáta (HTML súbory)
├── data_processed/            # Spracované dáta (Markdown, JSONL)
└── rag_index/                 # Vektorový index (FAISS)
```

### Kľúčové súbory a ich úlohy

| Súbor | Úloha |
|-------|-------|
| `app.py` | FastAPI server, REST API endpoint |
| `src/rag/ask_cli.py` | RAG logika, sémantické vyhľadávanie, generovanie cez LLM |
| `src/rag/build_index_e5.py` | Vytvorenie vektorového indexu |
| `src/ingest/10_convert_docling.py` | HTML → Markdown konverzia |
| `src/ingest/20_normalize_json.py` | Markdown → JSONL normalizácia |
| `ui/index.html` | Frontend rozhranie |
| `scripts/bootstrap.sh` | Automatizácia pipeline |
| `docker/Dockerfile` | Docker konfigurácia |
| `docker/docker-compose.yml` | Docker Compose konfigurácia |

---

## Použitie systému

### Cez webové rozhranie

1. Otvorte http://localhost:8000 v prehliadači
2. Zadajte vašu otázku do textového poľa
3. Kliknite na tlačidlo "Opýtať sa"
4. Získajte odpoveď so zdrojmi

### Cez API

**Endpoint:** `POST /api/ask`

**Request:**
```json
{
  "question": "Ako pomôcť žiakovi s ADHD?"
}
```

**Response:**
```json
{
  "answer": "Odpoveď z AI s citáciami..."
}
```

### Príklad práce systému

Keď používateľ zadá otázku:

1. **Načítanie API kľúčov** z `api_keys.env`
2. **Načítanie mapovania URL** z `urls.txt`
3. **Vytvorenie embedding otázky** pomocou multilingual-e5-small modelu
4. **Vyhľadanie najrelevantnejších dokumentov** v FAISS indexe (sémantické vyhľadávanie, k=20)
5. **Rozšírenie vyhľadávania** pomocou kľúčových slov (ADHD, matematika, čítanie, atď.)
6. **Odstránenie duplikátov** dokumentov
7. **Filtrovanie podľa úrovní podpory** (1-3) cez `level_ok()`
8. **Výber top-12 najrelevantnejších dokumentov**
9. **Vytvorenie kontextu** z vybraných dokumentov (chunks do 1000 znakov)
10. **Nájdenie správnych URL** pre každý dokument cez `resolve_url()`
11. **Odoslanie systémového promptu + kontextu + otázky** do AI (Claude/GPT)
12. **Vrátenie štruktúrovanej odpovede** so zdrojmi (číslo, názov, URL)

---

## Riešenie problémov

### Kontajner sa nespúšťa

**Kontrola logov:**
```bash
cd docker
docker-compose logs
```

**Kontrola RAG indexu:**
```bash
ls -la rag_index/faiss_e5/
```

### Chyby s API kľúčmi

**Kontrola `.env` súboru:**
```bash
cat docker/.env
```

**Uistite sa, že:**
- API kľúče sú správne nastavené
- Kľúče sú platné a aktívne
- Máte internetové pripojenie

### Chyby s modelom

**Kontrola názvu modelu:**
- Pre Anthropic: `claude-3-5-sonnet-20241022` alebo `claude-3-5-haiku-20241022`
- Pre OpenAI: `gpt-4o-mini` alebo `gpt-4o`

**Uistite sa, že:**
- Váš API kľúč má prístup k zvolenému modelu
- Názov modelu je správny

### RAG index neexistuje

**Vytvorenie indexu:**
```bash
bash scripts/bootstrap.sh
```

Alebo manuálne:
```bash
python src/ingest/10_convert_docling.py
python src/ingest/20_normalize_json.py
python src/rag/build_index_e5.py
```

### Port 8000 je obsadený

**Zmena portu v `docker-compose.yml`:**
```yaml
ports:
  - "8001:8000"  # Namiesto 8000:8000
```

### Docker-compose: command not found

**Pre nový Docker:**
```bash
docker compose build  # Bez pomlčky
docker compose up -d
```

**Alebo inštalácia docker-compose:**
```bash
sudo apt-get install docker-compose
```

---

## Docker konfigurácia

### Multi-stage build

Dockerfile používa multi-stage build s týmito targets:

1. **`builder`** - inštaluje Python závislosti
2. **`backend`** - kopíruje backend kód a závislosti
3. **`frontend`** - kopíruje len súbory z `ui/`
4. **`final`** - spája backend + frontend

### Čo je zahrnuté v Docker obraze

✅ Backend (FastAPI) - `app.py` a `src/rag/ask_cli.py`  
✅ Frontend (UI) - priečinok `ui/` s HTML  
✅ Python závislosti z `requirements.txt`  
✅ RAG index (`rag_index/faiss_e5/`)  
✅ URL mapovanie (`urls.txt`)

### Čo je vylúčené

❌ `.venv/` - virtuálne prostredie (inštaluje sa v kontajneri)  
❌ `data_raw/` - surové dáta (nepotrebné pre runtime)  
❌ `data_processed/` - spracované dáta (nepotrebné ak je index už zostavený)  
❌ `src/ingest/` - skripty na spracovanie dát  
❌ `scripts/` - bootstrap skripty  
❌ `api_keys.env` - prenáša sa cez environment premenné

### Docker Compose príkazy

```bash
# Zostavenie obrazu
cd docker
docker-compose build

# Spustenie kontajnera
docker-compose up -d

# Zobrazenie logov
docker-compose logs -f

# Zastavenie kontajnera
docker-compose down

# Reštart kontajnera
docker-compose restart
```

### Docker skripty

#### `docker/start.sh`
**Funkcia:** Spustí Docker kontajner s aplikáciou.

**Čo robí:**
- Kontroluje prítomnosť Docker
- Vytvára `.env` súbor ak neexistuje
- Zostavuje Docker obraz ak je potrebné
- Spúšťa kontajner na porte 8000

**Použitie:**
```bash
bash docker/start.sh
```

#### `docker/stop.sh`
**Funkcia:** Zastaví a odstráni Docker kontajner.

**Použitie:**
```bash
bash docker/stop.sh
```

#### `docker/build-backend.sh`
**Funkcia:** Zostaví len backend časť (Python kód, RAG logika).

**Kedy použiť:**
- Zmenili ste `app.py`, `src/rag/ask_cli.py`, `requirements.txt`
- Pridali ste nové Python závislosti
- Zmenili ste RAG logiku

**Použitie:**
```bash
bash docker/build-backend.sh
```

#### `docker/build-frontend.sh`
**Funkcia:** Zostaví len frontend časť (HTML súbory).

**Kedy použiť:**
- Zmenili ste súbory v `ui/` (HTML, CSS, JS)
- Aktualizovali ste štýly alebo rozhranie
- Pridali ste nové stránky

**Použitie:**
```bash
bash docker/build-frontend.sh
```

#### `docker/build-all.sh`
**Funkcia:** Zostaví celý projekt (backend + frontend).

**Kedy použiť:**
- Prvá zostava
- Zmenili ste aj backend aj frontend
- Chcete úplnú prestavbu

**Použitie:**
```bash
bash docker/build-all.sh
```

---

## Metriky a charakteristiky systému

### Technické parametre

- **Embeddings model:** multilingual-e5-small (384 dimenzie)
- **Veľkosť chunk:** 1400 znakov
- **Prekrytie chunks:** 200 znakov
- **Top dokumentov:** 20 → filtrovanie → 12
- **LLM timeout:** 120 sekúnd
- **Čas odozvy API:** ~5-15 sekúnd (závisí od LLM)

### Architektonické riešenia

- Multi-stage Docker build
- REST API architektúra
- Modulárna štruktúra kódu
- Rozdelenie spracovania dát a runtime

---

## Dôležité poznámky

- **RAG Index**: Uistite sa, že `rag_index/faiss_e5/` obsahuje zostavený index pred spustením kontajnera.
- **API Kľúče**: Nikdy nekomitujte `api_keys.env` alebo `docker/.env` do Git repozitára.
- **Docker Cache**: Docker automaticky cache-uje vrstvy. Ak `requirements.txt` sa nezmenil, Docker použije cache pri ďalšej zostave.
- **Osobné zostavy**: Môžete zostaviť len backend alebo len frontend pomocou príslušných skriptov pre rýchlejšiu zostavu.

---

## Ďalšie zdroje

- FastAPI dokumentácia: https://fastapi.tiangolo.com/
- LangChain dokumentácia: https://python.langchain.com/
- Docker dokumentácia: https://docs.docker.com/
- FAISS dokumentácia: https://github.com/facebookresearch/faiss
- HuggingFace: https://huggingface.co/
- Anthropic Claude: https://docs.anthropic.com/
- OpenAI: https://platform.openai.com/docs

---

**Autor:** BP2026 Team  
**Verzia:** 1.0  
**Dátum:** 2024
