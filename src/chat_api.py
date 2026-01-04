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
from typing import List

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

def normalize_query_for_retrieval(question: str) -> str:
    """
    Convert a natural language question into a search-like phrase
    suitable for semantic retrieval.
    """
    q = question.lower()

    # remove common instruction words
    for junk in [
        "summarize",
        "based on the provided sources",
        "based on the sources",
        "based on sources",
        "please",
        "what are",
        "what is",
        "give me",
        "provide",
        "?",
    ]:
        q = q.replace(junk, "")

    # collapse whitespace
    q = " ".join(q.split())

    return q


def focus_by_entity(chunks: List, question: str, min_keep: int = 3) -> List:
    """
    Post-filter chunks by main entity mentioned in the question.
    Universal: works for plants, places, people, terms.
    If filtering becomes too aggressive, falls back to original chunks.
    """

    q = question.lower()

    # very simple entity extraction: longest capitalized phrase OR latin binomial
    latin_match = re.findall(r"\b[a-z]+ [a-z]+\b", q)
    entity_terms = set(latin_match)

    if not entity_terms:
        # fallback: meaningful words from question
        entity_terms = {
            w for w in re.findall(r"[a-z]{5,}", q)
            if w not in {"which", "about", "include", "describe", "traditional", "documented"}
        }

    if not entity_terms:
        return chunks

    focused = []
    for ch in chunks:
        text = (ch.content or "").lower()
        if any(term in text for term in entity_terms):
            focused.append(ch)

    # safety fallback
    if len(focused) < min_keep:
        return chunks

    return focused

def extract_entity_from_question(question: str) -> str | None:
    if not question:
        return None

    # Try Latin binomial: Genus species
    m = re.search(r"\b([A-Z][a-z]{2,}\s+[a-z]{2,})\b", question)
    if m:
        return m.group(1).lower()

    # Fallback: longest meaningful word
    tokens = re.findall(r"[a-zA-Z]{5,}", question.lower())
    if not tokens:
        return None

    return max(tokens, key=len)


# def _is_noise_chunk(text: str) -> bool:
#     if not text:
#         return True

#     t = text.strip()
#     if len(t) < 120:
#         return True

#     lower = t.lower()

#     # Headings/sections to drop
#     for pat in _NOISE_PATTERNS:
#         if re.search(pat, lower):
#             return True

#     lines = [ln.strip() for ln in t.splitlines() if ln.strip()]

#     # 1) List-like chunks (taxonomic lists, indices, enumerations)
#     if len(lines) >= 8:
#         short_lines = sum(1 for ln in lines if len(ln) <= 40)
#         if short_lines / len(lines) >= 0.6:
#             return True

#     # 2) Low-sentence / low-language signal:
#     # if almost no sentence punctuation, it's usually a list/table/metadata.
#     punct = sum(t.count(ch) for ch in ".?!;:")
#     if punct <= 1 and len(lines) >= 6:
#         return True

#     # 3) Excessively "catalog-like": too many commas vs. text
#     comma_ratio = (t.count(",") / max(1, len(t)))
#     if comma_ratio > 0.03 and punct <= 2:
#         return True

#     return False

def _is_noise_chunk(text: str) -> bool:
    """
    Conservative, universal noise filter.

    Goal:
    - Drop obvious boilerplate (TOC/References/Index/etc.)
    - Drop very short fragments
    - Drop very list/table-like chunks
    Without over-filtering normal prose split into many short lines (common after PDF->MD).
    """
    if not text:
        return True

    t = text.strip()
    if len(t) < 120:
        return True

    lower = t.lower()

    # Obvious section headers / boilerplate
    for pat in _NOISE_PATTERNS:
        if re.search(pat, lower):
            return True

    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    if not lines:
        return True

    # If the chunk is mostly very short lines AND has weak sentence signal,
    # it's usually a table, catalog, index, or list.
    short_lines = sum(1 for ln in lines if len(ln) <= 40)
    short_ratio = short_lines / max(1, len(lines))

    # Sentence signal (we treat dot as weak because PDF->MD can drop punctuation)
    punct = sum(t.count(ch) for ch in "?!;:")

    # Digit-heavy catalogs / tables (IDs, measurements, tabular content)
    digit_ratio = sum(ch.isdigit() for ch in t) / max(1, len(t))

    # Comma-heavy + low punctuation tends to be enumerations / catalog rows
    comma_ratio = t.count(",") / max(1, len(t))

    # Stronger "table/list" heuristic:
    # - many short lines (>=70%) OR digit-heavy
    # - and no clear sentence punctuation
    if (short_ratio >= 0.70 or digit_ratio >= 0.12) and punct <= 1:
        return True

    # Another common pattern: comma-separated enumerations with low punctuation
    if comma_ratio > 0.03 and punct == 0 and len(lines) >= 6:
        return True

    return False


