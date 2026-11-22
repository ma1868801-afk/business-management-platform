"""Re-ranking (04_rag_design.md section 6.5): the cross-encoder
`cross-encoder/ms-marco-MiniLM-L-6-v2` by default, an LLM-based fallback when it cannot be
loaded, and -- the spec's own last-resort path, used when both are unavailable -- the
fusion order, with a warning. `sentence-transformers.CrossEncoder` needs `torch`, which this
development sandbox cannot install for a disk-space reason, not a network one -- see
`app/rag/embeddings.py`'s docstring for the confirmed root cause and
RAG_REFACTOR_REPORT.md section 8 -- so `CrossEncoderReranker.is_fallback` is always true
here; `rerank()` still returns `None` to signal "could not score", which is exactly the
condition the pipeline's documented fallback path exists for.
"""
from __future__ import annotations

from typing import Optional

try:
    from sentence_transformers import CrossEncoder

    _HAVE_CROSS_ENCODER = True
except ImportError:
    _HAVE_CROSS_ENCODER = False


class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.is_fallback = not _HAVE_CROSS_ENCODER
        self._model: Optional["CrossEncoder"] = None
        if not self.is_fallback:
            self._model = CrossEncoder(model_name)  # pragma: no cover

    def score(self, query: str, candidates: list[tuple[str, str]]) -> Optional[list[tuple[str, float]]]:
        """`candidates` is [(chunk_id, embed_text), ...]. Returns [(chunk_id, score), ...]
        in the same order, or `None` if the model is unavailable (the pipeline then falls
        back per section 6.5: LLM rerank, then fusion order, each with a warning)."""
        if self.is_fallback or not candidates:
            return None
        pairs = [(query, text) for _, text in candidates]  # pragma: no cover
        scores = self._model.predict(pairs)  # pragma: no cover
        return [(cid, float(s)) for (cid, _), s in zip(candidates, scores)]  # pragma: no cover
