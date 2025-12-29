import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, distinct, text
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


def _extract_focus_terms(text: str) -> list[str]:
    """
    Extract focus terms from the user question.
    Universal: derives terms from the question itself (no domain hardcode).
    """
    if not text:
        return []

    t = text.strip()

    terms: set[str] = set()

    # 1) Latin binomial like "Hypericum perforatum"
    for m in re.findall(r"\b([A-Z][a-z]+)\s+([a-z]{2,})\b", t):
        terms.add(f"{m[0]} {m[1]}")
        terms.add(m[0])
        terms.add(m[1])

    # 2) Anything inside parentheses: "(St. John's Wort)"
    for p in re.findall(r"\(([^)]+)\)", t):
        p = p.strip()
        if len(p) >= 3:
            terms.add(p)

    # 3) Quoted phrases
    for q in re.findall(r"\"([^\"]+)\"", t):
        q = q.strip()
        if len(q) >= 3:
            terms.add(q)

    # 4) Fallback: long words (helps when no binomial)
    words = re.findall(r"[A-Za-z][A-Za-z'\-]{3,}", t)
    for w in words:
        if len(w) >= 5:
            terms.add(w)

    # normalize
    cleaned = []
    for term in terms:
        term = term.strip()
        if term:
            cleaned.append(term)

    return cleaned

# def _extract_focus_terms(question: str) -> list[str]:
#     if not question:
#         return []

#     q = question.strip()
#     terms: list[str] = []

#     # 1) Quoted phrases: "..." or '...'
#     for m in re.finditer(r'(["\'])(.+?)\1', q):
#         phrase = m.group(2).strip()
#         if len(phrase) >= 3:
#             terms.append(phrase)

#     # 2) Parentheses content: ( ... )
#     for m in re.finditer(r"\(([^)]+)\)", q):
#         inside = m.group(1).strip()
#         if len(inside) >= 3:
#             terms.append(inside)

#     # 3) Latin binomial: Genus species (very common in bio, but harmless elsewhere)
#     m = re.search(r"\b([A-Z][a-z]{2,})\s+([a-z]{3,})\b", q)
#     if m:
#         terms.append(m.group(1))
#         terms.append(m.group(2))
#         terms.append(f"{m.group(1)} {m.group(2)}")

#     # 4) Tokens that look like identifiers / names / acronyms / versions
#     #    - CamelCase, ALLCAPS, snake_case, kebab-case, dotted.tokens, v1, 3.2, 2024
#     token_re = re.compile(
#         r"\b("
#         r"[A-Z]{2,}"                          # ALLCAPS
#         r"|[A-Z][a-z]+(?:[A-Z][a-z]+)+"       # CamelCase
#         r"|[a-z]+(?:_[a-z0-9]+)+"             # snake_case
#         r"|[a-z]+(?:-[a-z0-9]+)+"             # kebab-case
#         r"|[A-Za-z]+(?:\.[A-Za-z0-9]+)+"      # dotted tokens
#         r"|v?\d+(?:\.\d+)+"                   # versions like 3.2, v1.2
#         r"|\d{4}"                             # years like 2024
#         r")\b"
#     )
#     for t in token_re.findall(q):
#         if len(t) >= 2:
#             terms.append(t)

#     # 5) Fallback: unique “meaningful” words (letters only) length>=5
#     #    No stoplist; just avoids tiny glue-words by length.
#     for w in re.findall(r"\b[A-Za-z]{5,}\b", q):
#         terms.append(w)

#     # Deduplicate, keep order, cap to avoid over-filtering
#     seen = set()
#     out: list[str] = []
#     for t in terms:
#         key = t.lower()
#         if key not in seen:
#             seen.add(key)
#             out.append(t)

#     return out[:12]


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

# DEFAULT_ROLE = (
#     "You are a helpful assistant that answers only based on the provided context. "
#     "If the context is not enough, say: 'I do not know based on the provided context.'"
# )

