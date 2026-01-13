# Internal Notes (Do Not Publish)

# RAG SaaS Backend (FastAPI + Neon + pgvector)

Small but real RAG backend split into two Cloud Run services: one for ingestion and one for chat.
It uses Neon Postgres with pgvector for embeddings storage and SentenceTransformers for vectorization.

This project is meant as a learning playground and a portfolio-ready example of a simple RAG backend.

---

## Architecture

### Storage

- Neon Postgres with pgvector
- Embedding dimension: VECTOR(768)

### Schema

**Workspace**
- id: text

**Document**
- id: serial
- workspace_id: text (FK → Workspace.id)
- source: text (file path or name)

**Chunk**
- id: serial
- document_id: int (FK → Document.id)
- index: int (chunk index inside the document)
- content: text
- embedding: vector(768)

---

## Services (Cloud Run)

### ingest (rag-saas-ingest)

FastAPI app: src.ingest_api:app

**Endpoints**
- GET /health — healthcheck
- POST /ingest-file — upload file, split into chunks, create embeddings, write to Neon

**Responsibilities**
- Accept file for a given workspace_id
- Convert PDF / MD to markdown (MarkItDown)
- Split text into chunks
- Create embeddings with SentenceTransformer
- Persist Workspace, Document, Chunk + embeddings in Neon

---

### chat (rag-saas-rag)

FastAPI app: src.chat_api:app

**Endpoints**
- GET /health — healthcheck
- POST /chat — answer question using RAG pipeline

**Responsibilities**
- Encode question into embedding
- Retrieve top-k chunks with pgvector (l2_distance)
- Build context from retrieved chunks
- Call LLM (Ollama or OpenAI)
- Return answer + sources

---

## LLM Pipeline

**Embeddings**
- SentenceTransformer (mpnet model, 768-dim vectors)

**LLM backends**
- ollama (local)
- openai (via OpenAI API)

**Environment variables**
- LLM_BACKEND (default: ollama)
- LLM_MODEL (e.g. llama3.2:latest or gpt-4.1-mini)
- OPENAI_API_KEY (for LLM_BACKEND=openai)
- LLM_ENABLED=true|false

---

## Local Development

### 1. Environment

Create `.env.local` in the project root:

DATABASE_URL=postgresql+psycopg://user:password@host:port/dbname  
LLM_BACKEND=openai  
LLM_MODEL=gpt-4.1-mini  
OPENAI_API_KEY=sk-...  
LLM_ENABLED=true  

Make sure Postgres has pgvector installed and DATABASE_URL points to it.

---

### 2. Install dependencies

python -m venv .venv  
source .venv/bin/activate  
pip install -r requirements.txt  

---

### 3. Run ingestion API locally

uvicorn src.ingest_api:app --reload --port 8001

Check:  
curl http://localhost:8001/health

---

### 4. Run chat API locally

uvicorn src.chat_api:app --reload --port 8000

Check:  
curl http://localhost:8000/health

---

### 5. Ingest a document (local)

curl -X POST "http://localhost:8001/ingest-file" \
-F "workspace_id=test-local" \
-F "file=@./some-doc.pdf"

---

### 6. Ask a question (local)

curl -X POST "http://localhost:8000/chat" \
-H "Content-Type: application/json" \
-d '{
  "workspace_id": "test-local",
  "question": "What is this document about?",
  "role": "You are a helpful assistant for this RAG backend."
}'

---

## Cloud Run Deployment (Neon + OpenAI)

The project runs as two Cloud Run services:

- rag-saas-ingest — heavy path (file upload, embeddings, DB writes)
- rag-saas-rag — light path (chat + retrieval + LLM)

---

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

---

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

---

### After deployment

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

## Admin UI (Vue 3 + Tailwind)

The repository includes a lightweight admin interface built with **Vue 3, Vite, and Tailwind CSS**.

The UI is intended as a **technical control panel** for interacting with the RAG backend during development and testing.

### Features
- Workspace selection
- Document upload (via ingestion API)
- Chat playground for querying a selected workspace
- Display of answers together with retrieved source chunks
- Notes view for inspecting stored records

### Tech stack
- Vue 3
- Vite
- Tailwind CSS

### Architecture
- The frontend is a separate UI layer that proxies requests to the backend APIs
- API calls are routed to:
  - `/api/ingest/*` — ingestion service
  - `/api/rag/*` — chat / retrieval service
- During local development, Vite proxy configuration is used to forward requests to FastAPI

### Scope
The UI is intentionally minimal and engineering-focused:
- No authentication
- No end-user UX polish
- No business logic on the frontend

Its purpose is to validate backend behavior and serve as a reference UI.


**Behaviour**
- Left form: uploads files to /ingest-file
- Right form: sends chat requests to /chat

Endpoints are configured via constants in main.js:
- INGEST_URL
- CHAT_URL

This UI is intentionally simple and internal.

---

# Internal Notes (Do Not Publish)

## Deployment
- rag-saas-ingest (Cloud Run) — ingestion
- rag-saas-rag (Cloud Run) — chat
- Shared storage: Neon Postgres + pgvector

## Ingestion paths
- Cloud ingest:
  - Normal-sized documents
  - Subject to Cloud Run limits
- Local helper:
  - Large PDFs / heavy preprocessing
  - Writes chunks + embeddings directly to the same DB

## LLM
- Supports Ollama (local) and OpenAI
- Controlled via env vars

## Known trade-offs
- Precision prioritized over recall
- Broad questions may return “Not stated in the provided context”
- Conservative filtering by design
