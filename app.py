from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
import logging
import os
import sys
import subprocess
import textwrap
import time
import uuid
from pathlib import Path

logger = logging.getLogger("bp2026")

# Auth: init DB and session secret (set DB path from app so auth and saved use same file)
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
import src.config
src.config.DB_PATH = project_root / "app.db"
from src.auth_db import init_db, create_user, get_user_by_username, verify_password
from src.saved_db import (
    init_saved_db,
    cleanup_expired_drafts,
    create_draft,
    get_draft_by_id_and_user,
    list_drafts_by_user,
    delete_draft_by_id_and_user,
    save_from_draft,
    insert_saved,
    list_by_user_id,
    get_saved_by_id_and_user,
    delete_by_id_and_user,
)
from src.documents_db import (
    init_documents_db,
    create_document,
    set_document_ready,
    set_document_error,
    get_document_by_id_and_user,
    list_documents_by_user,
    delete_document_by_id_and_user,
    cleanup_old_documents,
)
from src import docling_extract
import src.config

init_db()
init_saved_db()
init_documents_db()
cleanup_expired_drafts()  # Remove expired drafts on startup

# Uploads directory and cleanup old documents (7 days)
src.config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
for _doc_id, stored_path in cleanup_old_documents():
    if stored_path:
        p = project_root / stored_path
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
SESSION_SECRET = os.environ.get("SESSION_SECRET", "bp2026-dev-secret-change-in-production")

# Ensure bp2026 logger is visible when running uvicorn
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logging.getLogger("bp2026").setLevel(logging.INFO)

app = FastAPI(title="BP2026 API")

