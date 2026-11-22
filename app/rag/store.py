"""The RAG vector store (04_rag_design.md section 5, as updated by
`docs/12_chromadb_migration.md`): all RAG data -- chunk text, metadata and 384-dim
embeddings, the per-index build manifest, and the cross-document entity lexicon
(section 8.2) -- lives in ChromaDB, one collection per index (`rag_router`,
`rag_data_analysis`, `rag_inventory`, `rag_knowledge_base`) plus a small `rag_meta`
collection for the two cross-index values. PostgreSQL keeps only business data; the SQL
tool's `bmp_readonly` role never had and still has no RAG grant of any kind (there is now
no RAG schema in Postgres at all for it to be denied against -- see
`tests/test_db_role_permissions.py`'s note on this).

`chromadb` was not installed in this project's main development/test venv (the one
`tests/*.py` run against -- see `pyproject.toml`'s own `[project.optional-dependencies]`
split, and `11_deployment_guide.md`'s prerequisites). This module therefore also offers a
local, file-backed store with the exact same `VectorStore` query surface (dense leg, entity
leg, upsert-by-content-hash, meta/lexicon persistence) so the indexer and the retrieval
pipeline can be built and tested without it. `ChromaStore` is what ships; `LocalNpyStore` is
the fallback, selected automatically by `connect()` only when `chromadb` is not importable --
never used otherwise. `tests/test_chroma_store.py` exercises `ChromaStore`'s own logic
against a small, faithful fake of the real `chromadb` client/collection API (documented
there) so the suite doesn't need the real package installed to run; `RAG_REFACTOR_REPORT.md`
section 8 separately verified `ChromaStore`/`connect()`/`_connect_chroma_with_retry` against
a real, locally-installed Chroma 1.5.9 server (the version `docker-compose.yml` pins),
including the actual startup race this module's retry logic exists to handle.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import logging
import time

import numpy as np
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from app.rag.chunker import ChunkRecord

try:
    import chromadb  # noqa: F401

    _HAVE_CHROMADB = True
except ImportError:
    _HAVE_CHROMADB = False

logger = logging.getLogger("bmp.rag.store")

INDEX_NAMES = ("router", "data_analysis", "inventory", "knowledge_base")


class VectorStore:
    """Common interface implemented by both backends."""

    def upsert_index(self, index_name: str, documents: dict, chunks: list[ChunkRecord], embeddings: np.ndarray) -> None:
        raise NotImplementedError

    def dense_search(self, index_name: str, query_vec: np.ndarray, top_k: int) -> list[tuple[str, float]]:
        raise NotImplementedError

    def entity_search(self, index_name: str, query_vec: np.ndarray, entities: set[str], top_k: int) -> list[tuple[str, float]]:
        raise NotImplementedError

    def get_chunk(self, chunk_id: str) -> Optional[ChunkRecord]:
        raise NotImplementedError

    def index_version(self) -> str:
        raise NotImplementedError

    def set_index_version(self, version: str) -> None:
        raise NotImplementedError

    def set_lexicon(self, lexicon: dict[str, str]) -> None:
        raise NotImplementedError

    def has_data(self) -> bool:
        raise NotImplementedError


class LocalNpyStore(VectorStore):
    """A single-process, file-backed stand-in for the real `ChromaStore`, used only when
    `chromadb` cannot be imported (this sandbox). One JSON manifest per index plus one
    `.npy` embedding matrix; loaded fully into memory, which is fine at the corpus's real
    scale (about 1,300 chunks, see section 5's note that an exact scan beats HNSW below
    tens of thousands of rows anyway)."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._chunks: dict[str, dict[str, ChunkRecord]] = {}  # index_name -> {chunk_id: record}
        self._embeddings: dict[str, np.ndarray] = {}  # index_name -> (n, dim)
        self._order: dict[str, list[str]] = {}  # index_name -> [chunk_id, ...] matching embeddings rows
        self._version: Optional[str] = None
        self.lexicon: dict[str, str] = {}
        self._load()

    def _index_path(self, index_name: str) -> Path:
        return self.root / f"{index_name}.json"

    def _emb_path(self, index_name: str) -> Path:
        return self.root / f"{index_name}.npy"

    def _load(self) -> None:
        for p in self.root.glob("*.json"):
            if p.stem == "_meta":
                continue
            index_name = p.stem
            data = json.loads(p.read_text())
            records = {c["chunk_id"]: ChunkRecord(**c) for c in data["chunks"]}
            self._chunks[index_name] = records
            self._order[index_name] = [c["chunk_id"] for c in data["chunks"]]
            emb_path = self._emb_path(index_name)
            if emb_path.exists():
                self._embeddings[index_name] = np.load(emb_path)
        meta_path = self.root / "_meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            self._version = meta.get("index_version")
            self.lexicon = meta.get("lexicon", {})

    def upsert_index(self, index_name: str, documents: dict, chunks: list[ChunkRecord], embeddings: np.ndarray) -> None:
        self._chunks[index_name] = {c.chunk_id: c for c in chunks}
        self._order[index_name] = [c.chunk_id for c in chunks]
        self._embeddings[index_name] = embeddings
        (self.root / f"{index_name}.json").write_text(
            json.dumps({"chunks": [asdict(c) for c in chunks]}, ensure_ascii=False)
        )
        np.save(self._emb_path(index_name), embeddings)

    def set_index_version(self, version: str) -> None:
        self._version = version
        self._write_meta()

    def set_lexicon(self, lexicon: dict[str, str]) -> None:
        self.lexicon = lexicon
        self._write_meta()

    def _write_meta(self) -> None:
        (self.root / "_meta.json").write_text(
            json.dumps({"index_version": self._version, "lexicon": self.lexicon}, ensure_ascii=False)
        )

    def index_version(self) -> str:
        return self._version or "unversioned"

    def _cosine(self, index_name: str, query_vec: np.ndarray, candidate_ids: Optional[list[str]] = None) -> list[tuple[str, float]]:
        order = self._order.get(index_name, [])
        emb = self._embeddings.get(index_name)
        if emb is None or not order:
            return []
        if candidate_ids is not None:
            idx = [order.index(cid) for cid in candidate_ids if cid in order]
            if not idx:
                return []
            sub_emb = emb[idx]
            sub_ids = [order[i] for i in idx]
        else:
            sub_emb = emb
            sub_ids = order
        sims = sub_emb @ query_vec  # vectors are unit-normalized, so dot product == cosine
        return list(zip(sub_ids, sims.tolist()))

    def dense_search(self, index_name: str, query_vec: np.ndarray, top_k: int) -> list[tuple[str, float]]:
        scored = self._cosine(index_name, query_vec)
        scored.sort(key=lambda t: -t[1])
        return scored[:top_k]

    def entity_search(self, index_name: str, query_vec: np.ndarray, entities: set[str], top_k: int) -> list[tuple[str, float]]:
        records = self._chunks.get(index_name, {})
        candidate_ids = [cid for cid, r in records.items() if entities & set(r.entities)]
        if not candidate_ids:
            return []
        scored = self._cosine(index_name, query_vec, candidate_ids)
        scored.sort(key=lambda t: -t[1])
        return scored[:top_k]

    def get_chunk(self, chunk_id: str) -> Optional[ChunkRecord]:
        for records in self._chunks.values():
            if chunk_id in records:
                return records[chunk_id]
        return None

    def all_chunks(self, index_name: str) -> list[ChunkRecord]:
        return list(self._chunks.get(index_name, {}).values())

    def has_data(self) -> bool:
        return bool(self._chunks)


