# Bakalárska práca - Inteligentný agent pre podporu práce špeciálneho pedagóga (SK)
## O projekte
BP2026 – je webová aplikácia pre lokálne použitie s RAG (Retrieval-Augmented Generation) pre konzultácie špeciálnych pedagógov: odpovedá na otázky na základe oficiálneho katalógu podporných opatrení <https://podporneopatrenia.minedu.sk/> a v prípade potreby čerpá informácie z internetu. Používateľ zadá otázku v slovenčine. Systém vyhľadá relevantné fragmenty v indexovaných dokumentoch (FAISS), doplní kontext vyhľadávaním na webe a vygeneruje odpoveď prostredníctvom Claude-API (Anthropic) s odkazmi na zdroje. K otázke môžete priložiť vlastný PDF súbor alebo obrázok – ich text sa pridá do kontextu spolu s katalógom. Prístup k rozhraniu a histórii odpovedí je chránený jednoduchou autorizáciou.
## Štruktúra projektu a stručný popis 

```
bp2026/
├── app.py                      # FastAPI hlavný server
├── requirements.txt            # Python závislosti
├── urls.txt                    # Zoznam URL adries na stiahnutie údajov
├── api_keys.env                # API-kľúče
│
├── docker/
│   ├── Dockerfile              # Obrazu programu
│   └── docker-compose.yml      # Spustenie kontajnera
│
├── docs/
│   └── test_questions.md       # Testové otázky pre agenta
│
├── evaluation/
│   ├── dataset.json             #dataset otazok pre hodnotenia
│   ├── evaluate.py              #skript na hodnotenia
│   └── results/
│       ├── eval_20260220_191145.json
│       └── evaluation_report.md
│
├── src/
│   ├── config.py               # Všeobecná konfigurácia (cesty, nahrané súbory)
│   ├── auth_db.py              # Databáza používateľov / autorizácia
│   ├── documents_db.py         # Databáza dokumentov nahraných používateľmi
│   ├── saved_db.py             # Databáza uložených odpovedí (história)
│   ├── docling_extract.py      # Extrahovanie textu z PDF/obrázkov (nahratie)
│   │
│   ├── ingest/
│   │   ├── 00_wget.sh          # Stiahnuť HTML/PDF z urls.txt → data_raw/
│   │   ├── 10_convert_docling.py   # Konverzia HTML/PDF → Markdown
│   │   └── 20_normalize_json.py    # Markdown → catalog.jsonl
│   │
│   └── rag/
│       ├── ask_cli.py           # Logika RAG: vyhľadávanie, kontext, volanie Claude
│       └── build_index_e5.py    # Vytvorenie indexu FAISS z catalog.jsonl
│
├── ui/
│   ├── html/
│   │   ├── index.html          # Home stránka
│   │   ├── auth.html           # Authorization stránka
│   │   └── welcome.html        # Welcome stránka
│   ├── css/
│   │   └── style.css           # Štýly
│   ├── js/
│   │   └── main.js             # Logika rozhrania (otázky, dokumenty, ukladanie)
│   └── assets/
│       └── logo_named.png      # Logo
│
├── data_raw/                   # Raw data (HTML, PDF) — výsledok wget
├── data_processed/             # Spracované údaje
│   ├── md/                     # Markdown after 10_convert_docling.py
│   └── json/
│       └── catalog.jsonl       # Normalizovaný katalóg po 20_normalize_json.py
│
├── rag_index/                  # FAISS index (after build_index_e5.py)
├── uploads/                    # Files uploaded by the user
└── db/                         # SQLite (auth, documents, saved)
```
## Ako to funguje?
__1. Príprava údajov__

Tento krok sa nevykonáva v prehliadači, ale v termináli na počítači, kde je projekt nasadený.

* **`urls.txt`** — do súboru sa pridajú odkazy na stránky katalógu (napr. podporneopatrenia.minedu.sk).

* **`00_wget.sh`** — skript stiahne súbory HTML a PDF z týchto URL adries do adresára `data_raw/` (napr. `data_raw/manual/`).

* **`10_convert_docling.py`** — všetky súbory HTML/PDF nachádzajúce sa v `data_raw/` sú konvertované na Markdown a uložené v `data_processed/md/` s rovnakou relatívnou cestou.

* **`20_normalize_json.py`** — Markdown je rozdelený do sekcií, sú pridané metadáta (úrovne podpory, URL adresy) a je vytvorený jeden veľký súbor `data_processed/json/catalog.jsonl`..