# TOP_K = int(os.getenv("TOP_K", "10"))
QUERY_REWRITE_ENABLED = os.getenv("QUERY_REWRITE_ENABLED", "true").lower() == "true"
QUERY_REWRITE_N = int(os.getenv("QUERY_REWRITE_N", "3"))
# QUERY_REWRITE_TOP_K_PER_QUERY = int(os.getenv("QUERY_REWRITE_TOP_K_PER_QUERY", "5"))
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



def llm_filter_relevant_chunks(
    question: str,
    candidates: list[dict],
) -> list[dict]:
    """
    Ask LLM which chunks are actually relevant to the question.
    Returns a filtered subset of candidates.
    """

    if not candidates:
        return candidates

    # Build a compact list for the LLM
    items = []
    for i, c in enumerate(candidates):
        text = (c.get("content") or "").strip()
        preview = text[:300].replace("\n", " ")
        items.append(f"[{i}] {preview}")

    filter_prompt = (
        "You are given a question and a list of text chunks.\n"
        "Select ONLY the chunks that contain information directly relevant to the question.\n"
        "Ignore chunks about other entities, lists, tables, catalogs, or unrelated topics.\n\n"
        "Return ONLY a comma-separated list of indices (for example: 0,2,3).\n"
        "If none are relevant, return an empty line.\n\n"
        f"Question:\n{question}\n\n"
        "Chunks:\n" + "\n".join(items)
    )

    try:
        chain = build_llm_chain(
            "You are a strict relevance filter. Do not explain anything."
        )
        raw = get_llm_answer(chain, filter_prompt, context="")

        indices = [
            int(x.strip())
            for x in raw.split(",")
            if x.strip().isdigit()
        ]

        return [
            candidates[i]
            for i in indices
            if 0 <= i < len(candidates)
        ]

    except Exception:
        # Fail safe: return original candidates
        return candidates



def is_multi_question(q: str) -> bool:
    q = q.lower()
    return any(sep in q for sep in [" and ", ",", ";"])


# def _retrieve_candidates(
#     db: Session,
#     workspace_id: str,
#     questions: list[str],
#     k_per_query: int,
#     # anchor_question: str,
#     # focus_terms: list[str],
# ) -> list[Chunk]:
#     """
#     Retrieve top chunks for each query and merge results (unique by chunk id).

#     Expects get_top_k_chunks_for_workspace() to return:
#         list[tuple[Chunk, float]]  # (chunk, distance)
#     where lower distance => more similar.

#     Attaches a temporary attribute `_distance` to each Chunk for downstream scoring.
#     """
#     merged: list[Chunk] = []
#     seen_ids: set[int] = set()


#     for q in questions:
#         normalized_q = normalize_query_for_retrieval(q)
#         query_chunks = [{"content": normalized_q}]
#         query_embeddings, _ = create_embeddings(query_chunks)
#         query_vector = query_embeddings[0].tolist()

#         print("[DEBUG] q:", q)
#         print("[DEBUG] type(query_vector):", type(query_vector))
#         print("[DEBUG] len(query_vector):", len(query_vector) if isinstance(query_vector, list) else "not a list")
#         print("[DEBUG] first3:", query_vector[:3] if isinstance(query_vector, list) else query_vector)

#         if not isinstance(query_vector, list) or (query_vector and isinstance(query_vector[0], list)) or len(query_vector) != 768:
#             raise ValueError(f"query_vector is invalid: type={type(query_vector)} len={len(query_vector) if hasattr(query_vector,'__len__') else 'n/a'} sample={str(query_vector)[:120]}")

#         rows = get_top_k_chunks_for_workspace(
#             db=db,
#             workspace_id=workspace_id,
#             query_embedding=query_vector,
#             # question=q,         
#             k=k_per_query,    
#         )

