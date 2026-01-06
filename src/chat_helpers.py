# =========================
# (all helper functions, no FastAPI app / endpoints)
# =========================

import os
import math
import re
from typing import Any, List, Sequence

DEBUG_LOGS = os.getenv("DEBUG_LOGS", "0") == "1"


def _dbg(*args):
    if DEBUG_LOGS:
        print(*args)


_NOISE_PATTERNS = [
    r"^\s*table of contents\b",
    r"^\s*contents\b",
    r"^\s*introduction\b",
    r"^\s*abstract\b",
    r"^\s*references\b",
    r"^\s*bibliography\b",
    r"^\s*literature\b",
    r"^\s*acknowledg(e)?ments\b",
    r"^\s*appendix\b",
    r"^\s*index\b",
]

_REF_LIKE_RE = re.compile(
    r"\b(19\d{2}|20\d{2}|vol\.|no\.|pp\.|ed\.|doi|isbn|issn|journal|proceedings|"
    r"phytochemistry|university|press|thesis|m\.sc|b\.sc)\b",
    re.IGNORECASE,
)

def _fact_density_score(text: str) -> float:
    """
    Universal heuristic: prefer prose-like, claim-bearing chunks.
    Penalize bibliography/list/table-like chunks.
    No domain keywords.
    """
    if not text:
        return -1e9

    t = text.strip()
    if len(t) < 120:
        return -1e9

    n = len(t)
    letters = sum(ch.isalpha() for ch in t)
    digits = sum(ch.isdigit() for ch in t)
    spaces = sum(ch.isspace() for ch in t)

    letters_ratio = letters / max(1, n)
    digits_ratio = digits / max(1, n)

    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    line_count = len(lines)
    short_lines = sum(1 for ln in lines if len(ln) <= 40)
    short_line_ratio = short_lines / max(1, line_count)

    punct = sum(t.count(ch) for ch in ".?!;:")
    comma_ratio = t.count(",") / max(1, n)

    ref_like_hits = 0
    if _REF_LIKE_RE.search(t):
        ref_like_hits += 1
    if "http://" in t or "https://" in t:
        ref_like_hits += 1
    if "(" in t and ")" in t:
        ref_like_hits += 1

    # Score: prose/claims up, lists/refs down
    score = 0.0
    score += 2.5 * letters_ratio
    score += 0.6 * math.log1p(punct)          # sentences signal
    score -= 2.0 * digits_ratio               # catalog-like
    score -= 1.2 * short_line_ratio           # table/list-like
    score -= 0.8 * comma_ratio                # heavy enumerations
    score -= 1.5 * ref_like_hits              # bibliography/reference-like
    score += 0.2 * math.log1p(n)              # slightly prefer longer chunks

    return score



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
    Post-filter chunks by main entity mentioned in the question.
    Universal: works for plants, places, people, terms.
    If filtering becomes too aggressive, falls back to original chunks.
    """
    q = question.lower()

    latin_match = re.findall(r"\b[a-z]+ [a-z]+\b", q)
    entity_terms = set(latin_match)

    if not entity_terms:
        entity_terms = {
            w
            for w in re.findall(r"[a-z]{5,}", q)
            if w
            not in {"which", "about", "include", "describe", "traditional", "documented"}
        }

    if not entity_terms:
        return chunks

    focused = []
    for ch in chunks:
        text = (ch.content or "").lower()
        if any(term in text for term in entity_terms):
            focused.append(ch)

    if len(focused) < min_keep:
        return chunks

    return focused


def _is_noise_chunk(text: str) -> bool:
    """
    Conservative, universal noise filter.
    """
    if not text:
        return True

    t = text.strip()
    if len(t) < 120:
        return True

    lower = t.lower()

    for pat in _NOISE_PATTERNS:
        if re.search(pat, lower):
            return True

    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    if not lines:
        return True

    short_lines = sum(1 for ln in lines if len(ln) <= 40)
    short_ratio = short_lines / max(1, len(lines))

    punct = sum(t.count(ch) for ch in "?!;:")
    digit_ratio = sum(ch.isdigit() for ch in t) / max(1, len(t))
    comma_ratio = t.count(",") / max(1, len(t))

    if (short_ratio >= 0.70 or digit_ratio >= 0.12) and punct <= 1:
        return True

    if comma_ratio > 0.03 and punct == 0 and len(lines) >= 6:
        return True

    return False


def _rewrite_queries(
    question: str,
    *,
    llm_enabled: bool,
    query_rewrite_enabled: bool,
    query_rewrite_n: int,
    build_llm_chain: Any,
    get_llm_answer: Any,
) -> list[str]:
    """
    Generate alternative search queries for better retrieval.
    """
    if not llm_enabled or not query_rewrite_enabled:
        return [question]

    rewrite_role = (
        "You rewrite a user's question into short search queries for semantic retrieval.\n"
        "Return 3 alternative queries (one per line), no numbering, no extra text.\n"
        "Use synonyms and related phrases that may appear in books.\n"
        "Do NOT answer the question."
    )

    try:
        chain = build_llm_chain(rewrite_role)
        raw = get_llm_answer(chain, question, context="")
        lines = [line.strip(" -\t\r\n") for line in raw.splitlines() if line.strip()]

        queries = []
        for q in lines:
            if q and q.lower() != question.lower():
                queries.append(q)

        merged = [question] + queries

        seen = set()
        out = []
        for q in merged:
            key = q.lower()
            if key not in seen:
                seen.add(key)
                out.append(q)

        return out[: max(1, query_rewrite_n + 1)]
    except Exception:
        return [question]



def llm_filter_relevant_chunks(
    question: str,
    candidates: list[dict],
    *,
    build_llm_chain: Any,
    get_llm_answer: Any,
) -> list[dict]:
    """
    LLM-assisted relevance selection (SOFT):
    - Keep a base set of top candidates always
    - Optionally add LLM-picked items
    - Never drop the base set
    """
    if not candidates:
        return candidates

    # Base context that must always survive (universal invariant)
    min_keep = max(3, len(candidates) // 3)
    base = candidates[:min_keep]

    items = []
    for i, c in enumerate(candidates):
        text = (c.get("content") or "").strip()
        preview = text[:300].replace("\n", " ")
        items.append(f"[{i}] {preview}")

    filter_prompt = (
        "You are given a question and a list of text chunks.\n"
        "Select ONLY the chunks that contain information directly relevant to the question.\n"
        "Return ONLY indices as comma-separated integers, like: 0,2,3\n"
        "If none are relevant, return: -1\n\n"
        f"Question:\n{question}\n\n"
        "Chunks:\n" + "\n".join(items)
    )

    try:
        chain = build_llm_chain(
            "You are a strict relevance filter.\n"
            "Output ONLY comma-separated integers (e.g., 0,2,3) or -1.\n"
            "No extra words."
        )

        raw = get_llm_answer(chain, filter_prompt, context="")
        raw = (raw or "").strip()

        import re
        nums = [int(x) for x in re.findall(r"-?\d+", raw)]

        picked = []
        if not (nums == [-1] or len(nums) == 0):
            picked = [candidates[i] for i in nums if 0 <= i < len(candidates)]

        # Merge base + picked, dedupe by chunk_id, preserve original order
        seen = set()
        merged = []
        for c in (base + picked):
            cid = c.get("chunk_id")
            key = cid if cid is not None else id(c)
            if key in seen:
                continue
            seen.add(key)
            merged.append(c)

        return merged

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

    CONTEXT_K = 8
    selected = merged[:CONTEXT_K]

    _dbg("=== RETRIEVAL SUMMARY ===")
    _dbg("total_rows:", total_rows)
    _dbg("dropped_noise:", dropped_noise)
    _dbg("dropped_dupe:", dropped_dupe)
    _dbg("kept_after_filters:", kept)
    _dbg("selected_for_context:", len(selected))
    if selected:
        _dbg("selected rrf:", [round(getattr(ch, "_rrf", 0.0), 6) for ch in selected])
        _dbg("selected distances:", [round(getattr(ch, "_distance", 0.0), 4) for ch in selected])
        _dbg("selected sources:", [getattr(ch.document, "source", None) for ch in selected])
    _dbg("=========================")

    return selected
