import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _PROJECT_ROOT / "app.db"

# Document uploads: directory and max file size (bytes). Override via env.
UPLOADS_DIR = _PROJECT_ROOT / "uploads"
DOCUMENT_UPLOAD_MAX_BYTES = int(os.environ.get("DOCUMENT_UPLOAD_MAX_BYTES", 10 * 1024 * 1024))  # 10MB
