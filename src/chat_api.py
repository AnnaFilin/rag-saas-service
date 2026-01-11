# =========================
# FastAPI app + endpoints
# SINGLE MODE, UNIVERSAL RAG
# =========================

import os

from fastapi import FastAPI, HTTPException
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
    rerank_by_lexical_overlap,
    llm_filter_relevant_chunks,
    _passes_coverage_gate,
    _extract_subject_phrase,
    deterministic_filter_relevant_chunks,
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

STRICT_ANSWER_ROLE = (
    "You are a strict QA assistant.\n"
    "Answer ONLY using the provided context.\n"
    "Do NOT use outside knowledge.\n"
    "Do NOT infer or guess.\n"
    "If the context does NOT explicitly contain the answer, reply exactly:\n"
    "Not stated in the provided context.\n"
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
    print("=== CHAT HANDLER HIT: V2_MARKER_2026_01_07 ===", __file__)

    llm_backend = os.getenv("LLM_BACKEND", "ollama")
    llm_model = os.getenv("LLM_MODEL", "llama3.2:latest")

    # LLM filter toggle (defaults ON)
    llm_filter_enabled = (
        os.getenv("LLM_FILTER_ENABLED", "1").strip().lower() not in ("0", "false", "no")
    )
    print("DBG LLM_FILTER_ENABLED =", llm_filter_enabled)

    effective_role = (
        request.role.strip()
        if request.role and request.role.strip()
        else DEFAULT_ROLE
    )

    db = SessionLocal()
    candidates: list[dict] = []
    stored_records = 0

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

        chunk_objs = rerank_by_lexical_overlap(
            chunk_objs,
            request.question,
        )

        # 🔒 Snapshot content to avoid any ORM/lazy-load/state weirdness
        for ch in chunk_objs:
            ch._content_snapshot = ch.content

        print("\n=== DEBUG RETRIEVAL (after rerank, before subject/LLM) ===")
        for i, ch in enumerate(chunk_objs[:20]):
            text = (ch.content or "")[:200].replace("\n", " ")
            print(
                f"[{i}] "
                f"doc={getattr(ch, 'document_id', None)} "
                f"chunk={getattr(ch, 'id', None)} "
                f"score={getattr(ch, '_distance', None)} "
                f"text={text}"
            )

        # 2) Build candidates (pre-limit so filter has room)
        pre_limit = max(CONTEXT_K, min(TOP_K, 20))
        chunk_objs = chunk_objs[:pre_limit]

        print("\n=== DEBUG CONTENT IDS ===")
        for i, ch in enumerate(chunk_objs[:10]):
            print(i, "chunk_id=", getattr(ch, "id", None), "content_id=", id(ch.content))

        candidates = [
            {
                "chunk_id": getattr(ch, "id", None),
                "document_id": getattr(ch, "document_id", None),
                "chunk_index": getattr(ch, "index", None),
                "content": getattr(ch, "_content_snapshot", ch.content),
                "source": getattr(getattr(ch, "document", None), "source", None),
                "score": getattr(ch, "_distance", None),
            }
            for ch in chunk_objs
        ]

        subject = _extract_subject_phrase(request.question)
        print("DBG subject =", repr(subject))
        print("DBG candidates before subject filter =", len(candidates))

        if subject:
            subj_l = subject.lower()
            candidates = [
                c for c in candidates
                if subj_l in (c.get("content") or "").lower()
            ]

        print("DBG candidates after subject filter =", len(candidates))

        print("\n=== DEBUG CANDIDATES (before filtering) ===")
        for i, c in enumerate(candidates[:20]):
            text = (c.get("content") or "")[:200].replace("\n", " ")
            print(
                f"[{i}] "
                f"doc={c.get('document_id')} "
                f"chunk={c.get('chunk_id')} "
                f"score={c.get('score')} "
                f"text={text}"
            )

        # Freeze content (defensive): keep original content stable across filter steps
        for c in candidates:
            c["_content_frozen"] = c.get("content")

        # 3) Filtering (LLM filter optional; deterministic filter when LLM filter is OFF)
        if llm_filter_enabled:
            filtered = llm_filter_relevant_chunks(
                request.question,
                candidates,
                build_llm_chain=build_llm_chain,
                get_llm_answer=get_llm_answer,
            )
        else:
            # NOTE: implement this helper in your helpers file
            # It MUST be workspace-agnostic and NOT use domain keywords.
            filtered = deterministic_filter_relevant_chunks(request.question, candidates)

        # Restore frozen content if any filter mutated/overwrote it
        for c in filtered:
            if "_content_frozen" in c:
                c["content"] = c["_content_frozen"]

        print("\n=== DEBUG AFTER FILTER ===")
        for i, c in enumerate(filtered[:20]):
            text = (c.get("content") or "")[:200].replace("\n", " ")
            print(
                f"[{i}] "
                f"doc={c.get('document_id')} "
                f"chunk={c.get('chunk_id')} "
                f"score={c.get('score')} "
                f"text={text}"
            )

        # Deterministic guardrail: no keyword overlap => no coverage (workspace-agnostic).
        if filtered and not _passes_coverage_gate(request.question, filtered):
            filtered = []

        if not filtered:
            # No coverage => return empty sources
            candidates = []
            stored_records = 0
        else:
            candidates = filtered

            # 4) Final context truncation (only when coverage exists)
            candidates.sort(key=lambda c: (c["score"] is None, c["score"]))
            candidates = candidates[:CONTEXT_K]
            stored_records = len(candidates)

    finally:
        db.close()

    print(
        "=== DEBUG ===",
        "stored_records=", stored_records,
        "len(candidates)=", len(candidates)
    )

    # 5) Answering (this is separate from the LLM filter toggle)
    if stored_records == 0:
        answer = "I do not know based on the provided context."
    elif not LLM_ENABLED:
        answer = "LLM is temporarily disabled."
    else:
        context = "\n\n---\n\n".join(
            c["content"] for c in candidates
            if c.get("content")
        )

        # ✅ Logs in the correct place (final answering)
        print("\n=== DEBUG ANSWER INPUT ===")
        print("DBG stored_records =", stored_records)
        print("DBG context_chars =", len(context))
        print("DBG role_used = STRICT_ANSWER_ROLE")  # keep it explicit

        # ✅ Use strict role for final answering (prevents 'it can be inferred')
        role_for_answer = request.role.strip() if request.role and request.role.strip() else STRICT_ANSWER_ROLE
        print("DBG role_used =", "request.role" if role_for_answer != STRICT_ANSWER_ROLE else "STRICT_ANSWER_ROLE")
        chain = build_llm_chain(role_for_answer)
        answer = get_llm_answer(chain, request.question, context)


        # Hard normalization: forbid mixed "answered + I do not know"
        lower = (answer or "").strip().lower()

        # If model appended generic fallback, remove it.
        bad_tail = "i do not know based on the provided context."
        if bad_tail in lower:
            # keep everything before the bad tail
            cut = lower.find(bad_tail)
            answer = answer[:cut].strip()

        if any(x in (answer or "").lower() for x in ["inferred", "implies", "it can be inferred"]):
            answer = "Not stated in the provided context."

        # If answer is empty after cleanup -> strict fallback
        if not answer.strip():
            answer = "Not stated in the provided context."

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


@app.delete("/notes/{note_id}")
def delete_note(note_id: int):
    db: Session = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")

        db.delete(note)
        db.commit()
        return {"ok": True}
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
