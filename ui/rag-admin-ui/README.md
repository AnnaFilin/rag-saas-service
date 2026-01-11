# RAG-Based Knowledge Retrieval Service

A modular Retrieval-Augmented Generation (RAG) prototype focused on **retrieval correctness, strict source grounding, and predictable system behavior**.

The project demonstrates how to design a RAG backend that prioritizes **traceability and control** over generative freedom, making it suitable for research-oriented and knowledge-sensitive use cases.

---

## Overview

This system implements a complete RAG pipeline that:

- Ingests heterogeneous documents and stores them as vectorized chunks
- Retrieves semantically relevant context per query
- Applies deterministic and optional LLM-based relevance filtering
- Generates answers **strictly grounded in retrieved sources**
- Returns answers together with the exact source excerpts used

The architecture is intentionally **domain-agnostic** and workspace-isolated, allowing the same backend to serve different knowledge bases without code changes.

---

## Core Design Principles

### 1. Strict Source Grounding

The system answers **only when sufficient evidence exists** in the retrieved context.

If no reliable coverage is found, it explicitly returns a no-answer fallback instead of speculative or inferred output. This behavior is enforced both before and after generation.

---

### 2. Deterministic Guardrails

To reduce hallucinations and unpredictable behavior, the pipeline includes multiple non-generative guardrails:

- Lexical overlap re-ranking
- Subject-based content narrowing
- Deterministic coverage validation
- Post-generation normalization to remove mixed or contradictory answers

These mechanisms are **independent of any specific domain** and work purely on question–context relationships.

---

### 3. Modular Retrieval Pipeline

The retrieval flow is explicitly separated into stages:

1. Vector-based semantic retrieval (pgvector)
2. Lexical re-ranking
3. Optional LLM-based relevance filtering
4. Deterministic coverage gating
5. Context truncation and ordering

Each stage can be enabled, disabled, or replaced independently, making the system easy to experiment with and reason about.

---

### 4. Controlled Answer Generation

Answer generation is performed under a strict answering role:

- No external knowledge injection
- No inference beyond provided context
- No speculative language
- No mixing of factual answers with uncertainty statements

This makes the output predictable and suitable for inspection and debugging.

---

## Architecture Summary

### Backend

- **Language / Framework**: Python, FastAPI
- **Database**: PostgreSQL (Neon) with pgvector
- **ORM**: SQLAlchemy
- **Embeddings**: SentenceTransformers
- **LLM Integration**: Pluggable via configuration (local or cloud)

### Frontend

- **Framework**: Vue 3
- **Styling**: Tailwind CSS
- **Build Tooling**: Vite

The frontend acts as a thin admin interface for document ingestion, chat interaction, and inspecting stored notes and sources.

---

## LLM Backend Flexibility

The system supports multiple LLM backends via configuration.

Both local models (e.g. self-hosted runtimes such as Ollama) and cloud-based providers can be used for relevance filtering and answer generation. This enables experimentation with different trade-offs around performance, privacy, and cost.

Document ingestion and answer generation are intentionally decoupled from a specific execution environment. In practice, this allows running heavy or long-document processing locally while using cloud models for lighter or exploratory workloads, without changing the retrieval architecture itself.

---

## Deployment & Configuration

- Backend and frontend can be run locally or deployed independently
- Vector storage is persistent and workspace-isolated
- Retrieval and generation behavior is configurable via environment flags
- No domain-specific assumptions are baked into the pipeline

The same architecture scales from local experimentation to cloud deployment without structural changes.

---

## Known Limitations

- Retrieval quality depends on document chunking and embedding quality
- Very broad or underspecified questions may correctly result in no-answer responses
- The system intentionally prioritizes correctness over recall

These trade-offs are deliberate.

---

## Project Status

The project is in a **stable prototype** state.

Achieved goals:
- Predictable RAG behavior
- Strict source attribution
- Clear architectural separation
- Reusable backend across multiple knowledge domains

Potential future work:
- Richer retrieval diagnostics
- Configurable ranking strategies per workspace
- Extended UI for workspace and corpus management

---

## Intended Use

This project is suitable as:

- A portfolio demonstration of RAG system design
- A foundation for internal knowledge tools
- A backend for research-oriented or compliance-sensitive applications
- A base for further experimentation with retrieval strategies

---

*This repository focuses on architectural clarity and correctness rather than feature completeness.*
