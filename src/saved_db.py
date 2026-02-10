import sqlite3
from datetime import datetime, timedelta
from src.config import DB_PATH

# Draft TTL: 24 hours
DRAFT_TTL_HOURS = 24


# Opens and returns a SQLite connection with Row factory.
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH.resolve()))
    conn.row_factory = sqlite3.Row
    return conn


# Returns the current UTC timestamp as a formatted string.
def _now_utc() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# Creates saved_answers and drafts tables with indexes, then cleans expired drafts.
def init_saved_db() -> None:
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_saved_answers_user_id ON saved_answers(user_id)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_saved INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_drafts_user_id ON drafts(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_drafts_expires_at ON drafts(expires_at)"
        )
        conn.commit()
        cleanup_expired_drafts()
    finally:
        conn.close()


# Deletes all expired drafts and returns the number of rows removed.
def cleanup_expired_drafts() -> int:
    now = _now_utc()
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM drafts WHERE expires_at < ?", (now,))
        n = cur.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


# ---------- Drafts (user_id in every WHERE) ----------


# Creates a temporary draft for the user with a 24-hour TTL and returns its id.
def create_draft(user_id: int, question_text: str, answer_text: str) -> int:
    now = _now_utc()
    expires = (datetime.utcnow() + timedelta(hours=DRAFT_TTL_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO drafts (user_id, question_text, answer_text, created_at, expires_at, is_saved)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (user_id, (question_text or "").strip(), (answer_text or "").strip(), now, expires),
        )
        draft_id = cur.lastrowid
        conn.commit()
        return draft_id
    finally:
        conn.close()


# Returns a non-expired, unsaved draft dict for the given user, or None.
def get_draft_by_id_and_user(draft_id: int, user_id: int) -> dict | None:
    now = _now_utc()
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT id, user_id, question_text, answer_text, created_at, expires_at, is_saved
               FROM drafts WHERE id = ? AND user_id = ? AND expires_at >= ? AND is_saved = 0""",
            (draft_id, user_id, now),
        ).fetchone()
    return dict(row) if row else None


# Lists all active (non-expired, unsaved) drafts for the user.
def list_drafts_by_user(user_id: int) -> list[dict]:
    now = _now_utc()
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT id, question_text, answer_text, created_at, expires_at
               FROM drafts WHERE user_id = ? AND expires_at >= ? AND is_saved = 0
               ORDER BY created_at DESC""",
            (user_id, now),
        ).fetchall()
    return [dict(r) for r in rows]


# Deletes a draft owned by the user and returns True if it was removed.
def delete_draft_by_id_and_user(draft_id: int, user_id: int) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM drafts WHERE id = ? AND user_id = ?", (draft_id, user_id))
        n = cur.rowcount
        conn.commit()
        return n > 0
    finally:
        conn.close()


# Marks a draft as saved (is_saved=1) so it won't appear as active.
def mark_draft_saved(draft_id: int, user_id: int) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE drafts SET is_saved = 1 WHERE id = ? AND user_id = ?",
            (draft_id, user_id),
        )
        n = cur.rowcount
        conn.commit()
        return n > 0
    finally:
        conn.close()


# Copies a valid draft to saved_answers, marks it saved, and returns (saved_id, created_at) or None.
def save_from_draft(draft_id: int, user_id: int) -> tuple[int, str] | None:
    draft = get_draft_by_id_and_user(draft_id, user_id)
    if not draft:
        return None
    saved_id, created_at = insert_saved(
        user_id,
        draft["question_text"],
        draft["answer_text"],
    )
    mark_draft_saved(draft_id, user_id)
    return (saved_id, created_at)


# ---------- Saved answers (permanent history) ----------


# Inserts a question-answer pair into saved_answers and returns (row_id, created_at).
def insert_saved(user_id: int, question_text: str, answer_text: str) -> tuple[int, str]:
    created_at = _now_utc()
    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO saved_answers (user_id, question_text, answer_text, created_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, (question_text or "").strip(), (answer_text or "").strip(), created_at),
        )
        row_id = cur.lastrowid
        conn.commit()
        return (row_id, created_at)
    finally:
        conn.close()


# Returns all saved answers for the user, ordered by creation date descending.
def list_by_user_id(user_id: int) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT id, question_text, answer_text, created_at
               FROM saved_answers WHERE user_id = ? ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# Returns a single saved answer dict if it belongs to the user, or None.
def get_saved_by_id_and_user(saved_id: int, user_id: int) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT id, question_text, answer_text, created_at
               FROM saved_answers WHERE id = ? AND user_id = ?""",
            (saved_id, user_id),
        ).fetchone()
    return dict(row) if row else None


# Deletes a saved answer owned by the user and returns True if removed.
def delete_by_id_and_user(row_id: int, user_id: int) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM saved_answers WHERE id = ? AND user_id = ?",
            (row_id, user_id),
        )
        n = cur.rowcount
        conn.commit()
        return n > 0
    finally:
        conn.close()