* **`build_index_e5.py`** — skript číta súbor `catalog.jsonl`, rozdelí text na časti, vypočíta pre ne vektorové reprezentácie (vloženia) pomocou modelu E5 a uloží **index FAISS** do `rag_index/`. Tento index sa používa na sémantické vyhľadávanie pri odpovediach na otázky.

Po dokončení týchto krokov má projekt pripravený katalóg a index. Môžete spustiť webovú aplikáciu..

__2. Práca s aplikáciou: od otázky k odpovedi__

 **Používateľ** otvorí webovú stránku. Ak nie je prihlásený, zobrazí sa mu uvítacie okno a prihlasovací/registračný formulár. Po úspešnom prihlásení sa dostane na **dashboard** (hlavnú stránku s AI asistentom).

 **Voliteľné:** používateľ môže nahrať súbor PDF alebo obrázok (tlačidlo „Nahrať“ v bloku „Priložiť dokument“). Súbor sa uloží na server, text sa z neho extrahuje pomocou **Docling** (`docling_extract.py`) a uloží sa do databázy dokumentov. V zozname sa zobrazí nový dokument. Je možné ho vybrať ako kontext pre ďalšiu otázku (alebo sa vyberie automaticky po nahratí).

**Používateľ zadá otázku** a klikne na „Odoslať otázku”. Text otázky a (ak je vybrané) `document_id` sa odošle na server v požiadavke.

**Server (`app.py`)**:
   - kontroluje reláciu (či je používateľ prihlásený);
   - ak existuje `document_id`, stiahne text tohto súboru pre aktuálneho používateľa z databázy dokumentov;
   - volá **`run_ai(question, document_context=...)`**.

**`run_ai`** odovzdáva kontrolu **RAG** (`ask_cli.ask`). Predvolene sa volanie vykonáva prostredníctvom **subprocesu** (samostatného procesu Python) s cieľom izolovať pamäť a chyby. Túto funkciu môžete deaktivovať pomocou `USE_SUBPROCESS=false` a volať `ask` priamo.

**RAG (`ask_cli.ask`)**:
   - ak je odovzdaný text priloženého dokumentu, pridá ho do kontextu (spolu s katalógom a webom);
   - načíta **index FAISS** a vykoná **sémantické vyhľadávanie** otázky (a kľúčových slov);
   - zhromažďuje relevantné fragmenty dokumentov do jedného kontextu s tagmi [D1], [D2], ...;
   - rozhoduje: či je dostatok dokumentov na odpoveď alebo je potrebné **webové vyhľadávanie** (Anthropic Tools / internetové vyhľadávanie);
   - generuje **systémové a užívateľské výzvy** a volá **Claude** (Anthropic);
   - prijme odpoveď, v prípade potreby pridá sekcie „Zdroje“ a „Overenie v internete“ a vráti text.

   **Server** prijme tento text, vytvorí **návrh** v databáze (otázka + odpoveď) a vráti **odpoveď** a **`draft_id`** klientovi.

**Prehliadač** zobrazí odpoveď (Markdown render). Tlačidlo „Uložiť odpoveď“ sa stane aktívnym: po kliknutí sa odošle **`draft_id`** a server prenesie tento návrh do tabuľky **uložené** (história). V sekcii „História otázok“ používateľ vidí všetky uložené páry otázok a odpovedí a môže ich rozbaliť a odstrániť.

__3. Autorizácia__
- **Registrácia/prihlásenie** — prostredníctvom `/api/register` a `/api/login`. Heslo je uložené ako hash. Po úspešnom prihlásení sa `užívateľské meno` zaznamená do relácie.
- **Middleware** kontroluje každú požiadavku: pre cesty ako `/dashboard`, `/api/ask`, `/api/documents`, `/api/saved` je potrebná relácia. Ak relácia neexistuje, vráti sa 401 alebo presmerovanie na domovskú stránku.
- Všetky údaje (dokumenty, koncepty, uložené odpovede) sú prepojené s **user_id**, takže jeden používateľ nemôže vidieť dokumenty a históriu iných používateľov.



## Spustenie projektu

__1.Požiadavky__

- Python 3.11+
- Git
- (voliteľne) Docker + Docker Compose

__2.Klonovanie repozitára__

```bash
git clone <URL_REPOZITARA>
cd bp2026
```

__3.Lokálne spustenie__

