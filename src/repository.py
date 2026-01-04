from src.models import Chunk, Document, Workspace
from sqlalchemy import select, or_
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import text
from pgvector import Vector as PgVector  
import os
import re


TOP_K = 20
MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "0.38"))

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z'\-]{2,}")  # >= 3 символов

def _extract_anchors(question: str, max_anchors: int = 4) -> list[str]:
    q = (question or "").strip()
    if not q:
        return []

    quoted = re.findall(r'"([^"]+)"|“([^”]+)”|‘([^’]+)’|\'([^\']+)\'', q)
    phrases = []
    for tup in quoted:
        phrase = next((x for x in tup if x), "")
        phrase = (phrase or "").strip().lower()
        if phrase and len(phrase) >= 4:
            phrases.append(phrase)
    if phrases:
        phrases = sorted(set(phrases), key=len, reverse=True)
        return phrases[: min(2, len(phrases))]

    # 2) Latin binomial: "Hypericum perforatum"
    m = re.search(r"\b([A-Z][a-z]{2,})\s+([a-z]{2,})\b", q)
    if m:
        return [m.group(1).lower(), m.group(2).lower()]

    # 3) fallback:
    tokens = [t.lower() for t in _WORD_RE.findall(q)]

    uniq = []
    seen = set()
    for t in sorted(tokens, key=len, reverse=True):
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:max_anchors]


def _chunk_matches_anchors(text: str, anchors: list[str]) -> bool:
    if not anchors:
        return True

    low = (text or "").lower()

    if len(anchors) == 1:
        return anchors[0] in low

    if len(anchors) == 2:
        return all(a in low for a in anchors)

    hits = sum(1 for a in anchors if a in low)
    return hits >= 2


# def get_top_k_chunks_for_workspace(
#     db,
#     workspace_id: str,
#     query_embedding: list[float],
#     k: int = TOP_K,
# ) -> list[tuple["Chunk", float]]:
#     # IMPORTANT: query_embedding must be a plain 1D Python list[float] of length 768
#     distance = Chunk.embedding.cosine_distance(query_embedding)

#     stmt = (
#         select(Chunk, distance.label("distance"))
#         .join(Document)
#         .where(Document.workspace_id == workspace_id)
#         .options(selectinload(Chunk.document))
#         .order_by(distance)
#         .limit(k * 20)
#     )
#     rows = db.execute(stmt).all()

#     pairs = [(chunk, float(dist)) for (chunk, dist) in rows]

#     print("=== RETRIEVAL DEBUG ===")
#     print("workspace_id:", workspace_id)

#     # 2 lines BEFORE results: verify query vector shape/type
#     print(
#         "Q_EMB:",
#         "type=", type(query_embedding).__name__,
#         "len=", (len(query_embedding) if isinstance(query_embedding, list) else "n/a"),
#         "first_type=", (type(query_embedding[0]).__name__ if isinstance(query_embedding, list) and query_embedding else "n/a"),
#     )
#     print(
#         "Q_EMB head:",
#         (query_embedding[:5] if isinstance(query_embedding, list) else query_embedding),
#     )

#     # 2 lines AFTER results: verify what came back
#     print("rows count:", len(rows))
#     if pairs:
#         top3_d = [p[1] for p in pairs[:3]]
#         top3_src = [
#             (p[0].document.source if p[0].document and p[0].document.source else None)
#             for p in pairs[:3]
#         ]
#         print("top3 distances:", top3_d)
#         print("top3 sources:", top3_src)
#     else:
#         print("top3 distances: []")
#         print("top3 sources: []")

#     print("=======================")

#     return pairs[:k]

def get_top_k_chunks_for_workspace(
    db,
    workspace_id: str,
    query_embedding: list[float],
    k: int = TOP_K,
) -> list[tuple["Chunk", float]]:
    # IMPORTANT: query_embedding must be a plain 1D Python list[float] of length 768
    distance = Chunk.embedding.cosine_distance(query_embedding)

    # Overfetch so that noise filtering has room to work.
    OVERFETCH = 20  # universal; not tied to any workspace/topic

    stmt = (
        select(Chunk, distance.label("distance"))
        .join(Document)
        .where(Document.workspace_id == workspace_id)
        .options(selectinload(Chunk.document))
        .order_by(distance)
        .limit(k * OVERFETCH)
    )
    rows = db.execute(stmt).all()

    pairs = [(chunk, float(dist)) for (chunk, dist) in rows]

    print("=== RETRIEVAL DEBUG ===")
    print("workspace_id:", workspace_id)
    print("Q_EMB: type=", type(query_embedding).__name__, "len=", len(query_embedding),
          "first_type=", type(query_embedding[0]).__name__ if query_embedding else None)
    print("rows count:", len(rows))
    if pairs:
        print("top3 distances:", [p[1] for p in pairs[:3]])
        print("top3 sources:", [getattr(p[0].document, "source", None) for p in pairs[:3]])
    print("=======================")

    # IMPORTANT: return ALL overfetched rows; caller will filter + cap later.
    return pairs



