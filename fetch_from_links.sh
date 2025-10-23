set -euo pipefail

OUT_DIR="data_raw/manual"
mkdir -p "$OUT_DIR"

while IFS= read -r URL; do
  [[ -z "$URL" || "$URL" =~ ^# ]] && continue
  echo "=== Fetching: $URL ==="
  wget \
    --recursive --level=20 --no-parent --continue \
    --execute robots=off \
    --convert-links --adjust-extension --page-requisites --timestamping \
    --user-agent="Mozilla/5.0 (X11; Linux x86_64)" \
    --accept html,htm,pdf \
    --reject jpg,jpeg,png,svg,gif,ico,css,js,woff,woff2,ttf,eot \
    --directory-prefix "$OUT_DIR" \
    "$URL"
done < urls.txt

echo "✓ Done. Files saved under $OUT_DIR"