def _chunk_metadata(c: ChunkRecord) -> dict:
    """Chroma metadata values must be str/int/float/bool (no lists, no None), so the
    `entities` array is flattened to a comma-joined string here and the full record is
    additionally kept as a JSON string (`record_json`) so `get_chunk`/`all_chunks` can
    reconstruct the exact same `ChunkRecord` the indexer built, including the fields
    (classification, owner, effective_date, ...) that are not promoted to their own
    filterable metadata field."""
    return {
        "doc_id": c.doc_id,
        "chunk_no": c.chunk_no,
        "entities_csv": ",".join(sorted(c.entities)),
        "record_json": json.dumps(asdict(c), ensure_ascii=False),
    }


class ChromaStore(VectorStore):
    """The production store: every RAG index lives in its own ChromaDB collection
    (`rag_<index_name>`), created with cosine distance (`hnsw:space: cosine`) so the score
    `ChromaStore` returns (`1 - distance`) is directly comparable to the cosine-similarity
    scores the rest of the pipeline (RRF fusion, the TF-IDF/cosine re-rank fallback) already
    assumes. A small `rag_meta` collection holds one document (`_meta`) whose body is a JSON
    blob of `{"index_version": ..., "lexicon": ..., "chunk_index": {chunk_id: index_name}}`
    -- the `chunk_index` map lets `get_chunk` find a chunk's collection in one lookup instead
    of scanning all four.

    `entity_search` has no ANN shortcut: Chroma's `where` filters match scalar equality (or
    `$in`/`$contains` on document text), not "this string metadata field contains one of
    these tokens", so the entity leg fetches every chunk's metadata for the index (cheap at
    this corpus's scale, same justification `LocalNpyStore` documents), filters in Python by
    `entities_csv`, then re-fetches just those candidates' embeddings for an exact cosine
    scan -- functionally identical to `LocalNpyStore.entity_search`, just sourced from Chroma
    instead of an in-memory matrix.
    """

    _META_COLLECTION = "rag_meta"
    _META_DOC_ID = "_meta"

    def __init__(self, client):
        if not _HAVE_CHROMADB:
            raise RuntimeError("chromadb is not installed; use LocalNpyStore in this environment")
        self.client = client
        self._collections: dict[str, "chromadb.Collection"] = {}
        self._version: Optional[str] = None
        self.lexicon: dict[str, str] = {}
        self._chunk_index: dict[str, str] = {}  # chunk_id -> index_name
        self._load_meta()

    def _collection(self, index_name: str):
        if index_name not in self._collections:
            self._collections[index_name] = self.client.get_or_create_collection(
                f"rag_{index_name}", metadata={"hnsw:space": "cosine"}
            )
        return self._collections[index_name]

    def _meta_collection(self):
        return self.client.get_or_create_collection(self._META_COLLECTION, metadata={"hnsw:space": "cosine"})

    def _load_meta(self) -> None:
        got = self._meta_collection().get(ids=[self._META_DOC_ID], include=["documents"])
        docs = got.get("documents") or []
        if docs and docs[0]:
            blob = json.loads(docs[0])
            self._version = blob.get("index_version")
            self.lexicon = blob.get("lexicon", {})
            self._chunk_index = blob.get("chunk_index", {})

    def _write_meta(self) -> None:
        blob = json.dumps({
            "index_version": self._version,
            "lexicon": self.lexicon,
            "chunk_index": self._chunk_index,
        }, ensure_ascii=False)
        # The meta collection stores no real vectors (only `get`-by-id is ever used on it,
        # never `query`); Chroma still requires an embedding of the collection's configured
        # dimensionality on every upsert, so a zero vector is used as a harmless placeholder.
        self._meta_collection().upsert(ids=[self._META_DOC_ID], embeddings=[[0.0] * 384], documents=[blob])

    def upsert_index(self, index_name: str, documents: dict, chunks: list[ChunkRecord], embeddings: np.ndarray) -> None:
        if not chunks:
            return
        coll = self._collection(index_name)
        ids = [c.chunk_id for c in chunks]
        coll.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=[c.embed_text for c in chunks],
            metadatas=[_chunk_metadata(c) for c in chunks],
        )
        self._chunk_index.update({cid: index_name for cid in ids})

    def set_index_version(self, version: str) -> None:
        self._version = version
        self._write_meta()

    def set_lexicon(self, lexicon: dict[str, str]) -> None:
        self.lexicon = lexicon
        self._write_meta()

    def index_version(self) -> str:
        return self._version or "unversioned"

    def dense_search(self, index_name: str, query_vec: np.ndarray, top_k: int) -> list[tuple[str, float]]:
        coll = self._collection(index_name)
        n = coll.count()
        if n == 0:
            return []
        res = coll.query(query_embeddings=[query_vec.tolist()], n_results=min(top_k, n))
        ids = res["ids"][0]
        distances = res["distances"][0]
        return [(cid, 1.0 - dist) for cid, dist in zip(ids, distances)]

    def entity_search(self, index_name: str, query_vec: np.ndarray, entities: set[str], top_k: int) -> list[tuple[str, float]]:
        coll = self._collection(index_name)
        if coll.count() == 0:
            return []
        got = coll.get(include=["metadatas"])
        candidate_ids = [
            cid
            for cid, meta in zip(got["ids"], got["metadatas"])
            if entities & (set((meta.get("entities_csv") or "").split(",")) - {""})
        ]
        if not candidate_ids:
            return []
        sub = coll.get(ids=candidate_ids, include=["embeddings"])
        emb = np.asarray(sub["embeddings"], dtype=np.float32)
        sims = emb @ query_vec
        scored = list(zip(sub["ids"], sims.tolist()))
        scored.sort(key=lambda t: -t[1])
        return scored[:top_k]

    def get_chunk(self, chunk_id: str) -> Optional[ChunkRecord]:
        index_name = self._chunk_index.get(chunk_id)
        search_order = [index_name] + [n for n in INDEX_NAMES if n != index_name] if index_name else list(INDEX_NAMES)
        for name in search_order:
            got = self._collection(name).get(ids=[chunk_id], include=["metadatas"])
            if got["ids"]:
                return ChunkRecord(**json.loads(got["metadatas"][0]["record_json"]))
        return None

    def all_chunks(self, index_name: str) -> list[ChunkRecord]:
        got = self._collection(index_name).get(include=["metadatas"])
        return [ChunkRecord(**json.loads(m["record_json"])) for m in got["metadatas"]]

    def has_data(self) -> bool:
        return any(self._collection(name).count() > 0 for name in INDEX_NAMES)


