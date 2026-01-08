# =========================
# (all helper functions, no FastAPI app / endpoints)
# =========================

import os
import re
from typing import Any, List, Sequence

DEBUG_LOGS = os.getenv("DEBUG_LOGS", "0") == "1"


DEFAULT_ROLE = (
    "You are a helpful assistant.\n"
    "Answer ONLY using the provided context.\n"
    "If information is missing, explicitly say it is not found in the provided sources.\n"
    "Do NOT use external knowledge.\n"
)

def _dbg(*args):
    if DEBUG_LOGS:
        print(*args)


def normalize_query_for_retrieval(question: str) -> str:
    """
    Convert a natural language question into a search-like phrase
    suitable for semantic retrieval.
    """
    q = question.lower()

    for junk in [
        "summarize",
        "based on the provided sources",
        "based on the sources",
        "based on sources",
        "please",
        "what are",
        "what is",
        "give me",
        "provide",
        "?",
    ]:
        q = q.replace(junk, "")

    q = " ".join(q.split())
    return q



def rerank_by_lexical_overlap(chunks: list, question: str) -> list:
    """
    Lightweight, universal re-ranker.
    Does NOT filter, only reorders chunks.
    """

    q_terms = set(
        w for w in re.findall(r"[a-zA-Z][a-zA-Z'\-]{2,}", question.lower())
    )
    if not q_terms:
        return chunks

    def score(ch):
        text = (ch.content or "").lower()
        return sum(1 for w in q_terms if w in text)

    return sorted(
        chunks,
        key=lambda ch: (score(ch), -getattr(ch, "_rrf", 0.0)),
        reverse=True,
    )



def _is_noise_chunk(text: str) -> bool:
    """
    Universal STRUCTURAL noise filter (domain-agnostic).
    Detects formatting-heavy / non-explanatory chunks such as:
    - TOC-like lists
    - index-like entries
    - pure Q/A prompts blocks
    - header/footer/page artifacts
    - table-like dense columns
    Uses only structural signals (no topic-specific keywords).
    """

    if not text:
        return True

    t = text.strip()
    if len(t) < 160:
        return True

    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    if not lines:
        return True

    # 1) Too many very short lines -> list/TOC/table fragments
    if len(lines) >= 8:
        short_lines = sum(1 for ln in lines if len(ln) <= 45)
        if short_lines / len(lines) >= 0.70:
            return True

    # 2) Question-prompt blocks: many lines starting with numbering/bullets
    bulletish = 0
    for ln in lines[:30]:
        # patterns like: "1.", "1)", "(1)", "-", "•", "*"
        if ln[:2].isdigit() and (ln[1:2] in {".", ")"} or ln[2:3] in {".", ")"}):
            bulletish += 1
        elif ln.startswith(("-", "•", "*")):
            bulletish += 1
        elif ln.startswith(("(", "[")) and len(ln) > 2 and ln[1].isdigit():
            bulletish += 1
    if len(lines) >= 6 and bulletish >= 4:
        return True

    # 3) Table-like: high digit density OR many repeated separators with low punctuation variety
    total_chars = len(t)
    digit_ratio = sum(ch.isdigit() for ch in t) / max(1, total_chars)
    comma_ratio = t.count(",") / max(1, total_chars)
    pipe_count = t.count("|")
    tab_count = t.count("\t")
    sep_count = t.count("  ")  # double spaces often in OCR tables

    if digit_ratio >= 0.14:
        return True
    if (pipe_count + tab_count) >= 6:
        return True
    if comma_ratio >= 0.05 and len(lines) >= 6:
        return True
    if sep_count >= 20 and len(lines) >= 8:
        return True

    # 4) Header/footer artifacts: many lines are nearly identical in shape/length
    if len(lines) >= 10:
        lens = [len(ln) for ln in lines[:30]]
        same_len = sum(1 for x in lens if abs(x - lens[0]) <= 3)
        if same_len / len(lens) >= 0.60:
            return True

    return False




# def llm_filter_relevant_chunks(
#     question: str,
#     candidates: list[dict],
#     *,
#     build_llm_chain,
#     get_llm_answer,
# ) -> list[dict]:
#     """
#     Returns a subset of candidates that are explicitly relevant to the question.
#     If the model cannot find relevant evidence, returns an empty list (STRICT gate).
#     """

#     if not candidates:
#         return []

#     # Keep the prompt compact and deterministic.
#     # IMPORTANT: The model must return only JSON.
#     system_role = (
#         "You are a strict evidence filter. "
#         "You must ONLY keep chunks that clearly contain information to answer the question. "
#         "If none are clearly relevant, return an empty list. "
#         "Do not guess, do not infer, do not use outside knowledge."
#     )

