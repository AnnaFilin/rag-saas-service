# =========================
# (FastAPI app + endpoints; imports helpers)
# =========================

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, distinct, text
from sqlalchemy.orm import Session

from src.db import Base, SessionLocal, engine
from src.embeddings import create_embeddings
from src.llm_pipeline import build_llm_chain, get_llm_answer
from src.repository import get_top_k_chunks_for_workspace, get_top_k_chunks_fts
from src.models import Workspace, Document, Chunk, Note  # noqa: F401

from src.chat_helpers import (
    _retrieve_candidates,
    _rewrite_queries,
    focus_by_entity,
    llm_filter_relevant_chunks,
    _fact_density_score,
)


# =========================
# CONFIG
# =========================

QUERY_REWRITE_ENABLED = os.getenv("QUERY_REWRITE_ENABLED", "true").lower() == "true"
QUERY_REWRITE_N = int(os.getenv("QUERY_REWRITE_N", "3"))
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() == "true"
QUERY_REWRITE_TOP_K_PER_QUERY = 20

TOP_K = 20


DEFAULT_ROLE = (
    "You are a helpful assistant. Answer ONLY using the provided context.\n"
    "If the user asks multiple things, answer the parts that ARE supported by the context.\n"
    "For each part that is NOT supported by the context, explicitly say it is not found in the provided context.\n"
    "Do NOT use external knowledge.\n"
)


SYNTHESIS_ROLE = (
    "You are a helpful assistant. Use ONLY the provided context.\n"
    "Synthesize an answer by combining information from multiple context chunks.\n"
    "If the user asks multiple things, answer the supported parts and mark missing parts as not found in the provided context.\n"
    "Do NOT use external knowledge.\n"
    "\n"
    "Grounding rules:\n"
    "- Treat each chunk as independent evidence; do not assume facts apply across different entities.\n"
    "- Include a claim only if it is explicitly stated in at least one chunk.\n"
    "- If chunks contain information about other entities unrelated to the question, ignore those parts.\n"
)


# =========================
# APP
# =========================

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500", "http://localhost:5173"],
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


# =========================
# API ENDPOINTS
# =========================

@app.get("/debug/search_chunks")
def debug_search_chunks(workspace_id: str, q: str, limit: int = 20):
    db: Session = SessionLocal()
    try:
        rows = db.execute(
            text("""
                select
                    c.id as chunk_id,
                    c.document_id as document_id,
                    c."index" as chunk_index,
                    d.source as source,
                    left(c.content, 400) as preview
                from chunks c
                join documents d on d.id = c.document_id
                where d.workspace_id = :workspace_id
                  and lower(c.content) like :pattern
                order by c.id desc
                limit :limit
            """),
            {
                "workspace_id": workspace_id,
                "pattern": f"%{q.lower()}%",
                "limit": limit,
            },
        ).mappings().all()

        return {"count": len(rows), "rows": [dict(r) for r in rows]}
    finally:
        db.close()


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
    mode = (request.mode or "reference").strip().lower()

    # =========================
    # 1. Build search queries (MODE-DEPENDENT)
    # =========================

    if mode in ("reference", "synthesis"):
        # STRICT modes:
        # - no rewrite
        # - no expansion
        # - one question = one retrieval intent
        search_queries = [request.question]

    elif mode == "custom":
        # Exploratory / power-user mode:
        # rewrite is allowed
        search_queries = _rewrite_queries(
            request.question,
            llm_enabled=LLM_ENABLED,
            query_rewrite_enabled=QUERY_REWRITE_ENABLED,
            query_rewrite_n=QUERY_REWRITE_N,
            build_llm_chain=build_llm_chain,
            get_llm_answer=get_llm_answer,
        )
        if not search_queries:
            search_queries = [request.question]

    else:
        # Safety fallback
        search_queries = [request.question]

    print("🚨 Search Queries: 🚨")
    print(search_queries)
    print("🚨 Search Queries: 🚨")

    # =========================
    # 2. Retrieval
    # =========================

    db = SessionLocal()
    try:
        chunk_objs = _retrieve_candidates(
            db=db,
            workspace_id=request.workspace_id,
            questions=search_queries,
            k_per_query=TOP_K,
            create_embeddings=create_embeddings,
            get_top_k_chunks_for_workspace=get_top_k_chunks_for_workspace,
            get_top_k_chunks_fts=get_top_k_chunks_fts,
        )

        # Entity focus is OK for all modes
        chunk_objs = focus_by_entity(chunk_objs, request.question)

        if mode == "custom":
            chunk_objs.sort(key=lambda ch: _fact_density_score(getattr(ch, "content", "")), reverse=True)

        CONTEXT_K = 8
        chunk_objs = chunk_objs[:CONTEXT_K]
  

        candidates = [
            {
                "chunk_id": getattr(chunk, "id", None),
                "document_id": getattr(chunk, "document_id", None),
                "chunk_index": getattr(chunk, "index", None),
                "content": chunk.content,
                "source": getattr(chunk.document, "source", None),
                "score": getattr(chunk, "_distance", None),
            }
            for chunk in chunk_objs
        ]

        # LLM relevance filter is OK for synthesis/custom
        # For reference it is conservative but acceptable
        candidates = llm_filter_relevant_chunks(
            request.question,
            candidates,
            build_llm_chain=build_llm_chain,
            get_llm_answer=get_llm_answer,
        )

        stored_records = len(candidates)

    finally:
        db.close()

    # =========================
    # 3. Empty result handling
    # =========================

    if stored_records == 0:
        answer = "This information is not found in the provided sources."

    else:
        context_parts = [c["content"] for c in candidates if c["content"]]
        context = "\n\n---\n\n".join(context_parts)

        if not LLM_ENABLED:
            answer = "LLM is temporarily disabled. Please try again later."

        else:
            # =========================
            # 4. Mode-specific answering
            # =========================

            if mode == "reference":
                q = request.question.lower()
                if " and " in q or "," in q or ";" in q:
                    return ChatResponse(
                        workspace_id=request.workspace_id,
                        question=request.question,
                        role=request.role,
                        answer=(
                            "Reference mode supports only ONE atomic question. "
                            "Please split your question or use synthesis mode."
                        ),
                        sources=[],
                        stored_records=0,
                        candidates=[],
                        llm_backend=llm_backend,
                        llm_model=llm_model,
                        mode=mode,
                    )
                effective_role = DEFAULT_ROLE

            elif mode == "synthesis":
                effective_role = SYNTHESIS_ROLE

            elif mode == "custom":
                effective_role = (
                    request.role.strip()
                    if request.role and request.role.strip()
                    else DEFAULT_ROLE
                )

            else:
                effective_role = DEFAULT_ROLE


            print("🚨 LLM WILL BE CALLED 🚨")

            if mode == "custom":
                chain = build_llm_chain(
                    effective_role,
                    append_default_rules=False,
                )
            else:
                chain = build_llm_chain(effective_role)

            answer = get_llm_answer(chain, request.question, context)


    # =========================
    # 5. Response
    # =========================

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

        documents = []
        for doc in rows:
            documents.append(
                {
                    "id": doc.id,
                    "workspace_id": doc.workspace_id,
                    "source": doc.source,
                    "created_at": getattr(doc, "created_at", None),
                }
            )

        return {"documents": documents}
    finally:
        db.close()
