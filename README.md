# BP2026 - Inteligentný agent pre podporu práce špeciálneho pedagóga

RAG (Retrieval-Augmented Generation) systém pre konzultácie v oblasti vzdelávacej podpory na Slovensku. Systém používa AI na základe oficiálnych dokumentov o podporných opatreniach.

## 📋 Obsah

1. [Sťahovanie projektu](#sťahovanie-projektu)
2. [Inštalácia a spustenie](#inštalácia-a-spustenie)
3. [Štruktúra projektu](#štruktúra-projektu)
4. [Skripty a ich funkcie](#skripty-a-ich-funkcie)
5. [Hlavné funkcie a moduly](#hlavné-funkcie-a-moduly)
6. [Docker konfigurácia](#docker-konfigurácia)
7. [Riešenie problémov](#riešenie-problémov)

---

## 📥 Sťahovanie projektu

### Požiadavky

- Python 3.11 alebo novší
- Docker a Docker Compose (pre Docker spustenie)
- Git

### Klonovanie repozitára

```bash
git clone <url-repozitára>
cd bp2026
```

---

## 🚀 Inštalácia a spustenie

### Spôsob 1: Spustenie cez Docker (odporúčané)

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
docker compose version  # alebo docker-compose --version
```

#### Krok 2: Konfigurácia API kľúčov

Vytvorte súbor `docker/.env` s vašimi API kľúčmi:

```bash
cd docker
nano .env
```

Pridajte vaše kľúče:
```env
ANTHROPIC_API_KEY=váš_kľúč_tu
# alebo použite OpenAI:
# OPENAI_API_KEY=váš_kľúč_tu

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

### Spôsob 2: Lokálne spustenie (bez Docker)

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
ANTHROPIC_API_KEY=váš_kľúč_tu
# alebo
OPENAI_API_KEY=váš_kľúč_tu
```

#### Krok 4: Spustenie servera

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

---

## 📁 Štruktúra projektu

```
bp2026/
├── app.py                      # Hlavný FastAPI server
├── requirements.txt            # Python závislosti
├── urls.txt                    # Список URL для завантаження даних (єдине джерело)
├── api_keys.env               # API kľúče (lokálne spustenie)
│
├── src/
│   ├── rag/
│   │   ├── ask_cli.py         # Hlavná RAG logika
│   │   └── build_index_e5.py  # Skript na vytvorenie vektorového indexu
│   └── ingest/
│       ├── 00_wget.sh         # Sťahovanie dát z webu
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
│   ├── build-backend.sh       # Zostavenie len backendu
│   ├── build-frontend.sh      # Zostavenie len frontendu
│   └── build-all.sh           # Zostavenie celého projektu
│
├── scripts/
│   └── bootstrap.sh           # Automatická zostava indexu
│
├── data_raw/                  # Surové dáta (HTML súbory)
├── data_processed/            # Spracované dáta (Markdown, JSONL)
└── rag_index/                 # Vektorový index (FAISS)
```

---

## 🔧 Skripty a ich funkcie

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

---

#### `docker/stop.sh`
**Funkcia:** Zastaví a odstráni Docker kontajner.

**Použitie:**
```bash
bash docker/stop.sh
```

---

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

---

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

---

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

### Data processing skripty

#### `scripts/bootstrap.sh`
**Funkcia:** Automaticky zostaví vektorový index z dát.

**Čo robí:**
1. Kontroluje, či je potrebné prestavať index
2. Odstraňuje nepotrebné súbory z `data_raw` (fonty, statické assety)
3. Spúšťa konverziu HTML → Markdown (`10_convert_docling.py`)
4. Spúšťa normalizáciu → JSONL (`20_normalize_json.py`)
5. Vytvára FAISS index (`build_index_e5.py`)

**Použitie:**
```bash
bash scripts/bootstrap.sh
```

---

#### `src/ingest/00_wget.sh`
**Funkcia:** Sťahuje HTML a PDF súbory z webu podľa `urls.txt`.

**Čo robí:**
- Číta URL z `urls.txt` (по одному URL на рядок)
- Používa `wget` na rekurzívne sťahovanie
- Ukladá súbory do `data_raw/manual/`
- Ignoruje obrázky, CSS, JS súbory
- Підтримує HTML, HTM та PDF формати

**Použitie:**
```bash
bash src/ingest/00_wget.sh
```

**💡 Актуалizácia dát:**
Pre pridanie nových URL jednoducho upravte súbor `urls.txt` - pridajte нові URL по одному на рядок. Potom spustite skript znovu.

---

## 🧩 Hlavné funkcie a moduly

### `app.py` - FastAPI Server

**Hlavné funkcie:**

#### `run_ai(q: str) -> str`
**Funkcia:** Spracováva otázky používateľa a vracia odpoveď z AI.

**Čo robí:**
- Pokúša sa importovať funkciu `ask` z `src/rag/ask_cli.py`
- Ak import zlyhá, spúšťa `ask_cli.py` ako subprocess
- Vracia odpoveď alebo chybovú správu

**Použitie:**
```python
answer = run_ai("Ako pomôcť žiakovi s ADHD?")
```

#### `@app.post("/api/ask")`
**Funkcia:** REST API endpoint pre odosielanie otázok.

**Request:**
```json
{
  "question": "Ako pomôcť žiakovi s ADHD?"
}
```

**Response:**
```json
{
  "answer": "Odpoveď z AI..."
}
```

---

### `src/rag/ask_cli.py` - RAG Systém

**Hlavné funkcie:**

#### `load_api_keys()`
**Funkcia:** Načíta API kľúče z `api_keys.env` súboru.

**Čo robí:**
- Číta `api_keys.env` súbor
- Parsuje riadky vo formáte `KEY=value`
- Nastavuje environment premenné

---

#### `load_url_mapping()`
**Funkcia:** Načíta mapovanie URL z `urls.txt`.

**Čo robí:**
- Číta `urls.txt` súbor
- Vytvára slovník mapovania URL
- Podporuje viacero kľúčov pre jedno URL

**Vracia:** `dict` - slovník mapovania URL

---

#### `resolve_url(doc_meta: dict) -> str`
**Funkcia:** Nájde správny URL na základe metadát dokumentu.

**Parametre:**
- `doc_meta`: Slovník s metadátami dokumentu (obsahuje `url`, `source_file`)

**Vracia:** `str` - URL dokumentu

**Čo robí:**
- Skúša nájsť URL z metadát
- Ak neexistuje, skúša nájsť podľa cesty k súboru
- Používa `URL_MAP` na mapovanie

---

#### `level_ok(meta: dict) -> bool`
**Funkcia:** Kontroluje, či dokument zodpovedá úrovniam podpory 1-3.

**Parametre:**
- `meta`: Slovník s metadátami dokumentu

**Vracia:** `bool` - True ak dokument zodpovedá úrovniam 1, 2 alebo 3

---

#### `compact(txt: str) -> str`
**Funkcia:** Komprimuje text odstránením nadbytočných medzier.

**Parametre:**
- `txt`: Vstupný text

**Vracia:** `str` - Komprimovaný text

---

#### `show_error_with_context(error_msg, docs_list)`
**Funkcia:** Zobrazí chybovú správu spolu s informáciami o nájdených dokumentoch.

**Parametre:**
- `error_msg`: Text chybovej správy
- `docs_list`: Zoznam nájdených dokumentov

---

### `src/rag/build_index_e5.py` - Vytvorenie vektorového indexu

**Funkcia:** Vytvára FAISS vektorový index z JSONL súborov.

**Čo robí:**
1. Načíta dokumenty z `data_processed/json/catalog.jsonl`
2. Rozdelí dokumenty na chunky (veľkosť 1400 znakov, prekrytie 200)
3. Vytvorí embeddings pomocou `intfloat/multilingual-e5-small`
4. Uloží FAISS index do `rag_index/faiss_e5/`

**Použitie:**
```bash
python src/rag/build_index_e5.py
```

---

### `src/ingest/10_convert_docling.py` - Konverzia HTML → Markdown

**Funkcia:** Konvertuje HTML súbory na Markdown pomocou Docling.

**Čo robí:**
1. Nájde všetky HTML súbory v `data_raw/`
2. Konvertuje ich na Markdown pomocou Docling
3. Uloží Markdown súbory do `data_processed/md/`
4. Zachováva štruktúru adresárov

**Použitie:**
```bash
python src/ingest/10_convert_docling.py
```

---

### `src/ingest/20_normalize_json.py` - Normalizácia do JSONL

**Funkcia:** Normalizuje Markdown súbory do JSONL formátu pre RAG systém.

**Čo robí:**
1. Načíta všetky Markdown súbory z `data_processed/md/`
2. Extrahuje nadpis a sekcie
3. Určuje úrovne podpory (1, 2, 3)
4. Hádže URL na základe cesty k súboru
5. Uloží normalizované dáta do `data_processed/json/catalog.jsonl`

**Hlavné funkcie:**

- `clean_text(text: str) -> str` - Čistí text od nepotrebných znakov
- `extract_title_and_sections(md_text: str)` - Extrahuje nadpis a sekcie
- `infer_levels(md_text: str)` - Určuje úrovne podpory z textu
- `guess_url_hint(md_path: Path)` - Hádže URL na základe cesty

**Použitie:**
```bash
python src/ingest/20_normalize_json.py
```

---

## 🐳 Docker konfigurácia

### Multi-stage build

Dockerfile používa multi-stage build s týmito targets:

1. **`builder`** - Inštaluje Python závislosti
2. **`backend`** - Kopíruje backend kód a závislosti
3. **`frontend`** - Kopíruje len súbory z `ui/`
4. **`final`** - Spája backend + frontend

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

---

## 🔍 Riešenie problémov

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

---

### Chyby s API kľúčmi

**Kontrola `.env` súboru:**
```bash
cat docker/.env
```

**Uistite sa, že:**
- API kľúče sú správne nastavené
- Kľúče sú platné a aktívne
- Máte internetové pripojenie

---

### Chyby s modelom

**Kontrola názvu modelu:**
- Pre Anthropic: `claude-3-5-sonnet-20241022` alebo `claude-3-5-haiku-20241022`
- Pre OpenAI: `gpt-4o-mini` alebo `gpt-4o`

**Uistite sa, že:**
- Váš API kľúč má prístup k zvolenému modelu
- Názov modelu je správny

---

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

---

### Port 8000 je obsadený

**Zmena portu v `docker-compose.yml`:**
```yaml
ports:
  - "8001:8000"  # Namiesto 8000:8000
```

---

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

## 📝 Poznámky

- **RAG Index**: Uistite sa, že `rag_index/faiss_e5/` obsahuje zostavený index pred spustením kontajnera.
- **API Kľúče**: Nikdy nekomitujte `api_keys.env` alebo `docker/.env` do Git repozitára.
- **Docker Cache**: Docker automaticky cache-uje vrstvy. Ak `requirements.txt` sa nezmenil, Docker použije cache pri ďalšej zostave.
- **Osobné zostavy**: Môžete zostaviť len backend alebo len frontend pomocou príslušných skriptov pre rýchlejšiu zostavu.

---

## 📚 Ďalšie zdroje

- FastAPI dokumentácia: https://fastapi.tiangolo.com/
- LangChain dokumentácia: https://python.langchain.com/
- Docker dokumentácia: https://docs.docker.com/

---

**Autor:** BP2026 Team  
**Verzia:** 1.0
