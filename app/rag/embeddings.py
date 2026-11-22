"""Embedding model wrapper (04_rag_design.md section 5): `sentence-transformers/
all-MiniLM-L6-v2`, 384 dimensions, vectors normalized to unit length.

`sentence-transformers` (and its `torch` dependency) could not be verified against the real
model in this development sandbox -- not for lack of PyPI access (confirmed reachable; see
RAG_REFACTOR_REPORT.md section 8), but because this sandbox's disk quota is too small for
the CUDA-enabled `torch` wheel pip resolves by default (confirmed directly: the install
failed with `OSError: [Errno 28] No space left on device` after ~3 GB of NVIDIA CUDA
packages). `pyproject.toml`'s own `tool.uv.sources` redirect for `torch` to a CPU-only wheel
index sidesteps exactly this in the real Docker build (where `uv sync` runs), which doesn't
carry the multi-gigabyte CUDA stack at all -- this sandbox's plain `pip install` doesn't use
that redirect. This module always tries the real
model first and falls back to a deterministic, dependency-free embedder built only from
scikit-learn's `TfidfVectorizer` (already installed) so that chunking, entity extraction,
fusion, selection and the rest of the retrieval pipeline can be built and tested end-to-end
in this sandbox today. The fallback is clearly not semantically equivalent to a trained
dense model -- it is a keyword/TF-IDF space, not a semantic one -- and it is not what the
system is specified to run: the real model ships in the Docker image, which is built on a
network-enabled machine. `Embedder.is_fallback` tells the caller which one is active, and
every `rag_tool` response should surface that fact (see `app/tools/rag_tool.py`).
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

import numpy as np

try:
    from sentence_transformers import SentenceTransformer

    _HAVE_SENTENCE_TRANSFORMERS = True
except ImportError:
    _HAVE_SENTENCE_TRANSFORMERS = False

EMBEDDING_DIM = 384


def _l2_normalize(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


class _FallbackTfidfEmbedder:
    """A fixed-vocabulary hashing + TF-IDF-weighted embedder, used only when
    sentence-transformers is unavailable. It is fit once on the corpus being indexed (so
    retrieval is internally consistent for that corpus) and queries are projected into the
    same space; this means it must be built with `fit()` before `encode()` is used for a
    query that was not part of the indexed corpus -- `encode()` still works for an unseen
    string because the underlying vectorizer uses a fixed hashing trick, not a learned
    vocabulary restricted to the fit set (see `HashingVectorizer`, which needs no fit)."""

    def __init__(self, dim: int = EMBEDDING_DIM, seed: int = 0):
        from sklearn.feature_extraction.text import HashingVectorizer

        self.dim = dim
        self._vectorizer = HashingVectorizer(
            n_features=dim, alternate_sign=True, norm=None, token_pattern=r"(?u)\b\w\w+\b"
        )
        self._seed = seed

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        mat = self._vectorizer.transform(texts).toarray().astype(np.float32)
        # A deterministic small jitter from a content hash keeps otherwise-all-zero vectors
        # (very short strings that hash to nothing) distinguishable, without affecting the
        # relative ranking of any text that does have real token content.
        for i, t in enumerate(texts):
            if not np.any(mat[i]):
                h = hashlib.sha256(t.encode("utf-8")).digest()
                rng = np.random.default_rng(int.from_bytes(h[:8], "little"))
                mat[i] = rng.normal(0, 1e-6, size=self.dim)
        return _l2_normalize(mat)


class Embedder:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.is_fallback = not _HAVE_SENTENCE_TRANSFORMERS
        self._model: Optional["SentenceTransformer"] = None
        self._fallback: Optional[_FallbackTfidfEmbedder] = None
        if self.is_fallback:
            self._fallback = _FallbackTfidfEmbedder()
        else:  # pragma: no cover - exercised only where sentence-transformers is installed
            self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        """Returns an (n, 384) float32 array, L2-normalized."""
        if not texts:
            return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
        if self.is_fallback:
            return self._fallback.encode(texts)
        vecs = self._model.encode(  # pragma: no cover
            texts, batch_size=batch_size, normalize_embeddings=True, convert_to_numpy=True
        )
        return vecs.astype(np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        return self.encode([text])[0]


_WORD_RE = re.compile(r"\w+")


def estimate_word_pieces(text: str) -> int:
    """A rough stand-in for the real tokenizer's word-piece count, used only so this
    sandbox can run build check 5 (no embedded text above 256 word pieces) without the real
    model. It is more conservative than the heuristic of `chunker.estimate_tokens` (counts
    sub-word splits for long/compound words), but is still an approximation -- the real
    check requires the real tokenizer and must be re-run wherever that is available."""
    tokens = 0
    for word in _WORD_RE.findall(text):
        tokens += max(1, (len(word) + 3) // 4)
    tokens += len(re.findall(r"[^\w\s]", text))
    return tokens
