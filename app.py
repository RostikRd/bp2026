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
try:
    sys.path.append(os.getcwd()) 
    from src.rag.ask_cli import ask as ASK  
except Exception as e:
    print(f"Warning: Could not import ask function: {e}", file=sys.stderr)

def run_ai(q: str) -> str:
    if callable(ASK):
        try:
            return ASK(q)
        except Exception as e:
            return f"Error: {str(e)}"
    try:
        out = subprocess.check_output(
            [sys.executable, "src/rag/ask_cli.py", q],
            stderr=subprocess.STDOUT, text=True, timeout=120
        )
        return out.strip()
    except subprocess.CalledProcessError as e:
        return "Error Ai: " + textwrap.shorten(e.output, width=1000)
    except Exception as e:
        return f"Error: {str(e)}"

class Q(BaseModel):
    question: str

@app.post("/api/ask")
def ask(q: Q):
    return {"answer": run_ai(q.question)}

# Mount static files - UI directory serves HTML, CSS, JS, and images
# All files in ui/ are accessible from root (/, /css/, /js/, etc.)
app.mount("/", StaticFiles(directory="ui", html=True), name="ui")