# SYNTHESIS_ROLE = (
#     "You are a helpful assistant. Use ONLY the provided context. "
#     "Synthesize an answer by combining information from multiple context chunks. "
#     "Do NOT use external knowledge. "
#     "If the context is insufficient, say: 'I do not know based on the provided context.'"
# )
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


def is_multi_question(q: str) -> bool:
    q = q.lower()
    return any(sep in q for sep in [" and ", ",", ";"])



# def _retrieve_candidates(db: Session, workspace_id: str, questions: list[str], k_per_query: int) -> list[Chunk]:
#     """
#     Retrieve top chunks for each query and merge results (unique by chunk id).
#     """
#     merged: list[Chunk] = []
#     seen_ids: set[int] = set()

#     for q in questions:
#         query_chunks = [{"content": q}]
#         query_embeddings, _ = create_embeddings(query_chunks)
#         query_vector = query_embeddings[0].tolist()

#         chunk_objs = get_top_k_chunks_for_workspace(
#             db=db,
#             workspace_id=workspace_id,
#             query_embedding=query_vector,
#             k=k_per_query,
#         )

#         for ch in chunk_objs:
#             if _is_noise_chunk(getattr(ch, "content", "") or ""):
#                 continue

#             ch_id = getattr(ch, "id", None)
#             if ch_id is None:
#                 merged.append(ch)
#                 continue
#             if ch_id not in seen_ids:
#                 seen_ids.add(ch_id)
#                 merged.append(ch)

#     return merged
def _retrieve_candidates(
    db: Session,
    workspace_id: str,
    questions: list[str],
    k_per_query: int,
    # focus_terms: list[str],
) -> list[Chunk]:
    """
    Retrieve top chunks for each query and merge results (unique by chunk id).

    Expects get_top_k_chunks_for_workspace() to return:
        list[tuple[Chunk, float]]  # (chunk, distance)
    where lower distance => more similar.

    Attaches a temporary attribute `_distance` to each Chunk for downstream scoring.
    """
    merged: list[Chunk] = []
    seen_ids: set[int] = set()


    for q in questions:
        query_chunks = [{"content": q}]
        query_embeddings, _ = create_embeddings(query_chunks)
        query_vector = query_embeddings[0].tolist()

        rows = get_top_k_chunks_for_workspace(
            db=db,
            workspace_id=workspace_id,
            query_embedding=query_vector,
            k=k_per_query,
        )

        for ch, dist in rows:
            content = getattr(ch, "content", "") or ""
            if _is_noise_chunk(content):
                continue

            setattr(ch, "_distance", dist)

            ch_id = getattr(ch, "id", None)
            if ch_id is None:
                merged.append(ch)
                continue

            if ch_id not in seen_ids:
                seen_ids.add(ch_id)
                merged.append(ch)

        # Sort by best (smallest) distance first
    merged.sort(key=lambda ch: getattr(ch, "_distance", float("inf")))
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
        chunk_objs = sorted(chunk_objs, key=lambda ch: getattr(ch, "_distance", 999.0))
        chunk_objs = chunk_objs[:TOP_K]


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
        stored_records = len(candidates)
    finally:
        db.close()


    if stored_records == 0:
        answer = "This is a stub answer."
    else:
        # question_lower = request.question.lower()
        # context_parts = [
        #     c["content"]
        #     for c in candidates
        #     if c["content"] and any(
        #         token in c["content"].lower()
        #         for token in question_lower.split()
        #         if len(token) > 4
        #     )
        # ]

        # if not context_parts:
        #     context_parts = [c["content"] for c in candidates if c["content"]]
        context_parts = [c["content"] for c in candidates if c["content"]]
        context = "\n\n---\n\n".join(context_parts)

        print("🚨 Context: 🚨")
        print(context)
        print("🚨 Context: 🚨")

        if not LLM_ENABLED:
            answer = "LLM is temporarily disabled. Please try again later."
        else:
            mode = (request.mode or "reference").strip().lower()

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


            print("🚨 LLM WILL BE CALLED 🚨")

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
