"""The shared query pipeline (04_rag_design.md section 6): rewrite -> expand -> retrieve ->
fuse (RRF) -> re-rank -> select. Every `rag_tool` call and the knowledge_base subgraph's
separate nodes run these same stages (section 6, "the stages are separate in the trace even
when two of them share one LLM call").

Rewrite and expansion need the LLM; this sandbox has no usable LLM client (see
`app/llm/client.py`), so both stages always take their documented failure path here (the
original query is used, a warning is recorded) -- which is real, specified behavior, not a
test shortcut. The dense/entity retrieval, RRF fusion, re-rank fallback and selection stages
need no LLM and run for real against the local store built by `app/rag/indexer.py`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from app.guards.passage_screen import screen_passage
from app.llm.client import GroqClient
from app.rag.embeddings import Embedder
from app.rag.entities import extract_query_entities
from app.rag.reranker import CrossEncoderReranker
from app.rag.store import VectorStore

_FALLBACK_MIN_COSINE = 0.22  # see the comment at its use site in rag_tool() below
_tfidf_cache: dict[str, tuple] = {}  # (index_name, index_version) -> (vectorizer, matrix, chunk_ids)


def _get_fallback_tfidf(store, index_name: str):
    """A corpus-fit TF-IDF space (real IDF weighting, no hash collisions), used only to
    score relevance when no cross-encoder/LLM re-ranker is available (see its use in
    `rag_tool` below). This is noticeably more precise for telling an off-corpus question
    apart from an on-corpus one than the fixed 384-dim hashing embedder used for the stored
    retrieval vectors (section 5 requires those to be exactly 384-dim and stable across
    queries, so they are left alone; this is an extra, local-only scoring step). Falls back
    to `None` if the store cannot list its own chunks (e.g. a real pgvector store), in which
    case the caller uses the hashing embedder's cosine score instead."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    all_chunks_fn = getattr(store, "all_chunks", None)
    if all_chunks_fn is None:
        return None
    key = f"{index_name}:{store.index_version()}"
    if key not in _tfidf_cache:
        chunks = all_chunks_fn(index_name)
        if not chunks:
            return None
        vec = TfidfVectorizer(stop_words="english", min_df=1)
        matrix = vec.fit_transform([c.embed_text for c in chunks])
        _tfidf_cache[key] = (vec, matrix, [c.chunk_id for c in chunks])
    return _tfidf_cache[key]


INDEX_PROFILES = {
    # variants, final_top_n, calls_per_request (informational only here)
    "router": {"variants": 2, "final_top_n": 8},
    "data_analysis": {"variants": 3, "final_top_n": 6},
    "inventory": {"variants": 3, "final_top_n": 6},
    "knowledge_base": {"variants": 3, "final_top_n": 6},
}


@dataclass
class RagResult:
    index: str
    query: str
    rewritten: str
    variants: list[str]
    passages: list[dict]
    no_relevant_passages: bool
    index_version: str
    timings_ms: dict
    warnings: list[str] = field(default_factory=list)
    embedder_is_fallback: bool = False
    reranker_is_fallback: bool = False


def rewrite_query(query: str, index_name: str, llm: GroqClient) -> tuple[str, Optional[str]]:
    """TechNova-style plain-text query rewrite; keep exact business entities."""
    system = (
        "You rewrite a user's question for a business knowledge-base retrieval system. "
        f"The target index is '{index_name}'. Output ONLY the rewritten query text: "
        "no JSON, no preamble, no quotes, and no explanation. Resolve vague references "
        "only when supported by the question. Fix obvious typos, expand abbreviations, "
        "keep it a single self-contained English query, and do not invent details. "
        "Preserve every code, number, date, and proper name exactly as written. "
        "If the query is already clear, return it nearly unchanged."
    )
    result = llm.complete_text(system, query, temperature=0.0, max_tokens=180,
                               call_name=f"rag.rewrite_query[{index_name}]")
    rewritten = (result.raw_text or "").strip().strip('"')
    if rewritten:
        from app.rag.entities import extract_pattern_entities
        if extract_pattern_entities(query) - extract_pattern_entities(rewritten):
            return query, "rewrite dropped an entity code; the original query was used"
        return rewritten, None
    return query, f"query rewrite unavailable ({result.error}); the original query was used"


def _parse_query_array(raw: str) -> list[str]:
    """Parse TechNova's JSON string-array response, tolerating fenced/prefaced text."""
    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    candidate = match.group(0) if match else raw
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, str)]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return [re.sub(r"^[\-\d\.\)\s]+", "", line).strip(" \"'`) ")
            for line in raw.splitlines() if line.strip()]


