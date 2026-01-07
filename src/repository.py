from src.models import Chunk, Document, Workspace
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import text
import os
import re

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z'\-]{2,}")

DEBUG_LOGS = os.getenv("DEBUG_LOGS", "0") == "1"


def _dbg(*args):
    if DEBUG_LOGS:
        print(*args)


def get_top_k_chunks_fts(
    db,
    workspace_id: str,
    query_text: str,
    k: int = 50,
) -> list[tuple["Chunk", float]]:
    """
    FTS retrieval that:
    1) extracts clean word tokens from the whole question
    2) picks rare tokens within the workspace (cnt > 0)
    3) builds OR websearch query from those tokens
    Returns (Chunk, distance_like) where smaller is better.
    """

    tokens = [t.lower() for t in _WORD_RE.findall(query_text or "")]
    seen = set()
    tokens = [t for t in tokens if not (t in seen or seen.add(t))]

    if not tokens:
        return []

    tokens = tokens[:25]

    freq_stmt = text("""
        WITH q AS (
          SELECT unnest(CAST(:terms AS text[])) AS term
        )
        SELECT
          q.term AS term,
          (
            SELECT count(*)
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.workspace_id = :ws
              AND to_tsvector('simple', c.content) @@ websearch_to_tsquery('simple', q.term)
          ) AS cnt
        FROM q
    """)

    freq_rows = db.execute(freq_stmt, {"ws": workspace_id, "terms": tokens}).fetchall()

    matching = [(str(r.term), int(r.cnt)) for r in freq_rows if int(r.cnt) > 0]
    matching.sort(key=lambda x: x[1])

    rare_terms = [t for (t, _) in matching[:3]]
    if not rare_terms:
        rare_terms = tokens[:3]

    q_or = " OR ".join(rare_terms)
    _dbg("FTS anchor:", q_or)

    stmt = text("""
        SELECT c.id AS id,
               ts_rank(
                 to_tsvector('simple', c.content),
                 websearch_to_tsquery('simple', :q_or)
               ) AS r
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE d.workspace_id = :ws
          AND to_tsvector('simple', c.content) @@ websearch_to_tsquery('simple', :q_or)
        ORDER BY r DESC
        LIMIT :k
    """)

    rows = db.execute(stmt, {"ws": workspace_id, "q_or": q_or, "k": k}).fetchall()
    _dbg("FTS rows:", len(rows))

    ids = [int(r.id) for r in rows]
    if not ids:
        return []

    chunks = (
        db.query(Chunk)
        .options(selectinload(Chunk.document))
        .filter(Chunk.id.in_(ids))
        .all()
    )

    rank_by_id = {int(r.id): float(r.r) for r in rows}

    pairs = [(ch, 1.0 - rank_by_id.get(int(ch.id), 0.0)) for ch in chunks]
    pairs.sort(key=lambda x: x[1])
    return pairs


def get_top_k_chunks_for_workspace(
    db,
    workspace_id: str,
    query_embedding: list[float],
    k: int = TOP_K,
) -> list[tuple["Chunk", float]]:
    distance = Chunk.embedding.cosine_distance(query_embedding)

    OVERFETCH = 20

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

    if DEBUG_LOGS:
        top3_d = [p[1] for p in pairs[:3]]
        top3_s = [getattr(p[0].document, "source", None) for p in pairs[:3]]
        print(f"VECTOR rows={len(rows)} top3_dist={top3_d} top3_src={top3_s}")

    return pairs


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
    _dbg("[ingest] workspace_id=", workspace_id, "source=", source,
         "chunks=", len(chunks), "embeddings=", len(embeddings))

    workspace = get_or_create_workspace(db, workspace_id)

    document = Document(workspace_id=workspace.id, source=source)
    db.add(document)
    db.flush()
    _dbg("[ingest] document.id=", document.id)

    chunk_objs = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        if DEBUG_LOGS and i < 3:
            content_len = len(chunk.get("content", ""))
            emb_len = len(embedding) if hasattr(embedding, "__len__") else None
            print("[ingest] i=", i, "content_len=", content_len, "emb_len=", emb_len)

        chunk_objs.append(
            Chunk(
                document_id=document.id,
                index=i,
                content=chunk["content"],
                embedding=embedding,
            )
        )

    db.add_all(chunk_objs)
    db.flush()

    if DEBUG_LOGS:
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
        print("[ingest] first10 (id,index)=", rows)

    db.commit()
    db.refresh(document)
    return document
