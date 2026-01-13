# RAG SaaS Backend

A backend service implementing Retrieval-Augmented Generation (RAG) with strict source grounding and workspace-isolated document retrieval.

Designed as a small but production-oriented RAG system suitable for portfolio demonstration and internal knowledge tools.

---

## What It Does

- Ingests documents into a vector database
- Retrieves relevant text chunks per query
- Generates answers grounded strictly in retrieved context
- Returns answers together with exact source excerpts

If relevant information is not found, the system explicitly returns a no-answer response.

---

## Architecture

The system consists of two independent FastAPI services:

### Ingestion Service
- Accepts document uploads per workspace
- Splits documents into chunks
- Generates embeddings using SentenceTransformers
- Stores data in PostgreSQL with pgvector

### Ingestion options
- **Cloud ingest service**: for typical documents (API upload → chunking → embeddings → storage).
- **Local helper**: for large/heavy documents that are impractical to upload via Cloud Run; it runs locally and writes processed chunks + embeddings to the same Postgres/pgvector storage.

### Chat Service
- Retrieves relevant chunks using vector similarity
- Builds context from retrieved sources
- Generates answers using an LLM
- Returns answers with source references

---

## Tech Stack

**Backend**
- Python
- FastAPI
- PostgreSQL (Neon) + pgvector
- SentenceTransformers
- SQLAlchemy

**LLM**
- Ollama (local)
- OpenAI (cloud, optional)
- Configurable via environment variables

**Frontend**
- Vue 3
- Tailwind CSS
- Vite

The frontend is a minimal admin UI for document upload and chat testing.

---

## Deployment

The services are designed to be deployed independently (e.g. Cloud Run):

- `rag-saas-ingest` — document ingestion and embeddings
- `rag-saas-rag` — retrieval and answering

Local and cloud deployments share the same architecture.

---

## Project Status

Stable prototype.

Core RAG functionality, retrieval pipeline, and source attribution are implemented and working.