# In Starlette the *last* added middleware runs *first* (outermost). So add Session last
# so it runs first and populates request.session before AuthGuard runs.
class AuthGuardMiddleware(BaseHTTPMiddleware):
    """Welcome at /. Unauthenticated -> welcome; protected -> redirect to /. Authenticated / -> /dashboard."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        session = request.session
        logged_in = bool(session.get("username"))

        if logged_in:
            if path == "/":
                return RedirectResponse(url="/dashboard", status_code=302)
            return await call_next(request)
        # Public: welcome (/), auth, logout, login/register API
        if path in ("/", "/auth", "/logout") or path.startswith("/api/login") or path.startswith("/api/register") or path.startswith("/api/logout") or path.startswith("/api/me"):
            return await call_next(request)
        if path == "/dashboard":
            return RedirectResponse(url="/", status_code=302)
        if path == "/api/ask" or (path.startswith("/api/") and path not in ("/api/me", "/api/login", "/api/register", "/api/logout")):
            return JSONResponse({"detail": "Vyžaduje sa prihlásenie"}, status_code=401)
        return await call_next(request)


app.add_middleware(AuthGuardMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)


ASK = None
USE_SUBPROCESS = os.environ.get("USE_SUBPROCESS", "false").lower() == "true"

if not USE_SUBPROCESS:
    try:
        _proj_str = os.path.dirname(os.path.abspath(__file__))
        if _proj_str not in sys.path:
            sys.path.insert(0, _proj_str)
        from src.rag.ask_cli import ask as ASK
    except Exception:
        ASK = None

def run_ai(q: str, document_context: str | None = None) -> str:
    env = os.environ.copy()
    if document_context and document_context.strip():
        env["USER_DOCUMENT_CONTEXT"] = document_context.strip()
    if USE_SUBPROCESS or not callable(ASK):
        try:
            proot = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(proot, "src", "rag", "ask_cli.py")
            result = subprocess.run(
                [sys.executable, script_path, q],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=proot,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else "Neznáma chyba"
                return f"Chyba: {error_msg[:500]}"
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_output = e.stderr if e.stderr else e.output
            return f"Chyba AI: {textwrap.shorten(error_output, width=1000)}"
        except Exception as e:
            return f"Chyba: {str(e)}"

    if callable(ASK):
        try:
            result = ASK(q, user_document_context=document_context)
            if not result:
                return "Chyba: Prázdna odpoveď od AI"
            return result
        except Exception as e:
            return f"Chyba: {str(e)}"

    return "Chyba: Nepodarilo sa vykonať dopyt AI"

class Q(BaseModel):
    question: str
    document_id: int | None = None


class RegisterBody(BaseModel):
    username: str
    password: str


class LoginBody(BaseModel):
    username: str
    password: str


class DraftBody(BaseModel):
    question: str = ""
    answer: str = ""


class FromDraftBody(BaseModel):
    draft_id: int


def _get_user_id(request: Request) -> int:
    """Return current user id or raise 401."""
    username = request.session.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Nie ste prihlásený")
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="Nie ste prihlásený")
    return user["id"]


@app.get("/")
def welcome_or_dashboard(request: Request):
    """Serve welcome page (only for unauthenticated; middleware redirects logged-in to /dashboard)."""
    return FileResponse(project_root / "ui" / "html" / "welcome.html")


@app.get("/dashboard")
def dashboard(request: Request):
    """Main app for authenticated users. Middleware redirects unauthenticated to /."""
    return FileResponse(project_root / "ui" / "html" / "index.html")


@app.get("/auth")
def auth_page():
    """Serve auth page (registration / login)."""
    return FileResponse(project_root / "ui" / "html" / "auth.html")


@app.post("/api/register")
def register(data: RegisterBody, request: Request):
    """Register new user. Validation: username 1..10, password exactly 4."""
    username = (data.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Prihlasovacie meno nesmie byť prázdne")
    if len(username) > 10:
        raise HTTPException(status_code=400, detail="Prihlasovacie meno najviac 10 znakov")
    if len(data.password) != 4:
        raise HTTPException(status_code=400, detail="Heslo musí mať presne 4 znaky")
    try:
        create_user(username, data.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    request.session["username"] = username
    return {"ok": True, "username": username}


@app.post("/api/login")
def login(data: LoginBody, request: Request):
    """Login. Validation: username 1..10, password exactly 4."""
    username = (data.username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Prihlasovacie meno nesmie byť prázdne")
    if len(username) > 10:
        raise HTTPException(status_code=400, detail="Prihlasovacie meno najviac 10 znakov")
    if len(data.password) != 4:
        raise HTTPException(status_code=400, detail="Heslo musí mať presne 4 znaky")
    if not get_user_by_username(username):
        raise HTTPException(status_code=401, detail="Používateľ s týmto prihlasovacím menom nebol nájdený")
    if not verify_password(username, data.password):
        raise HTTPException(status_code=401, detail="Nesprávne heslo")
    request.session["username"] = username
    return {"ok": True, "username": username}


@app.get("/logout")
def logout_get(request: Request):
    """Clear session and redirect to welcome (/). Used by the logout link."""
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


@app.post("/api/logout")
def logout(request: Request):
    """Clear session (API)."""
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    """Return current user or 401."""
    username = request.session.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Nie ste prihlásený")
    return {"username": username}


@app.post("/api/ask")
def ask(q: Q, request: Request):
    """Protected: run AI, optionally with user document context; create draft, return answer + draft_id."""
    user_id = _get_user_id(request)
    question = (q.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Otázka je prázdna")
    document_context = None
    if q.document_id is not None:
        doc = get_document_by_id_and_user(q.document_id, user_id)
        if not doc:
            raise HTTPException(status_code=403, detail="Dokument nebol nájdený alebo nemáte oprávnenie")
        if doc.get("status") != "ready":
            raise HTTPException(
                status_code=400,
                detail="Dokument ešte nie je spracovaný alebo má chybu. Počkajte na stav ready alebo nahrajte iný.",
            )
        document_context = (doc.get("extracted_text") or "").strip()
        if not document_context:
            raise HTTPException(status_code=400, detail="Dokument nemá extrahovaný text")
    answer_text = run_ai(question, document_context=document_context)
    try:
        draft_id = create_draft(user_id, question, answer_text)
        logger.info("Draft created draft_id=%s user_id=%s", draft_id, user_id)
    except Exception as e:
        logger.exception("Draft creation failed: %s", e)
        draft_id = None
    return {"answer": answer_text, "draft_id": draft_id}


@app.post("/api/drafts")
def drafts_post(data: DraftBody, request: Request):
    """Create draft for current user. Returns draft_id."""
    user_id = _get_user_id(request)
    question = (data.question or "").strip()
    answer = (data.answer or "").strip()
    if not question or not answer:
        raise HTTPException(status_code=400, detail="Otázka aj odpoveď sú povinné")
    draft_id = create_draft(user_id, question, answer)
    return {"draft_id": draft_id}


@app.get("/api/drafts")
def drafts_list(request: Request):
    """List active (non-expired) drafts for current user."""
    cleanup_expired_drafts()
    user_id = _get_user_id(request)
    items = list_drafts_by_user(user_id)
    return {"items": items}


@app.delete("/api/drafts/{draft_id:int}")
def drafts_delete(draft_id: int, request: Request):
    """Delete draft only if owned by current user."""
    user_id = _get_user_id(request)
    if not delete_draft_by_id_and_user(draft_id, user_id):
        raise HTTPException(status_code=404, detail="Čiernopis nebol nájdený alebo nemáte oprávnenie")
    return {"ok": True}


@app.post("/api/saved/from-draft")
def saved_from_draft(data: FromDraftBody, request: Request):
    """Save draft into permanent history. 410 if draft expired/not found."""
    user_id = _get_user_id(request)
    logger.info("Save from draft draft_id=%s user_id=%s", data.draft_id, user_id)
    result = save_from_draft(data.draft_id, user_id)
    if result is None:
        logger.warning("Save from draft failed: draft_id=%s user_id=%s (expired or not found)", data.draft_id, user_id)
        raise HTTPException(
            status_code=410,
            detail="Čiernopis vypršal alebo neexistuje. Získajte odpoveď znova a uložte.",
        )
    saved_id, created_at = result
    item = get_saved_by_id_and_user(saved_id, user_id)
    if not item:
        logger.error("Saved record not found after insert saved_id=%s user_id=%s", saved_id, user_id)
        raise HTTPException(status_code=500, detail="Chyba pri ukladaní")
    logger.info("Saved draft_id=%s -> saved_id=%s user_id=%s", data.draft_id, saved_id, user_id)
    return {"ok": True, "saved_id": saved_id, "item": item}


@app.get("/api/saved")
def saved_list(request: Request):
    """List saved Q/A for current user. Requires session."""
    user_id = _get_user_id(request)
    items = list_by_user_id(user_id)
    return {"items": items}


@app.delete("/api/saved/{item_id:int}")
def saved_delete(item_id: int, request: Request):
    """Delete saved item if owned by current user. Returns 404 if not found or not owner."""
    user_id = _get_user_id(request)
    if not delete_by_id_and_user(item_id, user_id):
        raise HTTPException(status_code=404, detail="Záznam nebol nájdený alebo nemáte oprávnenie")
    return {"ok": True}


# ---------- User documents (upload, list, delete) ----------
ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


def _check_upload_file(filename: str, content_type: str | None, size: int) -> tuple[str, str]:
    """Returns (mime_type, safe_extension) or raises HTTPException."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Povolené formáty: PDF, JPG, PNG, WEBP. Zadaný súbor má príponu: {ext or '(žiadna)'}",
        )
    if size > src.config.DOCUMENT_UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Súbor je príliš veľký. Maximum je {src.config.DOCUMENT_UPLOAD_MAX_BYTES // (1024*1024)} MB.",
        )
    mime = (content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Nepovolený typ súboru: {content_type or 'neznámy'}. Povolené: PDF, JPEG, PNG, WEBP.",
        )
    return (mime, ext)


