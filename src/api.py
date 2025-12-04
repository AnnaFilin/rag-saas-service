from fastapi import FastAPI
from pydantic import BaseModel
from src.process_texts import split_into_chunks
from src.embeddings import create_embeddings
from src.memory_store import store

app = FastAPI()

class ChatRequest(BaseModel):
    workspace_id: str
    question: str
    role: str | None = None

class IngestRequest(BaseModel):
    workspace_id: str
    documents: list[str]



@app.get("/health")
def health_check():
    """Return a simple OK status for readiness/liveness checks."""
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    return {
        "workspace_id": request.workspace_id,
        "question": request.question,
        "role": request.role,
        "answer": "This is a stub answer.",
        "sources": [],
    }


@app.post("/ingest")
def ingest(request: IngestRequest):
    """Accept new documents for ingestion and return a simple summary."""

    all_chunks = []
    for document in request.documents:
        chunks = split_into_chunks(text=document, source=request.workspace_id)
        all_chunks.extend(chunks)

    embeddings, _ = create_embeddings(all_chunks) 
    store.add(request.workspace_id, all_chunks, embeddings)
    stored_records = len(store.get_workspace(request.workspace_id))

    return {
        "workspace_id": request.workspace_id,
        "ingested_count": len(request.documents),
        "chunks_count": len(all_chunks),
        "embeddings_count": len(embeddings),
        "stored_records": stored_records,
        "skipped": 0,
        "errors": [],
    }