import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile

from src.db import Base, SessionLocal, engine
from src.load_docs import convert_to_markdown
from src.process_texts import split_into_chunks
from src.embeddings import create_embeddings
from src.repository import create_document_with_chunks
from src.models import Workspace, Document, Chunk  # noqa: F401


app = FastAPI()


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(bind=engine)
    print("🗄️ Database schema initialized.")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest-file")
async def ingest_file(workspace_id: str = Form(...), file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix or ".tmp"
    temp_file = tempfile.NamedTemporaryFile("wb", delete=False, suffix=suffix)
    try:
        temp_file.write(await file.read())
        temp_file.close()

        doc = convert_to_markdown(temp_file.name)
        chunks = split_into_chunks(text=doc["content"], source=workspace_id)
        embeddings, _ = create_embeddings(chunks)

        db = SessionLocal()
        try:
            create_document_with_chunks(db, workspace_id, doc.get("source", workspace_id), chunks, embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings)
        finally:
            db.close()

        return {
            "workspace_id": workspace_id,
            "chunks_count": len(chunks),
            "embeddings_count": len(embeddings),
            "stored_records": len(chunks),
            "errors": [],
        }
    finally:
        if Path(temp_file.name).exists():
            Path(temp_file.name).unlink()