"""`rag_tool` (02_architecture.md section 6.4): the one retrieval tool, called once per
index name. Wraps the shared pipeline of `app/rag/pipeline.py` and lazily builds (once per
process) the embedder, reranker, LLM client and vector store (ChromaDB, via
`app/rag/store.py`'s `connect()` -- see `docs/12_chromadb_migration.md`) from
`app/config.py`'s settings, loading a persisted index if one exists or building it from
`rag_sources/` on first use.

Input:  {"index": "router|data_analysis|inventory|knowledge_base", "query": "<text>"}
Output: see 04_rag_design.md section 6.7 (index, query, rewritten, variants, passages,
        no_relevant_passages, index_version, timings_ms), plus `warnings` and a `degraded`
        object naming which pieces (embedder/reranker/llm) are running on this sandbox's
        documented fallback instead of the real model (see app/rag/embeddings.py,
        app/rag/reranker.py, app/llm/client.py) -- never hidden from the caller, since it
        changes how much to trust the ranking.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.config import settings
from app.llm.client import GroqClient
from app.rag.embeddings import Embedder
from app.rag.indexer import run_indexer
from app.rag.pipeline import rag_tool as _run_pipeline
from app.rag.reranker import CrossEncoderReranker
from app.rag.store import VectorStore, connect

_VALID_INDEXES = {"router", "data_analysis", "inventory", "knowledge_base"}

_state: dict = {}


def _get_components() -> tuple[VectorStore, Embedder, CrossEncoderReranker, GroqClient]:
    if "store" not in _state:
        embedder = Embedder(settings.embedding_model)
        reranker = CrossEncoderReranker(settings.reranker_model)
        llm = GroqClient(api_key=settings.groq_api_key, model=settings.llm_model)

        store = connect(settings)
        if not store.has_data():  # nothing persisted yet -- build it now (the real deployment
            # runs this as the separate `indexer` container job instead, see Dockerfile).
            report, store = run_indexer(settings.rag_sources_dir, embedder=embedder, store=store)
            if not report.ok:
                raise RuntimeError(f"RAG index build failed: {report.errors[:5]}")
        elif not getattr(store, "lexicon", None):
            # Persisted chunks exist (e.g. from a prior process) but the lexicon -- built
            # only in memory during run_indexer -- was lost; rebuild to restore it rather
            # than running with no entity-aware retrieval.
            report, store = run_indexer(settings.rag_sources_dir, embedder=embedder, store=store)

        _state.update(store=store, embedder=embedder, reranker=reranker, llm=llm)
    return _state["store"], _state["embedder"], _state["reranker"], _state["llm"]


def rag_tool(index: str, query: str) -> dict:
    if index not in _VALID_INDEXES:
        return {"error": {"code": "schema_error", "message": f"`index` must be one of {sorted(_VALID_INDEXES)}"}}
    if not isinstance(query, str) or not query.strip():
        return {"error": {"code": "schema_error", "message": "`query` must be a non-empty string"}}
    if len(query) > settings.max_input_chars:
        return {"error": {"code": "schema_error", "message": f"`query` exceeds {settings.max_input_chars} characters"}}

    store, embedder, reranker, llm = _get_components()
    result = _run_pipeline(index, query, store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings)

    out = {
        "index": result.index,
        "query": result.query,
        "rewritten": result.rewritten,
        "variants": result.variants,
        "passages": result.passages,
        "no_relevant_passages": result.no_relevant_passages,
        "index_version": result.index_version,
        "timings_ms": result.timings_ms,
    }
    if result.warnings:
        out["warnings"] = result.warnings
    degraded = {}
    if result.embedder_is_fallback:
        degraded["embedder"] = "TF-IDF hashing fallback (sentence-transformers unavailable in this environment)"
    if result.reranker_is_fallback:
        degraded["reranker"] = "fusion order (cross-encoder unavailable in this environment)"
    if not llm.is_available:
        degraded["llm"] = "query rewrite/expansion skipped (no LLM client available)"
    if degraded:
        out["degraded"] = degraded
    return out