#         for ch, dist in rows:
#             content = getattr(ch, "content", "") or ""
#             # if _is_noise_chunk(content):
#             #     continue
#             if _is_noise_chunk(content):
#                 print("[DEBUG] dropped as noise:", (content[:80] or "").replace("\n", " "))
#                 continue


#             setattr(ch, "_distance", dist)

#             ch_id = getattr(ch, "id", None)
#             if ch_id is None:
#                 merged.append(ch)
#                 continue

#             if ch_id not in seen_ids:
#                 seen_ids.add(ch_id)
#                 merged.append(ch)

#         # Sort by best (smallest) distance first
#     merged.sort(key=lambda ch: getattr(ch, "_distance", float("inf")))

#     # Universal rerank: prefer chunks that share meaningful tokens with the question text
#     # (works across any workspace/topic; no hardcoded entities)
#     question_text = " ".join(questions).lower()

#     def _tokens(text: str) -> set[str]:
#         # keep simple: letters/numbers only, length>=4 to avoid noise
#         cleaned = "".join((c if c.isalnum() else " ") for c in (text or "").lower())
#         return {t for t in cleaned.split() if len(t) >= 4}

#     q_tokens = _tokens(question_text)

#     def _overlap_score(chunk_text: str) -> int:
#         c_tokens = _tokens(chunk_text)
#         # count overlap; cap not needed yet
#         return len(q_tokens & c_tokens)

#     merged.sort(
#         key=lambda ch: (
#             -_overlap_score(getattr(ch, "content", "") or ""),
#             getattr(ch, "_distance", float("inf")),
#         )
#     )

#     TOP_CONTEXT = min(8, len(merged))
#     return merged[:TOP_CONTEXT]


    # merged.sort(key=lambda ch: getattr(ch, "_distance", float("inf")))

    # print("[DEBUG] merged candidates:", len(merged), "top10 distances:", [getattr(ch, "_distance", None) for ch in merged[:10]])

    # return merged


# def _retrieve_candidates(
#     db: Session,
#     workspace_id: str,
#     questions: list[str],
#     k_per_query: int,
# ) -> list[Chunk]:
#     """
#     Minimal, stable retrieval:
#     - semantic top-k via pgvector
#     - noise filtering (tables, catalogs, lists)
#     - strict context cap
#     NO rerank, NO heuristics
#     """

#     merged: list[Chunk] = []
#     seen_ids: set[int] = set()

#     for q in questions:
#         normalized_q = normalize_query_for_retrieval(q)

#         query_embeddings, _ = create_embeddings([{"content": normalized_q}])
#         query_vector = query_embeddings[0].tolist()

#         rows = get_top_k_chunks_for_workspace(
#             db=db,
#             workspace_id=workspace_id,
#             query_embedding=query_vector,
#             k=k_per_query,
#         )

#         for ch, dist in rows:
#             content = ch.content or ""

#             # hard noise filter (tables / lists / catalogs)
#             if _is_noise_chunk(content):
#                 continue

#             ch_id = ch.id
#             if ch_id in seen_ids:
#                 continue

#             setattr(ch, "_distance", float(dist))
#             seen_ids.add(ch_id)
#             merged.append(ch)

#     # pure semantic order
#     merged.sort(key=lambda ch: ch._distance)

#     # Precision: diversify by document (universal, no hardcoding)
#     PER_DOC_LIMIT = 2
#     by_doc: dict[int, int] = {}
#     diversified: list[Chunk] = []
#     for ch in merged:
#         doc_id = getattr(ch, "document_id", None)
#         if doc_id is None:
#             continue
#         used = by_doc.get(doc_id, 0)
#         if used >= PER_DOC_LIMIT:
#             continue
#         by_doc[doc_id] = used + 1
#         diversified.append(ch)
#     merged = diversified

#     # hard context limit
#     CONTEXT_K = 8
#         # DEBUG: what we actually send to LLM
#     selected = merged[:CONTEXT_K]
#     print("=== CONTEXT DEBUG ===")
#     print("selected count:", len(selected))
#     print("selected distances:", [round(getattr(ch, "_distance", 999.0), 4) for ch in selected])
#     print("selected sources:", [getattr(getattr(ch, "document", None), "source", None) for ch in selected])
#     print("=====================")

#     return selected