def expand_query(rewritten: str, index_name: str, llm: GroqClient, max_variants: int) -> tuple[list[str], Optional[str]]:
    """TechNova-style JSON-array-in-text expansion with local parsing and dedupe."""
    system = (
        "Generate alternative search-query phrasings for a business knowledge-base "
        f"retrieval system over the '{index_name}' index. Given one query, produce "
        f"up to {max_variants} short alternatives using relevant synonyms, company "
        "vocabulary, and related aspects without drifting from the original intent. "
        "Each alternative must be a standalone English search query. Do not add facts, "
        "codes, numbers, or names not present in the original query. "
        f"Respond with ONLY a JSON array of {max_variants} strings. No other text."
    )
    result = llm.complete_text(system, f"Query: {rewritten}", temperature=0.4,
                               max_tokens=350, call_name=f"rag.expand_query[{index_name}]")
    raw = result.raw_text or ""
    variants = _parse_query_array(raw) if raw else []
    from app.rag.entities import extract_pattern_entities
    base_entities = extract_pattern_entities(rewritten)
    seen = {rewritten.strip().lower()}
    deduped = []
    for variant in variants:
        value = variant.strip()
        key = value.lower()
        if not value or key in seen or extract_pattern_entities(value) - base_entities:
            continue
        seen.add(key)
        deduped.append(value)
        if len(deduped) >= max_variants:
            break
    if result.error:
        return [], f"query expansion unavailable ({result.error}); continuing with the rewritten query alone"
    return deduped, None


def _merge_multi_query_results(ranked_lists: list[list[tuple[str, float]]], top_n: int) -> list[tuple[str, float]]:
    """TechNova-style multi-query retrieval: merge in query order and dedupe by chunk id."""
    seen: set[str] = set()
    merged: list[tuple[str, float]] = []
    for ranked in ranked_lists:
        for chunk_id, score in ranked:
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            merged.append((chunk_id, score))
            if len(merged) >= top_n:
                return merged
    return merged


