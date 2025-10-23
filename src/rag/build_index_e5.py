# Build vector index for RAG system
import os, json
from pathlib import Path
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.docstore.document import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

JSONL = Path("data_processed/json/catalog.jsonl")
PERSIST = Path("rag_index/faiss_e5"); PERSIST.mkdir(parents=True, exist_ok=True)

EMBED_MODEL = os.environ.get("EMBED_MODEL", "intfloat/multilingual-e5-small")

# Load and prepare documents
items = [json.loads(l) for l in JSONL.read_text(encoding="utf-8").splitlines()]
docs = []
for it in items:
    full = f"# {it['title']}\n"
    for s in it["sections"]:
        if s.get("heading"):
            full += f"\n## {s['heading']}\n"
        full += s.get("text", "") + "\n"
    meta = {
        "title": it["title"],
        "levels": ",".join(map(str, it["levels"])),
        "url": it.get("url_hint", ""),
        "source_file": it["source_file"],
    }
    docs.append(Document(page_content=full, metadata=meta))

# Split into chunks
splitter = RecursiveCharacterTextSplitter(chunk_size=1400, chunk_overlap=200)
chunks = splitter.split_documents(docs)

# Create embeddings and index
embedder = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL,
    encode_kwargs={"normalize_embeddings": True},
)

vs = FAISS.from_documents(chunks, embedder)
vs.save_local(str(PERSIST))
print(f"✓ FAISS index at {PERSIST} using {EMBED_MODEL}")