Vytvor virtuálne prostredie a aktivuj ho:

```bash
python -m venv .venv
source .venv/bin/activate
```

Nainštaluj závislosti:

```bash
pip install -r requirements.txt
```

V koreňovom adresári vytvor súbor `api_keys.env` a doplň minimálne:

```env
ANTHROPIC_API_KEY=...
# voliteľne:
# ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
# SESSION_SECRET=...
```

Ak ešte nemáš pripravený index `rag_index/faiss_e5`, spusti:

```bash
python src/ingest/10_convert_docling.py
python src/ingest/20_normalize_json.py
python src/rag/build_index_e5.py
```

Spusť aplikáciu:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Otvor v prehliadači:

- `http://localhost:8000`
- API dokumentácia: `http://localhost:8000/docs`

__3.Spustenie cez Docker__

Prejdi do priečinka `docker`:

```bash
cd docker
```

Vytvor `docker/.env` (podľa `docker-compose.yml`) a nastav premenné:

```env
ANTHROPIC_API_KEY=...
SESSION_SECRET=...
```

Spusť kontajner:

```bash
docker compose up --build
```

Aplikácia bude dostupná na:

- `http://localhost:8000`

__4.Rýchly test evaluácie__

```bash
python evaluation/evaluate.py --ids 4 5
```

Výsledky sa ukladajú do `evaluation/results/`.
________
# Bachelor thesis - Intelligent agent for supporting the work of special educators (en)
## About the project
BP2026 - is a web application for local use with RAG (Retrieval-Augmented Generation) for consulting special educators: it answers questions based on the official catalog of support measures <https://podporneopatrenia.minedu.sk/> and, if necessary, pulls information from the Internet. The user enters a question in Slovak. The system searches for relevant fragments in indexed documents (FAISS), supplements the context with a web search, and generates a response via Claude-API (Anthropic) with links to sources. You can attach your own PDF or image to the question — their text is added to the context along with the catalog. Access to the interface and response history is protected by simple authorization.
## Project structure and short description 

```
bp2026/
├── app.py                      # FastAPI main server
├── requirements.txt            # Python dependencies
├── urls.txt                    # List of URLs for data download
├── api_keys.env                # API-keys
│
├── docker/
│   ├── Dockerfile              # Program image assembly
│   └── docker-compose.yml      # Container launch
│
├── docs/
│   └── test_questions.md       # Test questions for agent
│
├── evaluation/
│   ├── dataset.json             #dataset for evaluate
│   ├── evaluate.py              #script for evaluate
│   └── results/
│       ├── eval_20260220_191145.json
│       └── evaluation_report.md
│
├── src/
│   ├── config.py               # General configuration (paths, uploads)
│   ├── auth_db.py              # User database / authorization
│   ├── documents_db.py         # Database of user-uploaded documents
│   ├── saved_db.py             # Database of saved answers (history)
│   ├── docling_extract.py      # Extracting text from PDF/images (upload)
│   │
│   ├── ingest/
│   │   ├── 00_wget.sh          # Download HTML/PDF from urls.txt → data_raw/
│   │   ├── 10_convert_docling.py   # HTML/PDF → Markdown conversion
│   │   └── 20_normalize_json.py    # Markdown → catalog.jsonl
│   │
│   └── rag/
│       ├── ask_cli.py          # RAG logic: search, context, call Claude
│       └── build_index_e5.py    # Building the FAISS index from catalog.jsonl
│
├── ui/
│   ├── html/
│   │   ├── index.html          # Home page
│   │   ├── auth.html           # Authorization page
│   │   └── welcome.html        # Welcome page
│   ├── css/
│   │   └── style.css           # Style
│   ├── js/
│   │   └── main.js             # Interface logic (questions, documents, saving)
│   └── assets/
│       └── logo_named.png      # Logo
│
├── data_raw/                   # Raw data (HTML, PDF) — result of wget
├── data_processed/             # Processed data
│   ├── md/                     # Markdown after 10_convert_docling.py
│   └── json/
│       └── catalog.jsonl       # Normalized catalog after 20_normalize_json.py
│
├── rag_index/                  # FAISS index (after build_index_e5.py)
├── uploads/                    # Files uploaded by the user
└── db/                         # SQLite (auth, documents, saved)
```
## How it works?
__1. Data preparation__

This step is performed not in the browser, but in the terminal on the machine where the project is deployed.

* **`urls.txt`** — links to catalog pages (e.g., podporneopatrenia.minedu.sk) are added to the file.

