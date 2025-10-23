from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, sys, subprocess, textwrap

app = FastAPI(title="BP2026 API")

# Додаємо CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# спробуємо імпортувати функцію ask з твого коду
ASK = None
try:
    sys.path.append(os.getcwd())  # щоб бачився пакет src
    from src.rag.ask_cli import ask as ASK  # змінюй, якщо функція в іншому місці
except Exception:
    pass

def run_ai(q: str) -> str:
    if callable(ASK):
        return ASK(q)
    # fallback: запуск CLI-скрипта
    try:
        out = subprocess.check_output(
            [sys.executable, "src/rag/ask_cli.py", q],
            stderr=subprocess.STDOUT, text=True, timeout=120
        )
        return out.strip()
    except subprocess.CalledProcessError as e:
        return "Помилка AI: " + textwrap.shorten(e.output, width=1000)

class Q(BaseModel):
    question: str

@app.post("/api/ask")
def ask(q: Q):
    return {"answer": run_ai(q.question)}

# віддаємо твій фронт з папки ui/
app.mount("/", StaticFiles(directory="ui", html=True), name="ui")