def _retrieve_candidates(
    db: Session,
    workspace_id: str,
    questions: list[str],
    k_per_query: int,
) -> list[Chunk]:
    """
    Minimal retrieval + HARD DEBUG:
    shows how many rows are dropped as noise vs duplicates.
    """

    merged: list[Chunk] = []
    seen_ids: set[int] = set()

    total_rows = 0
    dropped_noise = 0
    dropped_dupe = 0
    kept = 0

    noise_samples = 0
    dupe_samples = 0

    for q in questions:
        normalized_q = normalize_query_for_retrieval(q)

        query_embeddings, _ = create_embeddings([{"content": normalized_q}])
        query_vector = query_embeddings[0].tolist()

        rows = get_top_k_chunks_for_workspace(
            db=db,
            workspace_id=workspace_id,
            query_embedding=query_vector,
            k=k_per_query,
        )

        total_rows += len(rows)

        for ch, dist in rows:
            content = (ch.content or "")

            # 1) noise
            if _is_noise_chunk(content):
                dropped_noise += 1
                if noise_samples < 5:
                    noise_samples += 1
                    src = getattr(getattr(ch, "document", None), "source", None)
                    preview = content[:120].replace("\n", " ")
                    print(f"[DROP:NOISE] dist={float(dist):.4f} source={src} preview={preview}")
                continue

            # 2) duplicates
            ch_id = getattr(ch, "id", None)
            if ch_id is not None and ch_id in seen_ids:
                dropped_dupe += 1
                if dupe_samples < 5:
                    dupe_samples += 1
                    src = getattr(getattr(ch, "document", None), "source", None)
                    preview = content[:120].replace("\n", " ")
                    print(f"[DROP:DUPE]  dist={float(dist):.4f} source={src} preview={preview}")
                continue

            # keep
            if ch_id is not None:
                seen_ids.add(ch_id)

            setattr(ch, "_distance", float(dist))
            merged.append(ch)
            kept += 1

    merged.sort(key=lambda ch: getattr(ch, "_distance", 999.0))

    CONTEXT_K = 8
    selected = merged[:CONTEXT_K]

    print("=== RETRIEVAL SUMMARY ===")
    print("total_rows:", total_rows)
    print("dropped_noise:", dropped_noise)
    print("dropped_dupe:", dropped_dupe)
    print("kept_after_filters:", kept)
    print("selected_for_context:", len(selected))
    if selected:
        print("selected distances:", [round(getattr(ch, "_distance", 0.0), 4) for ch in selected])
        print("selected sources:", [getattr(ch.document, "source", None) for ch in selected])
    print("=========================")

    return selected





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
    mode = (request.mode or "reference").strip().lower()

    # Retrieval queries:
    if mode == "synthesis":
        # For synthesis: do NOT rewrite away the entity name.
        search_queries = [request.question]
    else:
        # For reference/custom: rewrite if enabled, but never allow empty output.
        search_queries = _rewrite_queries(request.question)
        if not search_queries:
            search_queries = [request.question]

    # search_queries = ["Hypericum perforatum"] if mode == "synthesis" else _rewrite_queries(request.question)
    print("🚨 Search Queries: 🚨")
    print(search_queries)
    print("🚨 Search Queries: 🚨")


    db = SessionLocal()
    try:
        chunk_objs = _retrieve_candidates(
            db=db,
            workspace_id=request.workspace_id,
            questions=search_queries,
            k_per_query=QUERY_REWRITE_TOP_K_PER_QUERY if (QUERY_REWRITE_ENABLED and LLM_ENABLED) else TOP_K,
            # anchor_question=request.question,
        )

        chunk_objs = focus_by_entity(chunk_objs, request.question)

        # Hard cap total candidates to TOP_K (keep first ones).
        # chunk_objs = sorted(chunk_objs, key=lambda ch: getattr(ch, "_distance", 999.0))
        # chunk_objs = chunk_objs[:TOP_K]
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

        candidates = llm_filter_relevant_chunks(
            request.question,
            candidates,
        )


        stored_records = len(candidates)

    finally:
        db.close()


    if stored_records == 0:
        answer = "This is a stub answer."
    else:
      
        context_parts = [c["content"] for c in candidates if c["content"]]
        context = "\n\n---\n\n".join(context_parts)

        print("🚨 Context: 🚨")
        print(context)
        print("🚨 Context: 🚨")

        if not LLM_ENABLED:
            answer = "LLM is temporarily disabled. Please try again later."
        else:
       
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