* **`00_wget.sh`** — the script downloads HTML and PDF files from these URLs to the `data_raw/` directory (e.g., `data_raw/manual/`).

* **`10_convert_docling.py`** — all HTML/PDF files found in `data_raw/` are converted to Markdown and saved in `data_processed/md/` with the same relative path.

* **`20_normalize_json.py`** — Markdown is broken down into sections, metadata (support levels, URLs) is added, and one large file `data_processed/json/catalog.jsonl` is created.

* **`build_index_e5.py`** — the script reads `catalog.jsonl`, splits the text into chunks, calculates vector representations (embeddings) for them using the E5 model, and saves the **FAISS index** in `rag_index/`. This index is used for semantic search when answering questions.

After completing these steps, the project has a ready catalog and index. You can launch the web application.

__2. App work: from question to answer__

 The **user** opens the website. If they are not logged in, they see the welcome page and the login/registration form. After successfully logging in, they are taken to the **dashboard** (the main page with the AI assistant).

 **Optional:** the user can upload a PDF or image (the “Nahrať” button in the “Priložiť dokument” block). The file is stored on the server, the text is extracted from it using **Docling** (`docling_extract.py`) and stored in the document database. A new document appears in the list. It can be selected as the context for the next question (or it is selected automatically after uploading).

**The user enters a question** and clicks “Odoslať otázku” (Send question). The text of the question and (if selected) `document_id` are sent to the server in the request.

**Server (`app.py`)**:
   - checks the session (whether the user is logged in);
   - if there is a `document_id`, downloads the text of this file for the current user from the document database;
   - calls **`run_ai(question, document_context=...)`**.

**`run_ai`** passes control to **RAG** (`ask_cli.ask`). By default, the call goes through **subprocess** (a separate Python process) to isolate memory and errors; you can disable this with `USE_SUBPROCESS=false` and call `ask` directly.

**RAG (`ask_cli.ask`)**:
   - if the text of an attached document is passed, it adds it to the context (along with the catalog and the web);
   - loads the **FAISS index** and performs a **semantic search** for the question (and keywords);
   - collects relevant document fragments into a single context with tags [D1], [D2], ...;
   - decides: are there enough documents for an answer or is a **web search** (Anthropic Tools / internet search) needed;
   - generates **system and user prompts** and calls **Claude** (Anthropic);
   - receives a response, adds the sections “Zdroje” and “Overenie v internete” if necessary, and returns the text.

   The **server** receives this text, creates a **draft** in the database (question + answer), and returns the **answer** and **`draft_id`** to the client.

The **browser** displays the response (Markdown render). The “Save answer” button becomes active: when clicked, **`draft_id`** is sent, and the server transfers this draft to the **saved** table (history). In the “Question history” section, the user sees all saved question-answer pairs and can expand and delete them.

__3. Authorization__
- **Registration/login** — via `/api/register` and `/api/login`; the password is stored as a hash. After a successful login, the `username` is recorded in the session.
- **Middleware** checks each request: for paths such as `/dashboard`, `/api/ask`, `/api/documents`, `/api/saved`, a session is required; if there is no session, 401 or a redirect to the home page is returned.
- All data (documents, drafts, saved answers) is linked to **user_id**, so one user cannot see other users' documents and history.


## Project Startup

__1.Requirements__

- Python 3.11+
- Git
- (optional) Docker + Docker Compose

__2.Clone the repository__

```bash
git clone <REPO_URL>
cd bp2026
```

__3.Local startup__

Create and activate virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

In the project root, create `api_keys.env` and add at least:

```env
ANTHROPIC_API_KEY=...
# optional:
# ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
# SESSION_SECRET=...
```

If `rag_index/faiss_e5` is not built yet, run:

```bash
python src/ingest/10_convert_docling.py
python src/ingest/20_normalize_json.py
python src/rag/build_index_e5.py
```

Start the app:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open in browser:

- `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

__4.Startup with Docker__

Go to `docker` directory:

```bash
cd docker
```

Create `docker/.env` (according to `docker-compose.yml`) and set:

```env
ANTHROPIC_API_KEY=...
SESSION_SECRET=...
```

Start container:

```bash
docker compose up --build
```

App will be available at:

- `http://localhost:8000`

__5.Quick evaluation test__

```bash
python evaluation/evaluate.py --ids 4 5
```

Results are saved in `evaluation/results/`.









