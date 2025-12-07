# RAG Local Prototype – TODO

## Learning with Cursor

- Use ASK mode to understand each core module:
  - `src/load_docs.py` – document loading
  - `src/process_texts.py` – chunking
  - `src/build_index.py` – embeddings + index
  - `src/query_engine.py` – semantic search
  - `src/llm_pipeline.py` – RAG chain
- Keep explanations in `docs/current-architecture.md` (only summaries, no code).

## Boundaries for this repo

- Do NOT change the core logic in this project.
- Use it only as:
  - a local RAG playground,
  - a reference implementation for the future cloud RAG SaaS.
- Any new cloud/backend code should live in a **separate repository**.

## Future separate project (cloud RAG SaaS)

- New repo: `rag-saas-service` (name TBD).
- Copy `docs/system-design.md` there as the starting point.
- Implement:
  - backend (FastAPI + vector DB),
  - frontend (simple SPA),
  - LLM integration via external API.


## RAG core refactor (from local prototype)

- Reuse `create_embeddings` logic as a generic "chunks → embeddings" function (no Chroma dependency).
- Replace `store_in_chroma` with a new storage layer using Neon Postgres + pgvector
  (same role: "embeddings → index", but without Chroma).
- Drop the `__main__` demo flow from `build_index.py` in the new service (ingest will be triggered via API, not by running the file directly).
