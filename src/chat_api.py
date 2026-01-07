# =========================
# FastAPI app + endpoints
# SINGLE MODE, UNIVERSAL RAG
# =========================

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, distinct
from sqlalchemy.orm import Session

from src.db import Base, SessionLocal, engine
from src.embeddings import create_embeddings
from src.llm_pipeline import build_llm_chain, get_llm_answer
from src.repository import get_top_k_chunks_for_workspace, get_top_k_chunks_fts
from src.models import Workspace, Document, Chunk, Note  # noqa: F401

from src.chat_helpers import (
    _retrieve_candidates,
    focus_by_entity,
    llm_filter_relevant_chunks,
)

# =========================
# CONFIG
# =========================

LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() == "true"
TOP_K = 20
CONTEXT_K = 8

DEFAULT_ROLE = (
    "You are a helpful assistant.\n"
    "Answer ONLY using the provided context.\n"
    "If information is missing, explicitly say it is not found in the provided sources.\n"
    "Do NOT use external knowledge.\n"
)

# =========================
# APP
# =========================

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5173",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(bind=engine)
    print("🗄️ Database schema initialized.")


# =========================
# TYPES
# =========================

class ChatRequest(BaseModel):
    workspace_id: str
    question: str
    role: str | None = None


class ChatResponse(BaseModel):
    workspace_id: str
    question: str
    role: str | None
    answer: str
    sources: list[dict]
    stored_records: int
    llm_backend: str
    llm_model: str


class NoteCreateRequest(BaseModel):
    workspace_id: str
    question: str
    answer: str
    sources: list[dict] = []


class NoteCreateResponse(BaseModel):
    id: int
    workspace_id: str
    created_at: str


class NoteOut(BaseModel):
    id: int
    workspace_id: str
    question: str
    answer: str
    sources: list[dict]
    created_at: str


class NotesListResponse(BaseModel):
    notes: list[NoteOut]


# =========================
# API
# =========================

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/workspaces")
def list_workspaces():
    db: Session = SessionLocal()
    try:
        results = db.execute(
            select(distinct(Document.workspace_id)).order_by(Document.workspace_id)
        ).scalars().all()
        if results:
            return {"workspaces": [ws for ws in results if ws]}
        rows = db.query(Workspace).all()
        return {"workspaces": [w.id for w in rows]}
    finally:
        db.close()


@app.post("/chat")
def chat(request: ChatRequest):
    llm_backend = os.getenv("LLM_BACKEND", "ollama")
    llm_model = os.getenv("LLM_MODEL", "llama3.2:latest")

    effective_role = (
        request.role.strip()
        if request.role and request.role.strip()
        else DEFAULT_ROLE
    )

    db = SessionLocal()
    try:
        # 1) Retrieval
        chunk_objs = _retrieve_candidates(
            db=db,
            workspace_id=request.workspace_id,
            questions=[request.question],
            k_per_query=TOP_K,
            create_embeddings=create_embeddings,
            get_top_k_chunks_for_workspace=get_top_k_chunks_for_workspace,
            get_top_k_chunks_fts=get_top_k_chunks_fts,
        )

        # 2) Optional entity focus (already guarded inside helper)
        chunk_objs = focus_by_entity(chunk_objs, request.question)

        # 3) Build candidates from MORE than final context (so LLM-filter has room)
        pre_limit = max(CONTEXT_K, min(TOP_K, 20))
        chunk_objs = chunk_objs[:pre_limit]

        candidates = [
            {
                "chunk_id": getattr(ch, "id", None),
                "document_id": getattr(ch, "document_id", None),
                "chunk_index": getattr(ch, "index", None),
                "content": ch.content,
                "source": getattr(ch.document, "source", None),
                "score": getattr(ch, "_distance", None),
            }
            for ch in chunk_objs
        ]

        # 4) LLM relevance filter + fallback (never empty after retrieval)
        filtered = llm_filter_relevant_chunks(
            request.question,
            candidates,
            build_llm_chain=build_llm_chain,
            get_llm_answer=get_llm_answer,
        )
        if filtered:
            candidates = filtered

        # 5) Final context truncation AFTER filter
        candidates = candidates[:CONTEXT_K]

        stored_records = len(candidates)

    finally:
        db.close()

    # 6) Answering
    if stored_records == 0:
        answer = "This information is not found in the provided sources."
    elif not LLM_ENABLED:
        answer = "LLM is temporarily disabled."
    else:
        context = "\n\n---\n\n".join(
            c["content"] for c in candidates if c.get("content")
        )
        chain = build_llm_chain(effective_role)
        answer = get_llm_answer(chain, request.question, context)

    return ChatResponse(
        workspace_id=request.workspace_id,
        question=request.question,
        role=request.role,
        answer=answer,
        sources=candidates,
        stored_records=stored_records,
        llm_backend=llm_backend,
        llm_model=llm_model,
    )


@app.post("/notes")
def create_note(request: NoteCreateRequest):
    db: Session = SessionLocal()
    try:
        note = Note(
            workspace_id=request.workspace_id,
            question=request.question,
            answer=request.answer,
            sources=request.sources or [],
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        return NoteCreateResponse(
            id=note.id,
            workspace_id=note.workspace_id,
            created_at=note.created_at.isoformat() if note.created_at else "",
        )
    finally:
        db.close()


@app.get("/notes")
def list_notes(workspace_id: str):
    db: Session = SessionLocal()
    try:
        rows = (
            db.query(Note)
            .filter(Note.workspace_id == workspace_id)
            .order_by(Note.created_at.desc())
            .all()
        )
        return NotesListResponse(
            notes=[
                NoteOut(
                    id=n.id,
                    workspace_id=n.workspace_id,
                    question=n.question,
                    answer=n.answer,
                    sources=n.sources or [],
                    created_at=n.created_at.isoformat() if n.created_at else "",
                )
                for n in rows
            ]
        )
    finally:
        db.close()


@app.get("/documents")
def list_documents(workspace_id: str):
    db: Session = SessionLocal()
    try:
        rows = (
            db.execute(
                select(Document)
                .where(Document.workspace_id == workspace_id)
                .order_by(Document.id.desc())
            )
            .scalars()
            .all()
        )
        return {
            "documents": [
                {
                    "id": d.id,
                    "workspace_id": d.workspace_id,
                    "source": d.source,
                    "created_at": getattr(d, "created_at", None),
                }
                for d in rows
            ]
        }
    finally:
        db.close()
