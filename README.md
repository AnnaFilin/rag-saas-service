## Architecture overview

This project is a small RAG backend built with FastAPI and Neon Postgres + pgvector.

There are two separate Cloud Run services sharing the same Neon database:

- **Chat service** (`rag-saas-rag`)
  - Runs `APP_MODULE=src.chat_api:app`
  - Lightweight read-only path: embeds the question, retrieves top-k chunks from pgvector, and (optionally) calls an LLM.
  - Endpoints:
    - `GET /health` – basic health check.
    - `POST /chat` – RAG query endpoint:
      - Request body:
        - `workspace_id: string`
        - `question: string`
        - `role?: string | null`
      - Response:
        - `answer: string` (LLM answer or stub, depending on `LLM_ENABLED`)
        - `sources: Chunk[]` – context used to answer
        - `candidates: Chunk[]` – same as sources, kept for debugging
        - `llm_backend`, `llm_model` – effective LLM settings

- **Ingestion service** (`rag-saas-ingest`)
  - Runs `APP_MODULE=src.ingest_api:app`
  - Heavy write path: converts documents to markdown, splits into chunks, computes embeddings, and stores them in Neon.
  - Endpoints:
    - `GET /health` – basic health check.
    - `POST /ingest-file` – document ingestion:
      - Multipart form data:
        - `workspace_id` – logical workspace key
        - `file` – uploaded document (PDF/Markdown, etc.)
      - Response:
        - `workspace_id: string`
        - `chunks_count: number`
        - `embeddings_count: number`
        - `stored_records: number`
        - `errors: string[]`

Both services use the same schema in Neon (Postgres + pgvector):

- `workspaces` – logical workspace id
- `documents` – ingested documents per workspace
- `chunks` – text chunks with `embedding VECTOR(768)` column.
