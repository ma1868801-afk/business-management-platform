"""Unit tests for `app.rag.store.ChromaStore` (the production RAG backend as of
`docs/12_chromadb_migration.md`).

`chromadb` cannot be installed in this sandbox (no PyPI network access -- the same
limitation every other Phase 3 module documents). `ChromaStore` is nonetheless real,
complete production code written against the real `chromadb` client/collection API
(`get_or_create_collection`, `.upsert`, `.get`, `.query`, `.count`), not a stub -- so this
file tests it against a small, faithful fake of that API (`_FakeClient`/`_FakeCollection`
below) rather than skipping it entirely. The fake implements only the calls `ChromaStore`
actually makes, with the same call signatures, return shapes, and cosine-space distance
semantics (`hnsw:space: cosine` -> distance = 1 - cosine_similarity) as the real client
documents. It is not a mock that assumes success: `query()`/`get()` compute real
similarity/filtering over whatever was actually `upsert`ed, the same way the real server
would. This is a genuine substitute for an integration test against the real package, not
equivalent to one -- a deployment with network access should additionally run this suite's
logic against a real `chromadb` server/PersistentClient at least once.

Run directly: python3 tests/test_chroma_store.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import app.rag.store as store_mod  # noqa: E402
from app.rag.chunker import ChunkRecord  # noqa: E402
from app.rag.store import ChromaStore, LocalNpyStore, connect  # noqa: E402

FAILURES = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    status = "OK" if cond else "FAIL"
    if not cond:
        FAILURES += 1
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))


# --- a small, faithful fake of the real chromadb client/collection API -----------------

def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return 1.0 - float(a @ b) / denom


class _FakeCollection:
    def __init__(self, name: str):
        self.name = name
        self._ids: list[str] = []
        self._embeddings: dict[str, list[float]] = {}
        self._documents: dict[str, str] = {}
        self._metadatas: dict[str, dict] = {}

    def upsert(self, ids, embeddings, documents=None, metadatas=None) -> None:
        documents = documents or [None] * len(ids)
        metadatas = metadatas or [{}] * len(ids)
        for i, cid in enumerate(ids):
            if cid not in self._ids:
                self._ids.append(cid)
            self._embeddings[cid] = embeddings[i]
            self._documents[cid] = documents[i]
            self._metadatas[cid] = metadatas[i]

    def count(self) -> int:
        return len(self._ids)

    def get(self, ids=None, include=None):
        include = include or []
        target_ids = ids if ids is not None else list(self._ids)
        target_ids = [i for i in target_ids if i in self._ids]  # real chroma silently drops unknown ids
        out = {"ids": target_ids}
        if "embeddings" in include:
            out["embeddings"] = [self._embeddings[i] for i in target_ids]
        if "documents" in include:
            out["documents"] = [self._documents[i] for i in target_ids]
        if "metadatas" in include:
            out["metadatas"] = [self._metadatas[i] for i in target_ids]
        return out

    def query(self, query_embeddings, n_results):
        qvec = np.asarray(query_embeddings[0], dtype=np.float32)
        scored = [
            (cid, _cosine_distance(qvec, np.asarray(self._embeddings[cid], dtype=np.float32)))
            for cid in self._ids
        ]
        scored.sort(key=lambda t: t[1])  # smaller distance = closer
        top = scored[:n_results]
        return {"ids": [[cid for cid, _ in top]], "distances": [[d for _, d in top]]}


class _FakeClient:
    def __init__(self):
        self._collections: dict[str, _FakeCollection] = {}

    def get_or_create_collection(self, name, metadata=None):
        if name not in self._collections:
            self._collections[name] = _FakeCollection(name)
        return self._collections[name]


class _FlakyHeartbeatClient:
    def heartbeat(self):
        return 123456789


class _FlakyHttpClientFactory:
    """Simulates the real Chroma startup race reproduced in RAG_REFACTOR_REPORT.md section
    8: `chromadb.HttpClient(...)`'s *constructor* raises (not some later call) for the first
    `fail_times` attempts, as if the container were running but the server inside it weren't
    accepting connections yet, then succeeds -- a stand-in for `chromadb.HttpClient` itself,
    patched into `app.rag.store.chromadb.HttpClient` for the duration of one test."""

    def __init__(self, fail_times: int):
        self.fail_times = fail_times
        self.calls = 0

    def __call__(self, host=None, port=None):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ValueError("simulated: Could not connect to a Chroma server. Are you sure it is running?")
        return _FlakyHeartbeatClient()


class _AlwaysFailHttpClientFactory:
    def __init__(self):
        self.calls = 0

    def __call__(self, host=None, port=None):
        self.calls += 1
        raise ValueError("simulated: chroma server never comes up")


class _RetrySettings:
    """Minimal settings stand-in for `_wait_for_chroma_ready`, which only reads these four
    fields -- real retries would make this test slow, so wait is kept tiny."""

    chroma_host = "chroma"
    chroma_port = 8000
    chroma_connect_retries = 5
    chroma_connect_retry_wait = 0.01


def _record(chunk_id, index_name, doc_id, entities, vec_seed) -> tuple[ChunkRecord, np.ndarray]:
    rec = ChunkRecord(
        chunk_id=chunk_id, doc_id=doc_id, index_name=index_name, title=f"title-{doc_id}",
        source_path=f"{doc_id}.md", chunk_no=1, section_path="Section", kind="text",
        body=f"body of {chunk_id}", embed_text=f"body of {chunk_id}", token_estimate=5,
        content_hash="h", entities=entities,
    )
    vec = np.zeros(384, dtype=np.float32)
    vec[vec_seed % 384] = 1.0
    return rec, vec


def main() -> int:
    # ChromaStore.__init__ checks the real import guard; flip it for this test (restored
    # after) since the real `chromadb` module cannot be imported here -- see module docstring.
    store_mod._HAVE_CHROMADB = True
    try:
        client = _FakeClient()
        store = ChromaStore(client)

        r1, v1 = _record("router::1", "router", "RT-01", ["ELEC-0001"], 0)
        r2, v2 = _record("router::2", "router", "RT-01", ["APPL-0002"], 1)
        r3, v3 = _record("router::3", "router", "RT-02", ["ELEC-0001", "APPL-0002"], 2)
        store.upsert_index("router", {}, [r1, r2, r3], np.stack([v1, v2, v3]))

        r4, v4 = _record("inv::1", "inventory", "INV-01", ["ELEC-0001"], 10)
        store.upsert_index("inventory", {}, [r4], np.stack([v4]))

        check("has_data is true once something was upserted", store.has_data())

        # --- dense_search: the closest stored vector (v1, identical direction) should rank first ---
        results = store.dense_search("router", v1, top_k=3)
        check("dense_search returns all 3 router chunks", len(results) == 3, results)
        check("dense_search ranks the identical vector first with similarity 1.0",
              results[0][0] == "router::1" and abs(results[0][1] - 1.0) < 1e-6, results)
        check("dense_search's orthogonal vectors score ~0 similarity to v1",
              all(abs(s) < 1e-6 for cid, s in results[1:]), results)

        # --- dense_search only searches the named index's collection, not other indexes ---
        inv_results = store.dense_search("inventory", v1, top_k=5)
        check("dense_search on 'inventory' never returns a 'router' chunk_id",
              all(cid.startswith("inv::") for cid, _ in inv_results), inv_results)

        # --- entity_search: filters to chunks whose entities intersect the query set ---
        hits = store.entity_search("router", v3, entities={"APPL-0002"}, top_k=5)
        hit_ids = {cid for cid, _ in hits}
        check("entity_search('APPL-0002') finds both chunks tagged with it, not the unrelated one",
              hit_ids == {"router::2", "router::3"}, hit_ids)

        empty_hits = store.entity_search("router", v1, entities={"NOPE-9999"}, top_k=5)
        check("entity_search with no matching entity returns nothing", empty_hits == [])

        # --- get_chunk: exact round-trip of every field, via the chunk_index fast path ---
        got = store.get_chunk("router::3")
        check("get_chunk reconstructs the exact ChunkRecord (fast path via chunk_index)",
              got == r3, got)

        # --- get_chunk still works by full scan if the chunk_index map is missing (e.g. data
        # written by an older process whose meta blob predates the map) ---
        store._chunk_index.clear()
        got2 = store.get_chunk("inv::1")
        check("get_chunk falls back to scanning every collection when chunk_index is empty",
              got2 == r4, got2)
        store._chunk_index["router::1"] = "router"  # restore for the rest of the test

        check("get_chunk returns None for an unknown id", store.get_chunk("nope") is None)

        # --- all_chunks (used by the pipeline's TF-IDF rerank fallback) ---
        all_router = store.all_chunks("router")
        check("all_chunks('router') returns exactly the 3 upserted router chunks",
              {c.chunk_id for c in all_router} == {"router::1", "router::2", "router::3"}, all_router)

        # --- index_version / lexicon persist in the rag_meta collection, not just in memory ---
        store.set_index_version("abc12345")
        store.set_lexicon({"ELEC-0001": "Electronics", "APPL-0002": "Appliances"})
        check("index_version reflects what was just set", store.index_version() == "abc12345")

        # A second ChromaStore wrapping the SAME client simulates a different process (e.g.
        # the `app` container) reconnecting to the same Chroma server the `indexer` wrote to.
        reconnected = ChromaStore(client)
        check("a second ChromaStore on the same client sees the persisted index_version",
              reconnected.index_version() == "abc12345", reconnected.index_version())
        check("a second ChromaStore on the same client sees the persisted lexicon",
              reconnected.lexicon == {"ELEC-0001": "Electronics", "APPL-0002": "Appliances"},
              reconnected.lexicon)
        check("a second ChromaStore on the same client can still read the upserted chunks",
              reconnected.get_chunk("router::2") == r2)

        # --- upsert_index with an empty chunk list is a safe no-op ---
        before = store.all_chunks("router")
        store.upsert_index("router", {}, [], np.zeros((0, 384), dtype=np.float32))
        check("upserting an empty chunk list changes nothing",
              store.all_chunks("router") == before)
    finally:
        store_mod._HAVE_CHROMADB = False

    # --- connect(): in THIS sandbox (chromadb genuinely not importable), the factory must
    # fall back to LocalNpyStore, never silently construct a broken ChromaStore ---
    class _Settings:
        chroma_host = ""
        chroma_port = 8000

        def __init__(self, tmp):
            self.rag_sources_dir = tmp / "rag_sources"
            self.chroma_persist_dir = tmp / ".chroma"

    import tempfile

    with tempfile.TemporaryDirectory() as d:
        s = connect(_Settings(Path(d)))
        check("connect() falls back to LocalNpyStore when chromadb is not installed",
              isinstance(s, LocalNpyStore), type(s))

    # _connect_chroma_with_retry: the Chroma startup-race fix (RAG_REFACTOR_REPORT.md
    # section 8). Patches `chromadb.HttpClient` itself, not something "after" it -- the real
    # race this reproduces is the *constructor* raising on a cold server, not a later call.
    from app.rag.store import _connect_chroma_with_retry

    # `store_mod.chromadb` only exists as a name at all when the real package was
    # importable (see the module's own `try: import chromadb / except ImportError`) --
    # which this suite deliberately doesn't require (see `connect() falls back to
    # LocalNpyStore...` just above). Inject a stand-in with just the one attribute this
    # function uses either way, and remove it afterwards rather than "restoring" something
    # that was never there.
    _had_chromadb_attr = hasattr(store_mod, "chromadb")
    _orig_http_client = store_mod.chromadb.HttpClient if _had_chromadb_attr else None
    if not _had_chromadb_attr:
        store_mod.chromadb = types.SimpleNamespace()
    try:
        flaky_factory = _FlakyHttpClientFactory(fail_times=3)
        store_mod.chromadb.HttpClient = flaky_factory
        _connect_chroma_with_retry(_RetrySettings())
        check("recovers once the server starts accepting connections", flaky_factory.calls == 4, str(flaky_factory.calls))

        always_fail_factory = _AlwaysFailHttpClientFactory()
        store_mod.chromadb.HttpClient = always_fail_factory
        try:
            _connect_chroma_with_retry(_RetrySettings())
            check("raises once retries are exhausted if the server never comes up", False)
        except ValueError:
            check("raises once retries are exhausted if the server never comes up", True)
        check("made exactly chroma_connect_retries attempts, not more", always_fail_factory.calls == 5, str(always_fail_factory.calls))
    finally:
        if _had_chromadb_attr:
            store_mod.chromadb.HttpClient = _orig_http_client
        else:
            del store_mod.chromadb

    print(f"\n{FAILURES} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
