# 12. ChromaDB Migration

RAG storage (`04_rag_design.md` section 5) moved from pgvector, in a `rag` schema of the PostgreSQL server,
to ChromaDB, a separate service. PostgreSQL now holds only business data. This is a direct instruction from
the project owner ("store all RAG data, embeddings, and vectors in ChromaDB instead of the current storage
system... keeping PostgreSQL for business data"), not a response to a defect in the pgvector design --
`01_requirements.md` assumption A-05 already named Chroma as its own stated alternative ("Alternative: Chroma
or FAISS on a Docker volume"), so this moves the system onto that alternative rather than against the
requirements document's own reasoning.

## 1. What Changed

| Area | Before | After |
|---|---|---|
| RAG vectors, chunks, documents, index metadata, entity lexicon | `rag.chunks`/`rag.documents`/`rag.index_runs` tables in PostgreSQL's `rag` schema, `vector(384)` column, HNSW index via pgvector | ChromaDB, one collection per index (`rag_router`, `rag_data_analysis`, `rag_inventory`, `rag_knowledge_base`) plus a `rag_meta` collection for the index version, lexicon, and a chunk-to-collection map -- see `app/rag/store.py`'s `ChromaStore` |
| Store interface | `VectorStore` (`PgvectorStore` was a structural placeholder, never completed -- see git history / the prior version of `app/rag/store.py`) | Same `VectorStore` interface (`dense_search`, `entity_search`, `get_chunk`, `index_version`, `all_chunks`, now also `set_lexicon`, `has_data`); `ChromaStore` is the real implementation, `LocalNpyStore` is the sandbox-only stand-in used when `chromadb` cannot be imported |
| Database roles | `bmp_readonly` (business data) + `bmp_rag_writer`/`bmp_rag_reader` (the `rag` schema) | `bmp_readonly` only. The two `bmp_rag_*` roles and `database/sql/06_rag_schema.sql`/`07_rag_roles.sql` are deleted. |
| Configuration | `DATABASE_URL_RAG`, `DATABASE_URL_RAG_READONLY` | `CHROMA_HOST`, `CHROMA_PORT`, `CHROMA_PERSIST_DIR` (`app/config.py`) |
| Docker Compose | `db` only (pgvector image) | `db` (plain `pgvector/pgvector:pg16` image still used, but now only for its Postgres server -- the extension is simply unused) + a new `chroma` service (`chromadb/chroma:0.5.15`), its own `chromadata` volume, `expose`d to the Compose network only |
| Dependencies | `pgvector>=0.3.6` (Python package) | `chromadb>=0.5.15` |
| Code touched | -- | `app/rag/store.py` (rewritten), `app/rag/indexer.py`, `app/tools/rag_tool.py`, `app/config.py`, `pyproject.toml`, `docker-compose.yml`, `.env.example`, `database/README.md`, `README.md` |
| Docs touched | -- | `04_rag_design.md` section 5 and its indexer-section mention, `05_security_and_guardrails.md` sections 2 (T-08), 13, 17, `11_deployment_guide.md` (throughout), this document |

`app/rag/pipeline.py` (the shared rewrite/expand/retrieve/fuse/re-rank/select pipeline) and every subgraph
that calls `rag_tool` needed **no changes at all** -- they were already written against the `VectorStore`
interface, not against pgvector directly, which is exactly the seam this migration confirms was designed
correctly the first time.

## 2. Why ChromaDB Still Cannot Be Tested Live Here, and What Stands In

Same limitation as every other Phase 3 dependency this sandbox lacks (`sentence-transformers`, `torch`,
`pglast`, `fastapi`, `chainlit`, `psycopg`'s real driver path, a reachable Docker daemon, network to Groq):
no PyPI network access at all (`pip install chromadb` fails to resolve `pypi.org`). `ChromaStore` is real,
complete production code written against the documented `chromadb` client/collection API, not a stub, with
`# pragma: no cover` markers only on the lines that construct a real client or collection. It is tested
against a small, faithful fake of that API in `tests/test_chroma_store.py` (17 checks: ranking, entity
filtering, cross-process meta persistence via a second `ChromaStore` on the same fake client, the
chunk-index fast path and its full-scan fallback, `connect()`'s own fallback selection) -- a genuine
substitute, not an equivalent, for an integration test against the real package. `connect()` falls back to
`LocalNpyStore` automatically whenever `chromadb` is not importable, so the indexer, `rag_tool`, and every
existing RAG-pipeline test (`test_rag_pipeline.py`, `test_knowledge_base_subgraph.py`,
`test_data_analysis_subgraph.py`, `test_inventory_subgraph.py`, `test_top_level_graph.py`,
`test_api_core.py`, `test_evaluation_harness.py`, the evaluation harness itself) kept running, unmodified,
through that fallback with no code changes of their own needed -- confirmed by re-running the full suite
after this migration (see the test run recorded alongside this delivery).

## 3. Security Trade-off: Chroma Has No Postgres-Style Role/Grant System

Worth calling out on its own, not just as a residual-risk table row (also recorded in
`05_security_and_guardrails.md` sections 13 and 17): the pgvector design's `bmp_rag_writer`/`bmp_rag_reader`
split gave the indexer-writes/application-reads boundary a hard, server-enforced guarantee via
Postgres `REVOKE`/`GRANT`. The open-source Chroma server has no equivalent fine-grained ACL -- any client
that can reach it can read and write every collection. The compensating controls adopted here are network
isolation (the `chroma` service is never published beyond the Compose network, exactly like `db`) and an
application-level discipline that the query-serving code path (`app/rag/pipeline.py`, `app/tools/rag_tool.py`)
never calls a write method on the store, checked statically by `tests/test_rag_readonly_serving_path.py`.
This is a real, accepted regression in defense-in-depth for the RAG side specifically -- it was not silently
absorbed. A deployment that needs a hard boundary here should put Chroma's own token-based server auth in
front of separate indexer/application client identities, or run two Chroma instances.

## 4. Not Touched, and Why

- **`docs/01_requirements.md` assumption A-05** still reads "Approve" next to the pgvector choice. It already
  names Chroma as its own stated alternative, so this migration is not a reversal of that assumption's
  reasoning, but the row itself is now stale against what the system actually runs. `01_requirements.md`,
  `02_architecture.md`, `03_database_design.md` and `08_phase_plan.md` are not modified without being asked
  (standing instruction); `02_architecture.md`'s diagram (`PG --- RAG[rag schema: vectors and chunks]`) and
  its "Containers" line ("`db` (PostgreSQL with pgvector)") are similarly now stale. Happy to update either
  if asked.
- **`rag_sources/` content** (the Phase 1 knowledge-base corpus itself) is left exactly as delivered, per the
  project's established boundary for that corpus (`09_phase2_completion_report.md` section 2 declined to
  "fix" a Phase 1 example for the same reason). Four files (`rag_sources/router/05_routing_rules.md`,
  `rag_sources/inventory/01_inventory_sql_extraction_rules.md` and `10_inventory_edge_cases.md`,
  `rag_sources/data_analysis/01_sql_extraction_guidelines.md`) contain the line "The `rag` schema is not
  accessible," written as a warning against querying the old Postgres `rag` schema with business SQL. It
  remains trivially true (there is now no `rag` schema in Postgres at all to access) but is stale phrasing
  that no longer names where RAG data actually lives. Not changed without being asked, for the same reason
  as the three protected docs above.
- **`03_database_design.md`** never documented the `rag` schema in the first place (it was specified only in
  `04_rag_design.md` and implemented only in `database/sql/06_rag_schema.sql`), so nothing in it needed to
  change either way.

## 5. Status

Done: store rewrite, indexer/rag_tool wiring, config, Docker Compose, dependencies, the SQL role files
removed, `.env.example`/`README.md`/`database/README.md` updated, `04_rag_design.md`/
`05_security_and_guardrails.md`/`11_deployment_guide.md` updated, `tests/test_chroma_store.py` and
`tests/test_rag_readonly_serving_path.py` added, `tests/test_db_role_permissions.py` and
`tests/test_secret_and_dependency_scan.py` updated to drop the now-moot Postgres-`rag`-schema checks, and
the full test suite re-run clean (see the run recorded alongside this delivery).