# def get_top_k_chunks_for_workspace(
#     db,
#     workspace_id: str,
#     query_embedding: list[float],
#     # question: str,
#     k: int = TOP_K,
# ) -> list[tuple["Chunk", float]]:
#     # distance = Chunk.embedding.cosine_distance(query_embedding)
#     query_embedding = PgVector(query_embedding)
#     distance = Chunk.embedding.cosine_distance(query_embedding)


#     # 1) Vector search (wide)
#     stmt = (
#         select(Chunk, distance.label("distance"))
#         .join(Document)
#         .where(Document.workspace_id == workspace_id)
#         .where(distance < MAX_DISTANCE)
#         .options(selectinload(Chunk.document))
#         .order_by(distance)
#         .limit(k * 5)
#     )
#     rows = db.execute(stmt).all()

#     # fallback if threshold cut everything
#     if not rows:
#         stmt2 = (
#             select(Chunk, distance.label("distance"))
#             .join(Document)
#             .where(Document.workspace_id == workspace_id)
#             .options(selectinload(Chunk.document))
#             .order_by(distance)
#             .limit(k * 5)
#         )
#         rows = db.execute(stmt2).all()

#     pairs = [(chunk, float(dist)) for (chunk, dist) in rows]

#     # anchors = _extract_anchors(question)
#     # if not anchors:
#     #     return pairs[:k]

#     # # 2) Gate on what vector search already returned
#     # gated = [(c, d) for (c, d) in pairs if _chunk_matches_anchors(c.content, anchors)]
#     # if gated:
#     #     return gated[:k]

#     # 3) Lexical fallback inside workspace (no hardcode; uses anchors from the question)
#     # For 1 anchor -> ILIKE %a%
#     # For 2 anchors (binomial) -> AND
#     # For >=3 anchors -> OR (otherwise too strict)
#     # stmt3 = (
#     #     select(Chunk, distance.label("distance"))
#     #     .join(Document)
#     #     .where(Document.workspace_id == workspace_id)
#     #     .options(selectinload(Chunk.document))
#     # )

#     # if len(anchors) == 1:
#     #     a = f"%{anchors[0]}%"
#     #     stmt3 = stmt3.where(Chunk.content.ilike(a))
#     # elif len(anchors) == 2:
#     #     a1 = f"%{anchors[0]}%"
#     #     a2 = f"%{anchors[1]}%"
#     #     stmt3 = stmt3.where(Chunk.content.ilike(a1)).where(Chunk.content.ilike(a2))
#     # else:
#     #     ors = [Chunk.content.ilike(f"%{a}%") for a in anchors]
#     #     stmt3 = stmt3.where(or_(*ors))  # requires: from sqlalchemy import or_

#     # rows3 = (
#     #     stmt3.order_by(distance)
#     #     .limit(k * 5)
#     # )
#     # rows3 = db.execute(rows3).all()

#     # pairs3 = [(chunk, float(dist)) for (chunk, dist) in rows3]
#     # gated3 = [(c, d) for (c, d) in pairs3 if _chunk_matches_anchors(c.content, anchors)]

#     # return (gated3[:k] if gated3 else pairs3[:k] if pairs3 else pairs[:k])
#     return pairs[:k]

# def get_top_k_chunks_for_workspace(
#     db,
#     workspace_id: str,
#     query_embedding: list[float],
#     question: str,         
#     k: int = TOP_K,
# ) -> list[tuple["Chunk", float]]:
#     distance = Chunk.embedding.cosine_distance(query_embedding)

#     stmt = (
#         select(Chunk, distance.label("distance"))
#         .join(Document)
#         .where(Document.workspace_id == workspace_id)
#         .where(distance < MAX_DISTANCE)
#         .options(selectinload(Chunk.document))
#         .order_by(distance)
#         .limit(k * 5)        
#     )
#     rows = db.execute(stmt).all()

