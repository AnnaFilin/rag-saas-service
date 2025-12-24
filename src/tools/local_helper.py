# DEV TOOL: local ingest helper for UI (http://127.0.0.1:7777)

from pathlib import Path
import tempfile

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.db import SessionLocal
from src.load_docs import convert_to_markdown
from src.process_texts import split_into_chunks
from src.embeddings import create_embeddings
from src.repository import create_document_with_chunks

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/ingest-file")
async def ingest_file(
    workspace_id: str = Form(...),
    file: UploadFile = File(...)
):
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
            create_document_with_chunks(
                db,
                workspace_id,
                doc.get("source", workspace_id),
                chunks,
                embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings,
            )
        finally:
            db.close()

        return {
            "workspace_id": workspace_id,
            "chunks_count": len(chunks),
            "status": "ready",
        }

    finally:
        Path(temp_file.name).unlink(missing_ok=True)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7777)
