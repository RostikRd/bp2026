# Inštrukcie pre aktualizáciu systému

## ✅ Urobene zmeny:

1. **Podpora všetkých 3 úrovní** - systém teraz zobrazuje dokumenty z úrovní 1, 2 aj 3
2. **Podpora PDF súborov** - systém teraz spracováva PDF súbory (vrátane katalog.pdf)

## 📋 Čo treba urobiť:

### 1. Presuňte katalog.pdf z _ignore priečinka:

```bash
mv data_raw/_ignore/katalog.pdf data_raw/manual/katalog.pdf
```

### 2. Znovu spustite pipeline na spracovanie dát:

```bash
# Spustite bootstrap skript, ktorý automaticky:
# - Konvertuje PDF → Markdown
# - Normalizuje → JSONL
# - Vytvorí FAISS index
bash scripts/bootstrap.sh
```

Alebo manuálne:

```bash
# 1. Konvertovať PDF → Markdown
python src/ingest/10_convert_docling.py

# 2. Normalizovať → JSONL
python src/ingest/20_normalize_json.py

# 3. Vytvoriť FAISS index
python src/rag/build_index_e5.py
```

### 3. Reštartujte aplikáciu:

```bash
# Ak používate Docker
bash docker/stop.sh
bash docker/start.sh

# Alebo lokálne
uvicorn app:app --reload
```

## ✨ Výsledok:

- ✅ Systém teraz podporuje všetky 3 úrovne podporných opatrení
- ✅ katalog.pdf bude spracovaný a zahrnutý do RAG systému
- ✅ AI bude môcť používať informácie z katalógu pri generovaní odpovedí

