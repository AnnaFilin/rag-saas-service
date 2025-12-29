
from src.models import Chunk, Document, Workspace
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import text


def get_top_k_chunks_for_workspace(
    db: Session,
    workspace_id: str,
    query_embedding: list[float],
    k: int = 3,
) -> list[tuple[Chunk, float]]:
    distance = Chunk.embedding.cosine_distance(query_embedding)

    stmt = (
        select(Chunk, distance.label("distance"))
        .join(Document)
        .where(Document.workspace_id == workspace_id)
        .options(selectinload(Chunk.document))
        .order_by(distance)  # lower distance = more similar
        .limit(k)
    )

    rows = db.execute(stmt).all()
    return [(chunk, float(dist)) for (chunk, dist) in rows]

# def get_top_k_chunks_for_workspace(
#     db: Session,
#     workspace_id: str,
#     query_embedding: list[float],
#     k: int = 10,
# ) -> list[tuple[Chunk, float]]:
#     """
#     Returns (chunk, distance) pairs.
#     Lower distance => more similar.
#     """
#     distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")

#     stmt = (
#         select(Chunk, distance)
#         .join(Document)
#         .where(Document.workspace_id == workspace_id)
#         .options(selectinload(Chunk.document))
#         .order_by(distance.asc())
#         .limit(k)
#     )

#     rows = db.execute(stmt).all()
#     return [(chunk, float(dist) if dist is not None else 999.0) for chunk, dist in rows]
# def get_top_k_chunks_for_workspace(
#     db: Session,
#     workspace_id: str,
#     query_embedding: list[float],
#     k: int = 3,
# ) -> list[Chunk]:
#     stmt = (
#         select(Chunk)
#         .join(Document)
#         .where(Document.workspace_id == workspace_id)
#         .order_by(Chunk.embedding.l2_distance(query_embedding))
#         .limit(k)
#     )
#     return db.scalars(stmt).all()

def get_or_create_workspace(db: Session, workspace_id: str) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace:
        return workspace

    workspace = Workspace(id=workspace_id)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


# def create_document_with_chunks(
#     db: Session,
#     workspace_id: str,
#     source: str,
#     chunks: list[dict],
#     embeddings: list[list[float]],
# ) -> Document:
#     workspace = get_or_create_workspace(db, workspace_id)

#     document = Document(workspace_id=workspace.id, source=source)
#     db.add(document)
#     db.flush()

#     chunk_objs = []
#     for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
#         chunk_objs.append(
#             Chunk(
#                 document_id=document.id,
#                 index=i,
#                 content=chunk["content"],
#                 embedding=embedding,
#             )
#         )


#     db.add_all(chunk_objs)
#     db.commit()
#     db.refresh(document)
#     return document


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