def connect(settings=None) -> VectorStore:
    """Builds the store this process should use. Real deployments (`chromadb` installed):
    an `HttpClient` against `settings.chroma_host`/`chroma_port` when `chroma_host` is set
    (the Docker Compose topology -- `indexer` and `app` are separate containers sharing one
    `chroma` service, exactly how they share one `db` Postgres service today), otherwise a
    local `PersistentClient` under `settings.chroma_persist_dir` (single-process/dev use).
    This sandbox (`chromadb` not importable): `LocalNpyStore`, unconditionally -- see the
    module docstring."""
    if settings is None:
        from app.config import settings as _settings

        settings = _settings
    if not _HAVE_CHROMADB:
        return LocalNpyStore(settings.rag_sources_dir.parent / ".rag_index")
    if settings.chroma_host:  # pragma: no cover - needs chromadb, see module docstring
        client = _connect_chroma_with_retry(settings)
    else:  # pragma: no cover - needs chromadb, see module docstring
        settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))
    return ChromaStore(client)  # pragma: no cover - needs chromadb, see module docstring


def _connect_chroma_with_retry(settings):  # pragma: no cover - needs chromadb
    """Builds the `HttpClient` against the shared Chroma server, with bounded retries --
    not just until its container process has started, but until the server inside it is
    actually accepting connections. Retries the *construction itself*, not just a
    post-construction check: `chromadb.HttpClient(...)` is not the lazy call its name
    suggests -- as of the pinned 1.5.9 server/client, it eagerly calls `get_user_identity()`
    during `__init__`, which raises `ValueError` immediately (not some later operation) if
    nothing is listening yet. An earlier version of this function retried a separate
    `client.heartbeat()` call placed *after* construction, which looked reasonable but never
    actually ran on a cold server, because construction itself had already raised -- caught
    here directly, against a real Chroma 1.5.9 server, by deliberately connecting before it
    was ready (see `tests/test_chroma_store.py`'s `_FlakyHeartbeatClient`-based tests, which
    model the same race one level down, now that this function is what retries the real
    failure mode instead of one that didn't occur). Total wait is bounded by
    `settings.chroma_connect_retries * settings.chroma_connect_retry_wait` (default: 30 x 2s
    = 60s); on exhaustion the final connection exception is allowed to propagate, since at
    that point something is actually wrong, not just still starting up."""

    @retry(
        stop=stop_after_attempt(max(1, settings.chroma_connect_retries)),
        wait=wait_fixed(settings.chroma_connect_retry_wait),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _connect():
        client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        client.heartbeat()  # belt-and-suspenders: confirms the connection is actually live
        return client

    t0 = time.monotonic()
    try:
        client = _connect()
    except Exception:
        logger.error(
            "Chroma server at %s:%s did not become ready after %d attempt(s) (%.1fs)",
            settings.chroma_host,
            settings.chroma_port,
            settings.chroma_connect_retries,
            time.monotonic() - t0,
        )
        raise
    elapsed = time.monotonic() - t0
    if elapsed > 1.0:  # only worth a log line if we actually had to wait
        logger.info("Chroma server at %s:%s became ready after %.1fs", settings.chroma_host, settings.chroma_port, elapsed)
    return client
