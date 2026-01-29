from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, sys, subprocess, textwrap

app = FastAPI(title="BP2026 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ASK = None
USE_SUBPROCESS = os.environ.get("USE_SUBPROCESS", "true").lower() == "true"

if not USE_SUBPROCESS:
    try:
        project_root = os.path.dirname(os.path.abspath(__file__))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.rag.ask_cli import ask as ASK
    except Exception:
        ASK = None

def run_ai(q: str) -> str:
    if USE_SUBPROCESS or not callable(ASK):
        try:
            project_root = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(project_root, "src", "rag", "ask_cli.py")
            result = subprocess.run(
                [sys.executable, script_path, q],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=project_root,
                encoding="utf-8",
                errors="replace"
            )
            if result.returncode != 0:
                error_msg = result.stderr if result.stderr else "Unknown error"
                return f"Error: {error_msg[:500]}"
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_output = e.stderr if e.stderr else e.output
            return f"Error Ai: {textwrap.shorten(error_output, width=1000)}"
        except Exception as e:
            return f"Error: {str(e)}"

    if callable(ASK):
        try:
            result = ASK(q)
            if not result:
                return "Error: Empty response from AI"
            return result
        except Exception as e:
            return f"Error: {str(e)}"

    return "Error: Could not execute AI query"

class Q(BaseModel):
    question: str

@app.post("/api/ask")
def ask(q: Q):
    return {"answer": run_ai(q.question)}

app.mount("/", StaticFiles(directory="ui", html=True), name="ui")