@app.post("/api/documents/upload")
async def documents_upload(request: Request, file: UploadFile = File(...)):
    """Upload a document; extract text with Docling; return document_id and status."""
    user_id = _get_user_id(request)
    filename = file.filename or "document"
    content_type = file.content_type
    # Read file to get size and save
    body = await file.read()
    size = len(body)
    mime, ext = _check_upload_file(filename, content_type, size)

    uploads_dir = src.config.UPLOADS_DIR
    unique_name = f"{user_id}_{int(time.time())}_{uuid.uuid4().hex[:12]}{ext}"
    stored_path = f"uploads/{unique_name}"
    full_path = project_root / stored_path
    try:
        full_path.write_bytes(body)
    except Exception as e:
        logger.exception("Failed to write upload: %s", e)
        raise HTTPException(status_code=500, detail="Nepodarilo sa uložiť súbor")

    doc_id = create_document(
        user_id=user_id,
        original_filename=filename,
        stored_path=stored_path,
        mime_type=mime,
    )
    logger.info("Document created doc_id=%s user_id=%s path=%s", doc_id, user_id, stored_path)

    # Synchronous Docling extraction (no worker in this app)
    try:
        text = docling_extract.extract_text_with_docling(str(full_path), mime)
        set_document_ready(doc_id, user_id, text)
        status = "ready"
        logger.info("Document extraction ready doc_id=%s", doc_id)
    except Exception as e:
        status = "error"
        err_msg = str(e)[:500]
        set_document_error(doc_id, user_id, err_msg)
        logger.warning("Document extraction failed doc_id=%s: %s", doc_id, e)
        # Optionally delete the file on extract failure to save space; we keep it for retry/debug
        # full_path.unlink(missing_ok=True)

    return {"document_id": doc_id, "status": status}


@app.get("/api/documents")
def documents_list(request: Request):
    """List current user's documents (id, original_filename, status, created_at, preview)."""
    user_id = _get_user_id(request)
    items = list_documents_by_user(user_id)
    return {"items": items}


@app.delete("/api/documents/{doc_id:int}")
def documents_delete(doc_id: int, request: Request):
    """Delete document and its file if owned by current user. 404 if not found or not owner."""
    user_id = _get_user_id(request)
    deleted, stored_path = delete_document_by_id_and_user(doc_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dokument nebol nájdený alebo nemáte oprávnenie")
    if stored_path:
        p = project_root / stored_path
        if p.exists():
            try:
                p.unlink()
            except Exception as e:
                logger.warning("Could not delete file %s: %s", p, e)
    return {"ok": True}


# Static files (css, js, images); routes above take precedence over mount
app.mount("/", StaticFiles(directory="ui", html=True), name="ui")
