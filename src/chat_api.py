import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, distinct
from sqlalchemy.orm import Session

from src.db import Base, SessionLocal, engine
from src.embeddings import create_embeddings
from src.llm_pipeline import build_llm_chain, get_llm_answer
from src.repository import get_top_k_chunks_for_workspace
from src.models import Workspace, Document, Chunk, Note  # noqa: F401

import re

_NOISE_PATTERNS = [
    r"^\s*table of contents\b",
    r"^\s*contents\b",
    r"^\s*introduction\b",
    r"^\s*abstract\b",
    r"^\s*references\b",
    r"^\s*bibliography\b",
    r"^\s*literature\b",
    r"^\s*acknowledg(e)?ments\b",
    r"^\s*appendix\b",
    r"^\s*index\b",
]

def _is_noise_chunk(text: str) -> bool:
    if not text:
        return True

    t = text.strip()
    if len(t) < 120:  # too short to be useful as evidence
        return True

    lower = t.lower()

    # Drop “section header only” chunks.
    for pat in _NOISE_PATTERNS:
        if re.search(pat, lower):
            return True

    return False


TOP_K = int(os.getenv("TOP_K", "10"))
QUERY_REWRITE_ENABLED = os.getenv("QUERY_REWRITE_ENABLED", "true").lower() == "true"
QUERY_REWRITE_N = int(os.getenv("QUERY_REWRITE_N", "3"))
QUERY_REWRITE_TOP_K_PER_QUERY = int(os.getenv("QUERY_REWRITE_TOP_K_PER_QUERY", "5"))
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() == "true"
DEFAULT_ROLE = (
    "You are a helpful assistant that answers only based on the provided context. "
    "If the context is not enough, say: 'I do not know based on the provided context.'"
)

SYNTHESIS_ROLE = (
    "You are a helpful assistant. Use ONLY the provided context. "
    "Synthesize an answer by combining information from multiple context chunks. "
    "Do NOT use external knowledge. "
    "If the context is insufficient, say: 'I do not know based on the provided context.'"
)


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500", "http://localhost:5173"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=False,
)

def _rewrite_queries(question: str) -> list[str]:
    """
    Generate a few alternative search queries for better retrieval.
    Uses the same LLM backend. If rewriting fails, returns the original question.
    """
    if not LLM_ENABLED or not QUERY_REWRITE_ENABLED:
        return [question]

    rewrite_role = (
        "You rewrite a user's question into short search queries for semantic retrieval.\n"
        "Return 3 alternative queries (one per line), no numbering, no extra text.\n"
        "Use synonyms and related phrases that may appear in books.\n"
        "Do NOT answer the question."
    )

    try:
        chain = build_llm_chain(rewrite_role)
        raw = get_llm_answer(chain, question, context="")
        lines = [line.strip(" -\t\r\n") for line in raw.splitlines() if line.strip()]
        queries = []
        for q in lines:
            if q and q.lower() != question.lower():
                queries.append(q)
        # Always include the original question as well.
        merged = [question] + queries
        # Deduplicate preserving order.
        seen = set()
        out = []
        for q in merged:
            key = q.lower()
            if key not in seen:
                seen.add(key)
                out.append(q)
        return out[: max(1, QUERY_REWRITE_N + 1)]
    except Exception:
        return [question]


def _retrieve_candidates(db: Session, workspace_id: str, questions: list[str], k_per_query: int) -> list[Chunk]:
    """
    Retrieve top chunks for each query and merge results (unique by chunk id).
    """
    merged: list[Chunk] = []
    seen_ids: set[int] = set()

    for q in questions:
        query_chunks = [{"content": q}]
        query_embeddings, _ = create_embeddings(query_chunks)
        query_vector = query_embeddings[0].tolist()

        chunk_objs = get_top_k_chunks_for_workspace(
            db=db,
            workspace_id=workspace_id,
            query_embedding=query_vector,
            k=k_per_query,
        )

        for ch in chunk_objs:
            if _is_noise_chunk(getattr(ch, "content", "") or ""):
                continue

            ch_id = getattr(ch, "id", None)
            if ch_id is None:
                merged.append(ch)
                continue
            if ch_id not in seen_ids:
                seen_ids.add(ch_id)
                merged.append(ch)

    return merged


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(bind=engine)
    print("🗄️ Database schema initialized.")


class ChatRequest(BaseModel):
    workspace_id: str
    question: str
    role: str | None = None
    mode: str | None = "reference"  # "reference" | "synthesis" | "custom"



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
    mode: str | None = None


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
    sources: list[dict] = []
    created_at: str


class NotesListResponse(BaseModel):
    notes: list[NoteOut]


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/workspaces")
def list_workspaces():
    db: Session = SessionLocal()
    try:
        workspaces = []
        results = db.execute(
            select(distinct(Document.workspace_id)).order_by(Document.workspace_id)
        ).scalars().all()
        workspaces = [ws for ws in results if ws]
        if not workspaces:
            rows = db.query(Workspace).all()
            workspaces = [workspace.id for workspace in rows]
        return {"workspaces": workspaces}
    finally:
        db.close()


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

        notes = []
        for n in rows:
            notes.append(
                NoteOut(
                    id=n.id,
                    workspace_id=n.workspace_id,
                    question=n.question,
                    answer=n.answer,
                    sources=n.sources or [],
                    created_at=n.created_at.isoformat() if n.created_at else "",
                )
            )

        return NotesListResponse(notes=notes)
    finally:
        db.close()


@app.post("/chat")
def chat(request: ChatRequest):
    llm_backend = os.getenv("LLM_BACKEND", "ollama")
    llm_model = os.getenv("LLM_MODEL", "llama3.2:latest")

    search_queries = _rewrite_queries(request.question)

    db = SessionLocal()
    try:
        chunk_objs = _retrieve_candidates(
            db=db,
            workspace_id=request.workspace_id,
            questions=search_queries,
            k_per_query=QUERY_REWRITE_TOP_K_PER_QUERY if (QUERY_REWRITE_ENABLED and LLM_ENABLED) else TOP_K,
        )

        # Hard cap total candidates to TOP_K (keep first ones).
        chunk_objs = chunk_objs[:TOP_K]

        candidates = [
            {
                "chunk_id": getattr(chunk, "id", None),
                "document_id": getattr(chunk, "document_id", None),
                "chunk_index": getattr(chunk, "index", None),
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
            mode = (request.mode or "reference").strip().lower()

            if mode == "synthesis":
                effective_role = SYNTHESIS_ROLE
            elif mode == "custom":
                effective_role = (
                    request.role.strip()
                    if request.role and request.role.strip()
                    else DEFAULT_ROLE
                )
            else:  # reference
                effective_role = DEFAULT_ROLE

            chain = build_llm_chain(effective_role)
            answer = get_llm_answer(chain, request.question, context)

    sources = [
        {
            "chunk_id": candidate.get("chunk_id"),
            "document_id": candidate.get("document_id"),
            "chunk_index": candidate.get("chunk_index"),
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
        mode=request.mode,
    )