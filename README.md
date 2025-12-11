# RAG SaaS Backend (FastAPI + Neon + pgvector)

Small but real RAG backend split into two Cloud Run services: one for ingestion, one for chat.  
It uses Neon Postgres with `pgvector` for embeddings storage and SentenceTransformers for vectorization.

This project is meant as a learning playground and a portfolio-ready example of a simple RAG backend.

---

## Architecture

**Storage**

- Neon Postgres with `pgvector`
- Embedding dimension: `VECTOR(768)`

**Schema**

- Workspace
  - id: text
- Document
  - id: serial
  - workspace_id: text (FK → Workspace.id)
  - source: text (file path or name)
- Chunk
  - id: serial
  - document_id: int (FK → Document.id)
  - index: int (chunk index inside the document)
  - content: text
  - embedding: vector(768)

**Services (Cloud Run)**

1. ingest (rag-saas-ingest)
   - FastAPI app: src.ingest_api:app
   - Endpoints:
     - GET /health – healthcheck
     - POST /ingest-file – upload file, split into chunks, create embeddings, write to Neon
   - Responsibilities:
     - Accept file for a given workspace_id
     - Convert PDF/MD to markdown (MarkItDown)
     - Split text into chunks
     - Create embeddings with SentenceTransformer
     - Persist Workspace, Document, Chunk + embeddings in Neon

2. chat (rag-saas-rag)
   - FastAPI app: src.chat_api:app
   - Endpoints:
     - GET /health – healthcheck
     - POST /chat – answer question using RAG pipeline
   - Responsibilities:
     - Encode question into embedding
     - Retrieve top-k chunks with pgvector (l2_distance)
     - Build context from retrieved chunks
     - Call LLM (Ollama or OpenAI)
     - Return answer + sources

**LLM pipeline**

- Embeddings: SentenceTransformer (mpnet model, 768-dim vectors)
- LLM backends:
  - ollama (local)
  - openai (via OpenAI API)
- Configured via environment variables:
  - LLM_BACKEND (default: ollama)
  - LLM_MODEL (e.g. llama3.2:latest or gpt-4.1-mini)
  - OPENAI_API_KEY (for LLM_BACKEND=openai)
  - LLM_ENABLED=true|false (for disabling LLM in chat service)

---

## Local development

### 1. Environment

Create .env.local in the project root with something like:

    DATABASE_URL=postgresql+psycopg://user:password@host:port/dbname
    LLM_BACKEND=openai
    LLM_MODEL=gpt-4.1-mini
    OPENAI_API_KEY=sk-...
    LLM_ENABLED=true

Make sure your Postgres has pgvector installed and the DATABASE_URL points to it  
(you can use Neon or any local Postgres with pgvector).

### 2. Install dependencies

    python -m venv .venv
    source .venv/bin/activate  # on Windows: .venv\Scripts\activate
    pip install -r requirements.txt

### 3. Run ingestion API locally

    uvicorn src.ingest_api:app --reload --port 8001

Check:

    curl http://localhost:8001/health

### 4. Run chat API locally

    uvicorn src.chat_api:app --reload --port 8000

Check:

    curl http://localhost:8000/health

### 5. Ingest a document (local)

    curl -X POST "http://localhost:8001/ingest-file" \
      -F "workspace_id=test-local" \
      -F "file=@./some-doc.pdf"

### 6. Ask a question (local)

    curl -X POST "http://localhost:8000/chat" \
      -H "Content-Type: application/json" \
      -d '{
        "workspace_id": "test-local",
        "question": "What is this document about?",
        "role": "You are a helpful assistant for this RAG backend."
      }'

---

## Cloud Run deployment (Neon + OpenAI)

The project is designed to run as two separate Cloud Run services:

- rag-saas-ingest – heavy path (file upload, embeddings, writes to Neon)
- rag-saas-rag – light path (chat + retrieval + LLM)

Below is an example deployment pattern (simplified, adjust for your project).

### Ingestion service

    gcloud run deploy rag-saas-ingest \
      --source . \
      --region me-west1 \
      --set-env-vars "DATABASE_URL=postgresql+psycopg://...Neon-URL..." \
      --set-env-vars "LLM_ENABLED=false" \
      --set-env-vars "LLM_BACKEND=ollama" \
      --set-env-vars "LLM_MODEL=llama3.2:latest" \
      --command "uvicorn" \
      --args "src.ingest_api:app","--host","0.0.0.0","--port","8080"

### Chat service (OpenAI)

    gcloud run deploy rag-saas-rag \
      --source . \
      --region me-west1 \
      --set-env-vars "DATABASE_URL=postgresql+psycopg://...Neon-URL..." \
      --set-env-vars "LLM_ENABLED=true" \
      --set-env-vars "LLM_BACKEND=openai" \
      --set-env-vars "LLM_MODEL=gpt-4.1-mini" \
      --set-env-vars "OPENAI_API_KEY=sk-..." \
      --command "uvicorn" \
      --args "src.chat_api:app","--host","0.0.0.0","--port","8080"

After deployment, you should be able to call:

    curl -X POST "https://<rag-saas-ingest-URL>/ingest-file" \
      -F "workspace_id=test-cloud" \
      -F "file=@./some-doc.pdf"

    curl -X POST "https://<rag-saas-rag-URL>/chat" \
      -H "Content-Type: application/json" \
      -d '{
        "workspace_id": "test-cloud",
        "question": "What is this service supposed to do?",
        "role": "You are a helpful assistant for a small RAG backend."
      }'

---

## Minimal web UI (admin panel)

The repo includes a tiny static admin page:

- index.html – simple two-column layout
- styles.css – basic styling
- main.js – JS logic

Current behaviour:

- Left form: uploads files to the ingestion service (/ingest-file)
- Right form: sends chat requests to the chat service (/chat)
- All URLs are controlled via constants at the top of main.js:
  - INGEST_URL
  - CHAT_URL

This UI is intentionally simple and “technical” – it’s just an internal admin panel for testing the backend.  
A proper frontend (Vite + Vue/React) can be built on top of this backend in a separate project.