#     if not rows:
#         stmt2 = (
#             select(Chunk, distance.label("distance"))
#             .join(Document)
#             .where(Document.workspace_id == workspace_id)
#             .options(selectinload(Chunk.document))
#             .order_by(distance)
#             .limit(k * 5)
#         )
#         rows = db.execute(stmt2).all()

#     pairs = [(chunk, float(dist)) for (chunk, dist) in rows]

#     anchors = _extract_anchors(question)
#     gated = [(c, d) for (c, d) in pairs if _chunk_matches_anchors(c.content, anchors)]

#     return (gated[:k] if gated else pairs[:k])

# MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "0.38"))


# def get_top_k_chunks_for_workspace(
#     db: Session,
#     workspace_id: str,
#     query_embedding: list[float],
#     k: int = 3,
# ) -> list[tuple[Chunk, float]]:
#     distance = Chunk.embedding.cosine_distance(query_embedding)

#     # 1) Try with threshold (cuts junk)
#     stmt_thresh = (
#         select(Chunk, distance.label("distance"))
#         .join(Document)
#         .where(Document.workspace_id == workspace_id)
#         .where(distance < MAX_DISTANCE)
#         .options(selectinload(Chunk.document))
#         .order_by(distance)  # lower distance = more similar
#         .limit(k)
#     )
#     rows = db.execute(stmt_thresh).all()

#     # 2) Fallback: if threshold filtered everything out, return best k anyway
#     if not rows:
#         stmt_no_thresh = (
#             select(Chunk, distance.label("distance"))
#             .join(Document)
#             .where(Document.workspace_id == workspace_id)
#             .options(selectinload(Chunk.document))
#             .order_by(distance)
#             .limit(k)
#         )
#         rows = db.execute(stmt_no_thresh).all()

#     return [(chunk, float(dist)) for (chunk, dist) in rows]


# MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "0.38"))

# def get_top_k_chunks_for_workspace(
#     db: Session,
#     workspace_id: str,
#     query_embedding: list[float],
#     k: int = 3,
# ) -> list[tuple[Chunk, float]]:
#     distance = Chunk.embedding.cosine_distance(query_embedding)

#     stmt = (
#         select(Chunk, distance.label("distance"))
#         .join(Document)
#         .where(Document.workspace_id == workspace_id)
#         .where(distance < MAX_DISTANCE)
#         .options(selectinload(Chunk.document))
#         .order_by(distance)  # lower distance = more similar
#         .limit(k)
#     )

#     rows = db.execute(stmt).all()
#     return [(chunk, float(dist)) for (chunk, dist) in rows]


def get_or_create_workspace(db: Session, workspace_id: str) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace:
        return workspace

    workspace = Workspace(id=workspace_id)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace



def create_document_with_chunks(
    db: Session,
    workspace_id: str,
    source: str,
    chunks: list[dict],
    embeddings: list[list[float]],
) -> Document:
    print("[DEBUG] create_document_with_chunks: workspace_id =", workspace_id)
    print("[DEBUG] create_document_with_chunks: source =", source)
    print("[DEBUG] len(chunks) =", len(chunks), "len(embeddings) =", len(embeddings))

    workspace = get_or_create_workspace(db, workspace_id)

    document = Document(workspace_id=workspace.id, source=source)
    db.add(document)
    db.flush()
    print("[DEBUG] document.id after flush =", document.id)

    chunk_objs = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        if i < 5:
            print("[DEBUG] loop i =", i, "content_len =", len(chunk.get("content", "")))
            # embedding can be large; just show type/len
            try:
                emb_len = len(embedding)
            except Exception:
                emb_len = None
            print("[DEBUG] embedding type =", type(embedding), "len =", emb_len)

        chunk_objs.append(
            Chunk(
                document_id=document.id,
                index=i,
                content=chunk["content"],
                embedding=embedding,
            )
        )

    print("[DEBUG] built chunk_objs =", len(chunk_objs))
    if chunk_objs:
        print("[DEBUG] first 5 chunk_objs indexes =", [c.index for c in chunk_objs[:5]])
        print("[DEBUG] last chunk_obj index =", chunk_objs[-1].index)

    db.add_all(chunk_objs)

    db.flush()

    rows = db.execute(
        text("""
            select id, "index"
            from chunks
            where document_id = :doc_id
            order by id asc
            limit 10
        """),
        {"doc_id": document.id},
    ).fetchall()

    print("[DEBUG] DB after flush: first 10 (id, index) rows =", rows)

    db.commit()
    db.refresh(document)
    return document
