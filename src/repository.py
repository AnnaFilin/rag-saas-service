
from src.models import Chunk, Document, Workspace
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_top_k_chunks_for_workspace(
    db: Session,
    workspace_id: str,
    query_embedding: list[float],
    k: int = 3,
) -> list[Chunk]:
    stmt = (
        select(Chunk)
        .join(Document)
        .where(Document.workspace_id == workspace_id)
        .order_by(Chunk.embedding.l2_distance(query_embedding))
        .limit(k)
    )
    return db.scalars(stmt).all()

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
    workspace = get_or_create_workspace(db, workspace_id)

    document = Document(workspace_id=workspace.id, source=source)
    db.add(document)
    db.flush()

    chunk_objs = []
    for chunk, embedding in zip(chunks, embeddings):
        chunk_objs.append(
            Chunk(
                document_id=document.id,
                index=chunk.get("index", 0),
                content=chunk["content"],
                embedding=embedding,
            )
        )

    db.add_all(chunk_objs)
    db.commit()
    db.refresh(document)
    return document