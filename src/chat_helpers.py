# =========================
# (all helper functions, no FastAPI app / endpoints)
# =========================

import os
import re
from typing import Any, List, Sequence

DEBUG_LOGS = os.getenv("DEBUG_LOGS", "0") == "1"


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


def focus_by_entity(chunks: List, question: str, min_keep: int = 3) -> List:
    """
    Apply entity focus ONLY when the question contains a clear named entity.
    If the question is generic (no entity), do not filter.
    """
    q = (question or "").strip().lower()

    # Heuristic: detect "entity-like" queries by requiring at least one strong entity signal.
    # This function must stay domain-agnostic.
    entity_terms = set(re.findall(r"\b[a-z]{3,}(?:[-'][a-z]{2,})+\b", q))

    # Also allow two-word capitalized patterns if you later support non-latin text;
    # for now keep it simple and safe: if no entity signal -> do not filter.
    if not entity_terms:
        return chunks

    focused = []
    for ch in chunks:
        text = (getattr(ch, "content", "") or "").lower()
        if any(term in text for term in entity_terms):
            focused.append(ch)

    if len(focused) < min_keep:
        return chunks

    return focused


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




def llm_filter_relevant_chunks(
    question: str,
    candidates: list[dict],
    *,
    build_llm_chain: Any,
    get_llm_answer: Any,
) -> list[dict]:
    """
    Ask LLM which chunks are actually relevant to the question.
    """
    if not candidates:
        return candidates

    items = []
    for i, c in enumerate(candidates):
        text = (c.get("content") or "").strip()
        preview = text[:300].replace("\n", " ")
        items.append(f"[{i}] {preview}")

    filter_prompt = (
        "You are given a question and a list of text chunks.\n"
        "Select ONLY the chunks that contain information directly relevant to the question.\n"
        "Ignore chunks about other entities, lists, tables, catalogs, or unrelated topics.\n\n"
        "Return ONLY a comma-separated list of indices (for example: 0,2,3).\n"
        "If none are relevant, return an empty line.\n\n"
        f"Question:\n{question}\n\n"
        "Chunks:\n" + "\n".join(items)
    )

    try:
        chain = build_llm_chain("You are a strict relevance filter. Do not explain anything.")
        raw = get_llm_answer(chain, filter_prompt, context="")
        indices = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
        return [candidates[i] for i in indices if 0 <= i < len(candidates)]
    except Exception:
        return candidates


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

            if _is_noise_chunk(content):
                dropped_noise += 1
                if noise_samples < 5:
                    noise_samples += 1
                    src = getattr(getattr(ch, "document", None), "source", None)
                    _dbg(f"[DROP:NOISE] dist={float(dist):.4f} source={src}")
                continue

            ch_id = getattr(ch, "id", None)
            if ch_id is not None and int(ch_id) in seen_ids:
                dropped_dupe += 1
                if dupe_samples < 5:
                    dupe_samples += 1
                    src = getattr(getattr(ch, "document", None), "source", None)
                    _dbg(f"[DROP:DUPE] dist={float(dist):.4f} source={src}")
                continue

            if ch_id is not None:
                seen_ids.add(int(ch_id))

            setattr(ch, "_distance", float(dist))
            setattr(ch, "_rrf", float(rrf_score))
            merged.append(ch)
            kept += 1

    merged.sort(key=lambda ch: (-getattr(ch, "_rrf", 0.0), getattr(ch, "_distance", 999.0)))

    return merged