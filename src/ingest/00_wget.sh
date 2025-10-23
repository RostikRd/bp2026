#!/usr/bin/env bash
set -euo pipefail

BASE_URL="https://podporneopatrenia.minedu.sk/katalog-podpornych-opatreni/"
OUT_DIR="data_raw"

mkdir -p "$OUT_DIR"

wget \
  --recursive \
  --level=5 \
  --no-clobber \
  --page-requisites \
  --convert-links \
  --adjust-extension \
  --no-parent \
  --domains podporneopatrenia.minedu.sk \
  --directory-prefix "$OUT_DIR" \
  "$BASE_URL"

echo "✓ Finished downloading to $OUT_DIR"