#     # We keep indices so we can return the original candidate objects safely.
#     numbered = []
#     for i, c in enumerate(candidates, start=1):
#         text = (c.get("content") or "").strip()
#         if not text:
#             continue
#         numbered.append(
#             f"[{i}] SOURCE={c.get('source')}\n{text}"
#         )

#     if not numbered:
#         return []

#     context = "\n\n---\n\n".join(numbered)

#     prompt = (
#         f"{system_role}\n\n"
#         f"QUESTION:\n{question}\n\n"
#         f"SOURCES:\n{context}\n\n"
#         "Return ONLY valid JSON in the following format:\n"
#         '{ "relevant": [1, 2, 3] }\n'
#         "Rules:\n"
#         "- relevant is a list of source numbers that contain direct evidence.\n"
#         "- If there is no direct evidence, return {\"relevant\": []}.\n"
#     )

#     # Reuse your existing chain builders to avoid new dependencies.
#     chain = build_llm_chain(DEFAULT_ROLE)
#     raw = get_llm_answer(chain, prompt, "")  # context already embedded in prompt

#     # Robust JSON parsing with safe fallback to STRICT empty.
#     try:
#         import json
#         start = raw.find("{")
#         end = raw.rfind("}")
#         if start == -1 or end == -1 or end <= start:
#             return []
#         data = json.loads(raw[start : end + 1])
#         ids = data.get("relevant", [])
#         if not isinstance(ids, list):
#             return []
#         kept = []
#         for idx in ids:
#             if isinstance(idx, int) and 1 <= idx <= len(candidates):
#                 kept.append(candidates[idx - 1])
#         return kept
#     except Exception:
#         return []
def llm_filter_relevant_chunks(
    question: str,
    candidates: list[dict],
    *,
    build_llm_chain,
    get_llm_answer,
) -> list[dict]:
    """
    Keep only candidates that contain direct evidence for the question.
    Returns [] if no direct evidence is present (strict gate).
    """

    if not candidates:
        return []

    # Use a dedicated strict role for gating.
    system_role = (
        "You are a strict evidence filter.\n"
        "You must ONLY keep sources that contain direct evidence to answer the question.\n"
        "If the question mentions a specific subject (e.g., a plant name like 'Withania somnifera'),\n"
        "ONLY keep sources that explicitly mention that subject.\n"
        "Do not guess. Do not infer. Do not use outside knowledge.\n"
        "Return ONLY valid JSON.\n"
    )


    numbered = []
    for i, c in enumerate(candidates, start=1):
        text = (c.get("content") or "").strip()
        if not text:
            continue
        numbered.append(f"[{i}] SOURCE={c.get('source')}\n{text}")

    if not numbered:
        return []

    context = "\n\n---\n\n".join(numbered)

    gate_question = (
        f"QUESTION:\n{question}\n\n"
        "Return ONLY valid JSON in this format:\n"
        '{ "relevant": [1, 2, 3] }\n'
        "Rules:\n"
        "- relevant is a list of source numbers that contain direct evidence.\n"
        "- If there is no direct evidence, return {\"relevant\": []}.\n"
    )

    chain = build_llm_chain(system_role)
    raw = get_llm_answer(chain, gate_question, context)

    try:
        import json
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return []
        data = json.loads(raw[start : end + 1])
        ids = data.get("relevant", [])
        if not isinstance(ids, list):
            return []
        kept = []
        for idx in ids:
            if isinstance(idx, int) and 1 <= idx <= len(candidates):
                kept.append(candidates[idx - 1])
        return kept
    except Exception:
        return []

        

