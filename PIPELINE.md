# Kroky vykonania programu

## 1. Príprava dát

**Krok 1: Pridanie URL do `urls.txt`**
- Do súboru `urls.txt` pridáte URL adresy stránok, ktoré chcete spracovať
- Každý URL na samostatný riadok
- Môžete pridať komentáre (riadky začínajúce s `#`)

**Krok 2: Sťahovanie dát (`00_wget.sh`)**
- Spustíte `bash src/ingest/00_wget.sh`
- Skript stiahne HTML a PDF súbory z URL v `urls.txt`
- Súbory sa uložia do `data_raw/manual/`

## 2. Konverzia dát

**Krok 3: Konverzia na Markdown (`10_convert_docling.py`)**
- Spustíte `python src/ingest/10_convert_docling.py`
- Docling konvertuje HTML a PDF súbory na Markdown formát
- Výsledok sa uloží do `data_processed/md/`

**Krok 4: Normalizácia do JSONL (`20_normalize_json.py`)**
- Spustíte `python src/ingest/20_normalize_json.py`
- Skript rozdelí Markdown súbory na sekcie
- Vytvorí JSONL súbor (`catalog.jsonl`) s normalizovanými dátami
- Automaticky určí úrovne podpory (1, 2, 3) pre každý dokument

## 3. Vytvorenie vektorového indexu

**Krok 5: Vytvorenie FAISS indexu (`build_index_e5.py`)**
- Spustíte `python src/rag/build_index_e5.py`
- Skript vytvorí embeddings (vektorové reprezentácie) textu pomocou multilingual-e5-small modelu
- Rozdelí dokumenty na menšie chunks (kúsky)
- Vytvorí FAISS vektorový index v `rag_index/faiss_e5/`

## 4. Spustenie aplikácie

**Krok 6: Spustenie FastAPI servera**
- Lokálne: `uvicorn app:app --reload --host 0.0.0.0 --port 8000`
- Alebo cez Docker: `bash docker/start.sh`

**Krok 7: Použitie systému**
- Otvoríte http://localhost:8000 v prehliadači
- Zadáte otázku
- Systém (`ask_cli.py`):
  1. Načíta API kľúče z `api_keys.env`
  2. Načíta mapovanie URL z `urls.txt`
  3. Vytvorí embedding vašej otázky pomocou multilingual-e5-small modelu
  4. Nájde najrelevantnejšie dokumenty v FAISS indexe (semantic search, k=20)
  5. Rozšíri vyhľadávanie pomocou kľúčových slov (ADHD, matematika, čítanie, atď.)
  6. Odstráni duplikáty dokumentov
  7. Filtruje podľa úrovní podpory (1-3) pomocou `level_ok()`
  8. Vyberie top 12 najrelevantnejších dokumentov
  9. Vytvorí kontext z vybraných dokumentov (chunks do 1000 znakov)
  10. Nájde správne URL pre každý dokument pomocou `resolve_url()`
  11. Pošle systémový prompt + kontext + otázku do AI (Claude/GPT)
  12. Vráti štruktúrovanú odpoveď so zdrojmi (číslo, názov, URL)

## Zhrnutie pipeline:

```
urls.txt → 00_wget.sh → HTML/PDF súbory
    ↓
10_convert_docling.py → Markdown súbory
    ↓
20_normalize_json.py → catalog.jsonl (normalizované dáta)
    ↓
build_index_e5.py → FAISS index (vektorová databáza)
    ↓
app.py → FastAPI server → Web rozhranie
    ↓
Používateľ → Otázka → Semantic search → AI → Odpoveď
```

## Detaily `ask_cli.py`:

**Hlavné funkcie:**

1. **`load_api_keys()`** - Načíta API kľúče z `api_keys.env` súboru
2. **`load_url_mapping()`** - Načíta mapovanie URL z `urls.txt` pre správne odkazy
3. **`resolve_url()`** - Nájde správny URL dokumentu na základe metadát
4. **`level_ok()`** - Filtruje dokumenty podľa úrovní podpory (1-3)
5. **Rozšírené vyhľadávanie** - Automaticky pridáva kľúčové slová na základe otázky:
   - ADHD → pozornosť, sústredenie, organizácia, časové signály
   - Matematika → matematické úlohy, počítanie
   - Čítanie → čítanie s porozumením, pravopis
   - ASD → vizuálne rozvrhy, prechodové rituály
   - A ďalšie kategórie...

**Proces vyhľadávania:**
- Semantic search: Hľadá podobné dokumenty na základe významu (nie len ключових слів)
- Keyword expansion: Rozširuje vyhľadávanie o релевантні терміни
- Level filtering: Zobrazuje len dokumenty s рівнями 1, 2 або 3
- Context preparation: Vytvára kontext z top 12 dokumentov pre AI

**AI modely:**
- Podporuje Anthropic Claude (3.5 Sonnet, Haiku)
- Podporuje OpenAI GPT (gpt-4o-mini)
- Automatický fallback na alternatívne modely pri chybách
- Retry logika pri preťažení API

## Automatizácia:

Namiesto manuálneho spúšťania krokov 3-5 môžete použiť:
```bash
bash scripts/bootstrap.sh
```
Tento skript automaticky:
- Skontroluje, či je potrebné prestavať index
- Spustí všetky potrebné konverzie
- Vytvorí nový FAISS index

