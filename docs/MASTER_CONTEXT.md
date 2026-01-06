# MASTER_CONTEXT.md
## RAG System — Current State & Work Plan

---

## A. SYSTEM / RAG STATE (FACTUAL, AS-IS)

### 1. What this system is
Universal RAG backend intended to work with:
- multiple workspaces
- heterogeneous corpora (encyclopedias, ethnobotany PDFs, textbooks)
- different question styles (fact lookup, synthesis, analytical extraction)

Backend stack:
- FastAPI
- pgvector (cosine distance)
- Postgres FTS
- chunk-based retrieval
- Ollama / OpenAI as LLM backend

This is **not** a chatbot — it is a **retrieval-first system**.

---

### 2. Ingestion (current reality)

- Multiple ingestion paths exist (local + cloud)
- Documents are chunked uniformly
- No strong metadata normalization
- No enforced entity boundaries during ingestion
- Chunks from different plants/entities freely coexist

**Result:**  
Retrieval often returns:
- correct documents
- but mixed or weakly related chunks

---

### 3. Retrieval pipeline (current)

High-level flow:

1. User question received
2. (Optionally) rewritten into multiple queries
3. For each query:
   - embedding search (pgvector)
   - FTS search (Postgres)
4. Results fused with RRF
5. Noise filtering (tables, short chunks, catalogs)
6. De-duplication
7. Optional entity focus
8. Context capped (CONTEXT_K)
9. Optional LLM relevance filter
10. Context passed to LLM

This pipeline **does work technically** (no crashes)  
but **semantic quality varies strongly by corpus**.

---

### 4. Chat modes (important)

#### Reference mode
- Intended for **one atomic factual question**
- Uses strict grounding
- Will refuse multi-part questions
- Often produces short answers

Status: **working as designed**, but limited by context quality.

---

#### Synthesis mode
- Allows multi-part questions
- Combines multiple chunks
- Still strictly context-bound
- Does NOT infer missing facts

Status: **working**, but answers feel “thin” when corpus is sparse or encyclopedic.

---

#### Custom role mode
- User provides full system role
- Overrides default/synthesis roles
- Allows analytical or abstract extraction
- Still constrained by retrieved context

Status: **working**, but heavily dependent on:
- quality of retrieval
- clarity of role prompt

---

### 5. Current observed problems (no speculation)

- Many answers are short or feel empty
- This is often because:
  - corpus chunks are descriptive, not usage-oriented
  - relevant info exists but is split across distant chunks
  - entity mixing causes conservative LLM behavior
- Increasing K does NOT reliably improve answers
- LLM correctly refuses to hallucinate (this is good)

**Key insight:**  
The system is *honest but underfed*, not broken.

---

### 6. What is explicitly NOT solved yet

- Optimal retrieval strategy per corpus type
- Whether entity-aware ingestion is required
- Whether different modes need different retrieval depth
- Whether synthesis should relax some grounding rules
- How to normalize “meatier” answers without hallucination

---

## B. UI / UX NOTES (PARKING LOT — NO LOGIC)

> This section intentionally contains **no solutions**.

- **UX-1:** User does not understand what kind of question fits which mode
- **UX-2:** Reference mode feels broken due to atomic-question restriction
- **UX-3:** Synthesis mode does not explain why answers may still be short
- **UX-4:** Custom role field has no guidance or examples
- **UX-5:** User cannot tell whether weak answers come from data, retrieval, or grounding
- **UX-6:** No feedback explaining corpus limitations

---

## C. WORK DISCIPLINE (IMPORTANT)

- UX work and RAG logic are handled in **separate chats**
- This document is the **single source of truth**
- Any new experiment must:
  - be committed
  - be briefly documented here
- No silent logic changes

---

## D. CURRENT STATUS SUMMARY

- System is **stable**
- Retrieval is **honest but conservative**
- Short answers are **expected given current data**
- Improvements must be **incremental**, not rewrites

---