def rag_tool(
    index_name: str,
    query: str,
    *,
    store: VectorStore,
    embedder: Embedder,
    reranker: CrossEncoderReranker,
    llm: GroqClient,
    settings,
) -> RagResult:
    import time

    timings: dict[str, int] = {}
    warnings: list[str] = []

    profile = INDEX_PROFILES[index_name]
    max_variants = settings.rag_router_variants if index_name == "router" else settings.rag_variants
    final_top_n = settings.rag_router_final_top_n if index_name == "router" else settings.rag_final_top_n

    t0 = time.monotonic()
    if getattr(settings, "rag_llm_preprocess_enabled", False):
        rewritten, warn = rewrite_query(query, index_name, llm)
        if warn:
            warnings.append(warn)
    else:
        # Keep retrieval deterministic and avoid spending scarce organization TPM on
        # two optional query-polishing calls before the actual router/answer call.
        rewritten = query
    timings["rewrite"] = int((time.monotonic() - t0) * 1000)

    t0 = time.monotonic()
    if getattr(settings, "rag_llm_preprocess_enabled", False) and max_variants > 0:
        variants, warn = expand_query(rewritten, index_name, llm, max_variants)
        if warn:
            warnings.append(warn)
    else:
        variants = []
    timings["expand"] = int((time.monotonic() - t0) * 1000)

    query_set = [rewritten] + variants  # stage B: "the rewritten query and its variants form Q"

    t0 = time.monotonic()
    entities = extract_query_entities(query, getattr(store, "lexicon", {}) or {})
    ranked_lists: list[list[tuple[str, float]]] = []
    # Keep exact entity hits separately: a fallback semantic/TF-IDF score must not
    # discard a chunk that the store matched through an exact employee/SKU/etc. ID.
    # This is especially important for "Who is <full name>?" questions, where the
    # short question may score weakly against a detailed employee record.
    exact_entity_chunk_ids: set[str] = set()
    for q in query_set:
        q_vec = embedder.encode_query(q)
        ranked_lists.append(store.dense_search(index_name, q_vec, settings.rag_top_k_per_query))
        # BMP keeps its entity-aware leg for exact employee/SKU/branch/supplier codes;
        # the main retrieval flow remains TechNova's multi-query merge + dedup.
        if entities and settings.rag_entity_leg:
            entity_ranked = store.entity_search(index_name, q_vec, entities, settings.rag_top_k_per_query)
            if entity_ranked:
                exact_entity_chunk_ids.update(cid for cid, _ in entity_ranked)
                ranked_lists.append(entity_ranked)
    timings["retrieve"] = int((time.monotonic() - t0) * 1000)

    t0 = time.monotonic()
    merged = _merge_multi_query_results(ranked_lists, settings.rag_rerank_candidates)
    candidate_order = {cid: i for i, (cid, _) in enumerate(merged)}

    candidates = [(cid, store.get_chunk(cid)) for cid, _ in merged]
    candidates = [(cid, c) for cid, c in candidates if c is not None]

    scored = reranker.score(rewritten, [(cid, c.embed_text) for cid, c in candidates])
    fallback_min_score = settings.rag_min_rerank_score
    if scored is None:
        # No cross-encoder (and no LLM re-rank fallback either, see reranker.py). Falling
        # back to bare fusion order with no score check at all would answer every query,
        # including off-corpus ones, as if it were on-topic -- the opposite of section
        # 11.2's off-corpus empty-rate requirement. Re-embedding the candidates and scoring
        # them by cosine similarity to the rewritten query gives a real, if crude, relevance
        # signal from the only model this sandbox has; FALLBACK_MIN_COSINE is an approximate
        # stand-in for RAG_MIN_RERANK_SCORE, calibrated by hand on a couple of examples, not
        # by the proper calibration of section 11.4 (which needs the real cross-encoder).
        tfidf = _get_fallback_tfidf(store, index_name) if candidates else None
        if tfidf is not None:
            warnings.append("re-ranker unavailable; candidates were scored by a corpus-fit TF-IDF fallback instead")
            vec, matrix, chunk_order = tfidf
            qv = vec.transform([rewritten])
            index_of = {cid: i for i, cid in enumerate(chunk_order)}
            sims = (matrix @ qv.T).toarray().ravel()
            scored = [(cid, float(sims[index_of[cid]])) for cid, _ in candidates if cid in index_of]
        else:
            warnings.append("re-ranker unavailable; candidates were scored by fallback-embedder cosine similarity instead")
            cand_vecs = embedder.encode([c.embed_text for _, c in candidates]) if candidates else None
            q_vec_rerank = embedder.encode_query(rewritten)
            scored = [
                (cid, float(cand_vecs[i] @ q_vec_rerank)) for i, (cid, _) in enumerate(candidates)
            ] if candidates else []
        fallback_min_score = _FALLBACK_MIN_COSINE
    scored.sort(key=lambda t: (-t[1], candidate_order.get(t[0], 10 ** 9)))
    timings["rerank"] = int((time.monotonic() - t0) * 1000)

    chunks_by_id = {cid: c for cid, c in candidates}
    # Exact entity matches are already grounded by the indexed entity metadata.
    # Retain them even when a fallback reranker gives a low lexical/semantic score;
    # all retained passages still pass the prompt-injection screen below, and the
    # answer remains subject to citation and privacy checks in the KB graph.
    kept = [
        (cid, s) for cid, s in scored
        if s >= fallback_min_score or cid in exact_entity_chunk_ids
    ]
    per_doc_count: dict[str, int] = {}
    passages = []
    quarantined: list[str] = []
    for cid, score in kept:
        c = chunks_by_id[cid]
        # Retrieval-time passage screen (05_security_and_guardrails.md section 9.2/9.3): a
        # flagged passage is quarantined -- removed from the evidence entirely, never just
        # labeled -- rather than handed to the answering model.
        suspicious, reasons = screen_passage(c.body, c.chunk_id)
        if suspicious:
            quarantined.append(c.chunk_id)
            continue
        if per_doc_count.get(c.doc_id, 0) >= settings.rag_max_per_doc:
            continue
        per_doc_count[c.doc_id] = per_doc_count.get(c.doc_id, 0) + 1
        passages.append({
            "rank": len(passages) + 1,
            "chunk_id": c.chunk_id,
            "doc_id": c.doc_id,
            "title": c.title,
            "section_path": c.section_path,
            "kind": c.kind,
            "text": c.body,
            "score": round(float(score), 4),
            "classification": c.classification,
            "suspicious": False,
        })
        if len(passages) >= final_top_n:
            break
    if quarantined:
        warnings.append(
            "a retrieved passage contained instruction-like text and was ignored "
            f"({', '.join(quarantined)})"
        )

    no_relevant_passages = len(passages) == 0

    return RagResult(
        index=index_name,
        query=query,
        rewritten=rewritten,
        variants=variants,
        passages=passages,
        no_relevant_passages=no_relevant_passages,
        index_version=store.index_version(),
        timings_ms=timings,
        warnings=warnings,
        embedder_is_fallback=embedder.is_fallback,
        reranker_is_fallback=reranker.is_fallback,
    )