def _retrieve_candidates(
    db: Any,
    workspace_id: str,
    questions: Sequence[str],
    k_per_query: int,
    *,
    create_embeddings: Any,
    get_top_k_chunks_for_workspace: Any,
    get_top_k_chunks_fts: Any,
) -> list[Any]:
    """
    Retrieval with RRF fusion.
    """

    merged: list[Any] = []
    fallback_rows: list[Any] = []
    seen_ids: set[int] = set()

    total_rows = 0
    dropped_noise = 0
    dropped_dupe = 0
    kept = 0

    noise_samples = 0
    dupe_samples = 0

    for q in questions:
        normalized_q = normalize_query_for_retrieval(q)

        query_embeddings, _ = create_embeddings([{"content": normalized_q}])
        query_vector = query_embeddings[0].tolist()

        vector_rows = get_top_k_chunks_for_workspace(
            db=db,
            workspace_id=workspace_id,
            query_embedding=query_vector,
            k=k_per_query,
        )

        fts_rows = get_top_k_chunks_fts(
            db=db,
            workspace_id=workspace_id,
            query_text=normalized_q,
            k=50,
        )

        RRF_K = 60
        scores: dict[int, float] = {}
        chunk_by_id: dict[int, Any] = {}
        dist_by_id: dict[int, float] = {}

        for rank, (ch, dist) in enumerate(vector_rows, start=1):
            cid = int(getattr(ch, "id"))
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
            chunk_by_id[cid] = ch
            dist_by_id[cid] = float(dist)

        for rank, (ch, dist) in enumerate(fts_rows, start=1):
            cid = int(getattr(ch, "id"))
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
            chunk_by_id[cid] = ch
            dist_by_id[cid] = min(dist_by_id.get(cid, 999.0), float(dist))

        rows = [
            (chunk_by_id[cid], dist_by_id.get(cid, 999.0), float(scores[cid]))
            for cid in scores.keys()
        ]
        rows.sort(key=lambda t: t[2], reverse=True)

        total_rows += len(rows)

        for ch, dist, rrf_score in rows:
            content = (ch.content or "")

            ch_id = getattr(ch, "id", None)
            ch_id_int = int(ch_id) if ch_id is not None else None

            # Keep a small fallback pool so we never return empty after retrieval.
            if len(fallback_rows) < 50:
                if ch_id_int is None or ch_id_int not in seen_ids:
                    setattr(ch, "_distance", float(dist))
                    setattr(ch, "_rrf", float(rrf_score))
                    fallback_rows.append(ch)

            if _is_noise_chunk(content):
                dropped_noise += 1
                if noise_samples < 5:
                    noise_samples += 1
                    src = getattr(getattr(ch, "document", None), "source", None)
                    _dbg(f"[DROP:NOISE] dist={float(dist):.4f} source={src}")
                continue

            if ch_id_int is not None and ch_id_int in seen_ids:
                dropped_dupe += 1
                if dupe_samples < 5:
                    dupe_samples += 1
                    src = getattr(getattr(ch, "document", None), "source", None)
                    _dbg(f"[DROP:DUPE] dist={float(dist):.4f} source={src}")
                continue

            if ch_id_int is not None:
                seen_ids.add(ch_id_int)

            setattr(ch, "_distance", float(dist))
            setattr(ch, "_rrf", float(rrf_score))
            merged.append(ch)
            kept += 1

    merged.sort(
        key=lambda ch: (-getattr(ch, "_rrf", 0.0), getattr(ch, "_distance", 999.0))
    )

    if not merged and fallback_rows:
        fallback_rows.sort(
            key=lambda ch: (-getattr(ch, "_rrf", 0.0), getattr(ch, "_distance", 999.0))
        )
        return fallback_rows

    return merged


# --- Coverage gate (lexical overlap) ---

_STOPWORDS = {
    "a","an","the","and","or","but","if","then","else","when","while","to","of","in","on","for","from","by","with",
    "is","are","was","were","be","been","being","do","does","did",
    "what","which","who","whom","whose","where","when","why","how",
    "about","into","over","under","between","among","as","at","it","this","that","these","those","based", "only", "provided", "context", "extract", "list", "present",
    "bullet", "separate", "explicitly", "stated", "summarize", "paragraph",
}

def _tokenize_for_coverage(text: str) -> set[str]:
    # Keep it simple and deterministic (no entity extraction, no model calls).
    text = (text or "").lower()
    tokens = re.findall(r"[a-z]+", text)
    return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS}

def _passes_coverage_gate(question: str, candidates: list[dict[str, Any]]) -> bool:
    """
    Coverage gate: return True only if at least one chunk has enough lexical overlap
    with the question. This is workspace-agnostic and avoids hardcoding entities.
    """
    q_terms = _tokenize_for_coverage(question)
    if not q_terms:
        # If we can't extract meaningful terms, do not block retrieval.
        return True

    best_overlap = 0.0
    for c in candidates[:10]:  # only inspect top candidates
        content = c.get("content") or ""
        ch_terms = _tokenize_for_coverage(content)
        if not ch_terms:
            continue
        overlap = len(q_terms & ch_terms) / max(1, len(q_terms))
        if overlap > best_overlap:
            best_overlap = overlap

    # Conservative threshold: requires at least ~1 meaningful term overlap for typical questions.
    return best_overlap >= 0.20



    