"""Checks the RAG-storage access-control trade-off `docs/12_chromadb_migration.md` and
`05_security_and_guardrails.md` sections 13/17 document: ChromaDB has no Postgres-style
per-role grant system, so the indexer-writes/application-reads split that pgvector's
`bmp_rag_writer`/`bmp_rag_reader` roles used to enforce at the database layer is now enforced
only by (1) network isolation (the `chroma` service is never published beyond the Compose
network, same as `db`) and (2) the serving code path simply never calling a write method on
the store. This file is the automated check for (2) -- a code-review-level control, not a
datastore-enforced one, which is exactly why it is worth a dedicated, explicit test rather
than being left as an informal convention.

It is a static (AST-based, not regex) scan: every "serving path" module -- the shared query
pipeline, the retrieval tool, the subgraphs that call it, the top-level graph, and the API
layer -- must contain no call to `VectorStore.upsert_index`/`set_index_version`/`set_lexicon`
(the only three write methods the interface exposes; see `app/rag/store.py`). Only
`app/rag/indexer.py` (the one-off build job) and `app/rag/store.py` (the interface/
implementations themselves) may call or define them.

Needs nothing but the standard library. Run directly: python3 tests/test_rag_readonly_serving_path.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FAILURES = 0

_WRITE_METHODS = {"upsert_index", "set_index_version", "set_lexicon"}

# Every module that is part of the request-serving path: it runs while answering a user's
# question, as opposed to the offline indexer job. A new subgraph or tool added to this path
# later should be added here too.
_SERVING_PATH_FILES = [
    "app/rag/pipeline.py",
    "app/tools/rag_tool.py",
    "app/graph/router.py",
    "app/graph/knowledge_base.py",
    "app/graph/data_analysis.py",
    "app/graph/inventory.py",
    "app/graph/top_level.py",
    "app/api_core.py",
    "app/main.py",
    "ui/chainlit_app.py",
]

# Files allowed to call/define the write methods: the offline build job, and the interface/
# implementations themselves (a method definition's own `def upsert_index(self, ...):` line
# is not a call and is fine wherever it is -- this scan only flags *calls*, via ast.Call).
_ALLOWED_CALLERS = {"app/rag/indexer.py"}


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    status = "OK" if cond else "FAIL"
    if not cond:
        FAILURES += 1
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))


def find_write_calls(path: Path) -> list[str]:
    """Returns the write-method names actually *called* (not merely defined) in `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _WRITE_METHODS:
                found.append(node.func.attr)
    return found


def main() -> int:
    for rel in _SERVING_PATH_FILES:
        path = ROOT / rel
        if not path.exists():
            check(f"{rel} exists (serving-path file list is up to date)", False)
            continue
        calls = find_write_calls(path)
        check(f"{rel} calls no RAG store write method", not calls, f"found: {calls}")

    # Sanity check the scan itself is wired correctly: the real indexer file DOES call all
    # three write methods (if this ever stops being true, the scan's own premise -- "only the
    # indexer writes" -- needs re-checking, not silently passing).
    indexer_calls = set(find_write_calls(ROOT / "app/rag/indexer.py"))
    check(
        "app/rag/indexer.py (the one allowed caller) actually calls all three write methods",
        indexer_calls == _WRITE_METHODS,
        f"found: {indexer_calls}",
    )

    # And that nothing outside the allowed caller + the interface file defines/calls them in
    # a way this scan's file list missed -- a repo-wide grep as a backstop against a new file
    # being added to the serving path without also being added to _SERVING_PATH_FILES above.
    all_py = list((ROOT / "app").rglob("*.py")) + list((ROOT / "ui").rglob("*.py"))
    unexpected = []
    for path in all_py:
        rel = str(path.relative_to(ROOT))
        if rel in _ALLOWED_CALLERS or rel == "app/rag/store.py":
            continue
        if find_write_calls(path):
            unexpected.append(rel)
    check(
        "no file outside app/rag/indexer.py calls a RAG store write method, repo-wide",
        not unexpected,
        f"unexpected callers: {unexpected}",
    )

    print(f"\n{FAILURES} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
