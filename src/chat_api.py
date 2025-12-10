import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.db import Base, SessionLocal, engine
from src.embeddings import create_embeddings
from src.llm_pipeline import build_llm_chain, get_llm_answer
from src.repository import get_top_k_chunks_for_workspace
from src.models import Workspace, Document, Chunk  # noqa: F401


LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() == "true"
DEFAULT_ROLE = (
    "You are a helpful assistant that answers only based on the provided context. "
    "If the context is not enough, say: 'I do not know based on the provided context.'"
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(bind=engine)
    print("🗄️ Database schema initialized.")


class ChatRequest(BaseModel):
    workspace_id: str
    question: str
    role: str | None = None


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


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/workspaces")
def list_workspaces():
    db = SessionLocal()
    try:
        rows = db.query(Workspace).all()
        return {"workspaces": [workspace.id for workspace in rows]}
    finally:
        db.close()


@app.post("/chat")
def chat(request: ChatRequest):
    llm_backend = os.getenv("LLM_BACKEND", "ollama")
    llm_model = os.getenv("LLM_MODEL", "llama3.2:latest")

    query_chunks = [{"content": request.question}]
    query_embeddings, _ = create_embeddings(query_chunks)
    query_vector = query_embeddings[0].tolist()

    db = SessionLocal()
    try:
        chunk_objs = get_top_k_chunks_for_workspace(
            db=db,
            workspace_id=request.workspace_id,
            query_embedding=query_vector,
            k=3,
        )
        candidates = [
            {
                "content": chunk.content,
                "source": getattr(chunk.document, "source", None),
                "score": None,
            }
            for chunk in chunk_objs
        ]
        stored_records = len(candidates)
    finally:
        db.close()

    if stored_records == 0:
        answer = "This is a stub answer."
    else:
        context_parts = [c["content"] for c in candidates if c["content"]]
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