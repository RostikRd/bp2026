#!/usr/bin/env bash
set -euo pipefail

IDX="rag_index/faiss_e5"
STAMP="$IDX/_built.stamp"
RAW="data_raw"
PROC="data_processed"

stamp() { date -r "$1" +%s 2>/dev/null || echo 0; }

need_build=0
[ ! -d "$IDX" ] && need_build=1
[ ! -f "$STAMP" ] && need_build=1
if [ $need_build -eq 0 ]; then
  t_idx=$(stamp "$IDX")
  t_raw=$(stamp "$RAW")
  t_proc=$(stamp "$PROC")
  [ "$t_raw" -gt "$t_idx" ] && need_build=1
  [ "$t_proc" -gt "$t_idx" ] && need_build=1
fi

# прибрати шум з data_raw (шрифти/статичні ассети)
find data_raw -type f \( \
  -name "*.ttf" -o -name "*.woff" -o -name "*.woff2" -o -name "*.css" -o -name "*.js" \
  -o -name "*.svg" -o -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.gif" -o -name "*.ico" \
  -o -path "*/assets/*" \) -print -delete || true


if [ $need_build -eq 1 ]; then
  echo "[bootstrap] Building index..."
  # (1) джерела в data_raw/ — у тебе вже є; якщо потрібно, запусти свій wget-скрипт тут
  # bash ingest/00_wget.sh

  # (2) Docling → Markdown
  python src/ingest/10_convert_docling.py
  # (3) normalizácia → JSONL
  python src/ingest/20_normalize_json.py
  # (4) LangChain FAISS+e5
  python src/rag/build_index_e5.py
else
  echo "[bootstrap] Index is fresh. Skipping rebuild."
fi
