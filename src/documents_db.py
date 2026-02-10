import sqlite3
from datetime import datetime, timedelta
from src.config import DB_PATH

# Delete documents older than this (cleanup)
DOCUMENT_MAX_AGE_DAYS = 7


# Opens and returns a SQLite connection with Row factory.
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH.resolve()))
    conn.row_factory = sqlite3.Row
    return conn


# Returns the current UTC timestamp as a formatted string.
def _now_utc() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# Creates the user_documents table and indexes if they do not exist.
def init_documents_db() -> None:
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                extracted_text TEXT,
                status TEXT NOT NULL DEFAULT 'processing',
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_documents_user_id ON user_documents(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_documents_created_at ON user_documents(created_at)"
        )
        conn.commit()
    finally:
        conn.close()


# Inserts a new document record with status 'processing' and returns its id.
def create_document(
    user_id: int,
    original_filename: str,
    stored_path: str,
    mime_type: str,
) -> int:
    now = _now_utc()
    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO user_documents
               (user_id, original_filename, stored_path, mime_type, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'processing', ?, ?)""",
            (user_id, original_filename, stored_path, mime_type, now, now),
        )
        doc_id = cur.lastrowid
        conn.commit()
        return doc_id
    finally:
        conn.close()


# Sets document status to 'ready' and stores the extracted text.
def set_document_ready(doc_id: int, user_id: int, extracted_text: str) -> bool:
    now = _now_utc()
    conn = _get_conn()
    try:
        cur = conn.execute(
            """UPDATE user_documents
               SET status = 'ready', extracted_text = ?, updated_at = ?, error_message = NULL
               WHERE id = ? AND user_id = ?""",
            (extracted_text or "", now, doc_id, user_id),
        )
        n = cur.rowcount
        conn.commit()
        return n > 0
    finally:
        conn.close()


# Sets document status to 'error' and stores the error message.
def set_document_error(doc_id: int, user_id: int, error_message: str) -> bool:
    now = _now_utc()
    conn = _get_conn()
    try:
        cur = conn.execute(
            """UPDATE user_documents
               SET status = 'error', error_message = ?, updated_at = ?
               WHERE id = ? AND user_id = ?""",
            (error_message or "", now, doc_id, user_id),
        )
        n = cur.rowcount
        conn.commit()
        return n > 0
    finally:
        conn.close()


# Returns a document dict if it exists and belongs to the given user, or None.
def get_document_by_id_and_user(doc_id: int, user_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT id, user_id, original_filename, stored_path, mime_type,
                      extracted_text, status, error_message, created_at, updated_at
               FROM user_documents WHERE id = ? AND user_id = ?""",
            (doc_id, user_id),
        ).fetchone()
    return dict(row) if row else None


# Returns a list of document dicts for the given user, ordered by creation date.
def list_documents_by_user(user_id: int) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT id, original_filename, status, error_message, created_at,
                      substr(extracted_text, 1, 500) AS extracted_preview
               FROM user_documents WHERE user_id = ? ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# Deletes a document record owned by the user and returns (deleted, stored_path).
def delete_document_by_id_and_user(doc_id: int, user_id: int) -> tuple[bool, str | None]:
    doc = get_document_by_id_and_user(doc_id, user_id)
    if not doc:
        return (False, None)
    stored_path = doc.get("stored_path")
    conn = _get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM user_documents WHERE id = ? AND user_id = ?",
            (doc_id, user_id),
        )
        n = cur.rowcount
        conn.commit()
        return (n > 0, stored_path)
    finally:
        conn.close()


# Deletes document records older than max_age_days and returns their (id, stored_path) for file cleanup.
def cleanup_old_documents(max_age_days: int = DOCUMENT_MAX_AGE_DAYS) -> list[tuple[int, str]]:
    cutoff = (datetime.utcnow() - timedelta(days=max_age_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, stored_path FROM user_documents WHERE created_at < ?",
            (cutoff,),
        ).fetchall()
        deleted = [(r["id"], r["stored_path"]) for r in rows]
        if deleted:
            ids = [r["id"] for r in rows]
            conn.execute(
                "DELETE FROM user_documents WHERE id IN (" + ",".join("?" * len(ids)) + ")",
                ids,
            )
            conn.commit()
        return deleted
    finally:
        conn.close()
