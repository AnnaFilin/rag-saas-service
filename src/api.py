from fastapi import FastAPI, File, Form, UploadFile
from pathlib import Path
import tempfile
from pydantic import BaseModel
from src.load_docs import convert_to_markdown
from src.process_texts import split_into_chunks
from src.embeddings import create_embeddings
from src.memory_store import store
from src.llm_pipeline import build_llm_chain, get_llm_answer
import os

LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() == "true"

DEFAULT_ROLE = (
    "You are a helpful assistant that answers only based on the provided context. "
    "If the context is not enough, say: 'I do not know based on the provided context.'"
)


app = FastAPI()

class ChatRequest(BaseModel):
    workspace_id: str
    question: str
    role: str | None = None

class IngestRequest(BaseModel):
    workspace_id: str
    documents: list[str]

class ChatResponse(BaseModel):
    workspace_id: str
    question: str
    role: str | None = None
    answer: str
    sources: list[dict]
    stored_records: int
    candidates: list[dict]
    llm_backend: str
    llm_model: str

class WorkspaceSummary(BaseModel):
    workspace_id: str
    records: int


@app.get("/workspaces")
def list_workspaces() -> list[WorkspaceSummary]:
    return [
        WorkspaceSummary(**workspace)
        for workspace in store.list_workspaces()
    ]

@app.get("/health")
def health_check():
    """Return a simple OK status for readiness/liveness checks."""
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    records = store.get_workspace(request.workspace_id)
    stored_records = len(records)
    llm_backend = os.getenv("LLM_BACKEND", "ollama")
    llm_model = os.getenv("LLM_MODEL", "llama3.2:latest")

    if stored_records == 0:
        answer = "This is a stub answer."
        candidates = []
    else:
        query_chunks = [{"content": request.question}]
        query_embeddings, _ = create_embeddings(query_chunks)
        query_vector = query_embeddings[0].tolist()
        candidates = store.top_k_similar(
            workspace_id=request.workspace_id,
            query_embedding=query_vector,
            k=3,
        )
        context_parts = [c["content"] for c in candidates if "content" in c]
        context = "\n\n---\n\n".join(context_parts)

        if not LLM_ENABLED:
            answer = "LLM is temporarily disabled. Please try again later."
        else:
            effective_role = (
                request.role.strip()
                if request.role and request.role.strip()
                else DEFAULT_ROLE
            )
            chain = build_llm_chain(effective_role)
            answer = get_llm_answer(chain, request.question, context)

    sources = [
        {
            "content": candidate.get("content"),
            "source": candidate.get("source"),
            "score": candidate.get("score"),
        }
        for candidate in candidates
    ]    

    return ChatResponse(
        workspace_id=request.workspace_id,
        question=request.question,
        role=request.role,
        answer=answer,
        sources=sources,
        stored_records=stored_records,
        candidates=candidates,
        llm_backend=llm_backend,
        llm_model=llm_model,
    )


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


@app.post("/ingest-file")
async def ingest_file(workspace_id: str = Form(...), file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix or ".tmp"
    temp_file = tempfile.NamedTemporaryFile("wb", delete=False, suffix=suffix)
    try:
        temp_file.write(await file.read())
        temp_file.close()
        doc = convert_to_markdown(temp_file.name)
        chunks = split_into_chunks(text=doc["content"], source=workspace_id)
        embeddings, _ = create_embeddings(chunks)
        store.add(workspace_id, chunks, embeddings)
        stored_records = len(store.get_workspace(workspace_id))
        chunks_count = len(chunks)
        embeddings_count = len(embeddings)
    finally:
        temp_file_path = temp_file.name
        if Path(temp_file_path).exists():
            Path(temp_file_path).unlink()

    return {
        "workspace_id": workspace_id,
        "ingested_count": 1,
        "chunks_count": chunks_count,
        "embeddings_count": embeddings_count,
        "stored_records": stored_records,
        "skipped": 0,
        "errors": [],
    }