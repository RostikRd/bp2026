#!/bin/bash
# Downloads HTML and PDF files from URLs listed in urls.txt to data_raw/manual/
set -euo pipefail

OUT_DIR="data_raw/manual"
URLS_FILE="urls.txt"

if [ ! -f "$URLS_FILE" ]; then
    echo "❌ File $URLS_FILE not found!"
    echo "Create $URLS_FILE file with URLs, one per line"
    exit 1
fi

mkdir -p "$OUT_DIR"

echo "📥 Downloading data from $URLS_FILE..."
echo ""

while IFS= read -r URL || [ -n "$URL" ]; do
    URL=$(echo "$URL" | tr -d '\r' | xargs)
    [[ -z "$URL" || "$URL" =~ ^# ]] && continue
    
    echo "=== Downloading: $URL ==="
    wget \
        --recursive --level=20 --no-parent --continue \
        --execute robots=off \
        --convert-links --adjust-extension --page-requisites --timestamping \
        --user-agent="Mozilla/5.0 (X11; Linux x86_64)" \
        --accept html,htm,pdf \
        --reject jpg,jpeg,png,svg,gif,ico,css,js,woff,woff2,ttf,eot \
        --directory-prefix "$OUT_DIR" \
        "$URL" || echo "⚠ Download error: $URL"
    echo ""
done < "$URLS_FILE"

echo "✅ Download completed. Files saved to $OUT_DIR"
echo ""
echo "💡 To add new URLs, edit the $URLS_FILE file"

