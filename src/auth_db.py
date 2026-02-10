import sqlite3
import hashlib
import os

from src.config import DB_PATH

USERNAME_MAX_LEN = 10
PASSWORD_EXACT_LEN = 4


# Hashes password with a fixed salt using SHA-256.
def _hash(password: str) -> str:
    salt = b"bp2026_auth"
    return hashlib.sha256(salt + password.encode("utf-8")).hexdigest()


# Opens and returns a SQLite connection with Row factory.
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH.resolve()))
    conn.row_factory = sqlite3.Row
    return conn


# Creates the users table and index if they do not exist.
def init_db() -> None:
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"
        )


# Registers a new user after validating username length and password, raises ValueError on failure.
def create_user(username: str, password: str) -> None:
    u = (username or "").strip()
    if not u:
        raise ValueError("Prihlasovacie meno nesmie byť prázdne")
    if len(u) > USERNAME_MAX_LEN:
        raise ValueError(f"Prihlasovacie meno najviac {USERNAME_MAX_LEN} znakov")
    if len(password) != PASSWORD_EXACT_LEN:
        raise ValueError("Heslo musí mať presne 4 znaky")

    password_hash = _hash(password)
    with _get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (u, password_hash),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError("Používateľ s týmto prihlasovacím menom už existuje")


# Returns user dict (id, username, password_hash) by username, or None if not found.
def get_user_by_username(username: str) -> dict | None:
    u = (username or "").strip()
    if not u:
        return None
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (u,),
        ).fetchone()
    return dict(row) if row else None


# Checks if username exists and the provided password matches the stored hash.
def verify_password(username: str, password: str) -> bool:
    if len(password) != PASSWORD_EXACT_LEN:
        return False
    user = get_user_by_username(username)
    if not user:
        return False
    return _hash(password) == user["password_hash"]
