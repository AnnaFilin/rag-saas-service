# PROJECT STATE (FACTUAL)

## 1. Purpose (as-is)
RAG service providing:
- document ingestion
- embedding storage
- hybrid retrieval (vector + FTS)
- LLM answering (Ollama / OpenAI)

Status: working, but still contains experimental and legacy remnants.

---

## 2. Ingestion paths (FACTS ONLY)

### 2.1 Local ingestion
- Exists: YES
- Used for: large documents (PDF / MD)
- Triggered by: manual scripts / local runs
- Writes to: same Postgres DB used by chat
- Isolation from cloud ingestion: PARTIAL (shared schema)

### 2.2 Cloud ingestion (GCP)
- Exists: YES
- Used for: smaller documents / API-based ingestion
- Triggered by: API / Cloud Run job
- Writes to: same Postgres DB used by chat
- Isolation from local ingestion: PARTIAL

⚠️ Local and cloud ingestion share models and tables; boundaries are not strictly enforced.

---

## 3. Runtime chat flow (VERBATIM)

Entry point:
- `src/chat_api.py`
- Route: `POST /chat`

High-level flow:
1. request received
2. question embeddings created
3. DB session opened
4. candidate chunks retrieved via:
   - pgvector similarity search
   - Postgres FTS (rare-term anchor)
5. candidates merged via RRF (Reciprocal Rank Fusion)
6. in-memory filtering applied (noise / duplicates)
7. optional entity focus applied
8. context assembled (top-K)
9. LLM called (if enabled)
10. response returned

---

## 4. Files that matter NOW (active path)

### Active files
- `src/chat_api.py` — request handling, mode logic
- `src/chat_helpers.py` — retrieval helpers, filters, RRF
- `src/repository.py` — DB access helpers
- `src/embeddings.py` — embedding creation
- `src/llm_pipeline.py` — LLM chain construction
- `src/models.py` — SQLAlchemy models
- `src/db.py` — DB session / engine

### Legacy / experimental
- `src/legacy/**` — NOT USED in chat path

---

## 5. Known problems (OBSERVED)

- Noise chunks (tables, lists, catalogs) still appear, though reduced
- Entity focus is heuristic and not guaranteed
- Retrieval behavior differs by corpus structure
- Multiple historical filters exist; not all are active
- Large files reduce readability due to accumulated experiments

---

## 6. What has RECENTLY CHANGED (FACT)

- Retrieval is now **hybrid**:
  - pgvector similarity
  - + Postgres FTS using rare tokens as lexical anchor
- Results are merged via **RRF**, not via hard thresholds
- Entity drift on encyclopedic corpora is significantly reduced
- Retrieval diagnostics are available via debug logging

---

## 7. What is explicitly NOT decided yet

- Whether entity-aware filtering should be first-class
- Whether ingestion should attach structured metadata
- Final semantics of chat modes (reference / synthesis / custom)
- Whether OpenAI and Ollama require different retrieval tuning
- Long-term separation of ingestion pipelines

---

## Snapshot — CURRENT STATE

- Backend: FastAPI
- Entry points:
  - `chat_api.py` (POST /chat)
  - `ingest_api.py` (document ingestion, separate flow)

- Retrieval mechanism:
  - pgvector similarity search
  - + Postgres FTS (rare-term anchor)
  - RRF fusion
  - noise + duplicate filtering
  - fixed CONTEXT_K

- Current status:
  Retrieval is materially more stable than previous vector-only approach.
  Codebase still requires structural cleanup and documentation,
  but behavior is now explainable and reproducible.
