# 08. Phase Plan and Open Decisions

The approved execution directive is: start strictly with Phase 1 and proceed to Phase 2 only upon explicit instruction. This document records what Phase 1 delivered, what Phase 2 and Phase 3 will contain, and the decisions that need confirmation first. Nothing from Phase 2 or Phase 3 has been started.

## 1. Phase 1 (Delivered): Documentation and RAG Sources

| Deliverable | Location | Count |
|---|---|---|
| Project overview | `README.md` | 1 |
| Design documents | `docs/` (01_requirements.md to 08_phase_plan.md) | 8 |
| Router RAG sources | `rag_sources/router/` | 7 |
| Data Analysis RAG sources | `rag_sources/data_analysis/` | 11 |
| Inventory RAG sources | `rag_sources/inventory/` | 10 |
| Knowledge base documents | `rag_sources/knowledge_base/` | 77 |
| Evaluation scenarios | `evaluation/` | 220 scenarios in 6 files plus an index |

Quality checks performed on the Phase 1 sources:
- Every SQL example (51) was parsed and planned by PostgreSQL 16 against an empty database built from the schema specification, so each query is syntactically valid and uses existing tables and columns.
- Every Python example (23) was executed against synthetic data that has the declared columns.
- All Markdown is English; Arabic appears only in the prompt field of evaluation scenarios.
- Facts that appear in several documents (suppliers, contract numbers, branch managers, policy parameters, season windows) were generated from one registry.

## 2. Phase 2 (Not Started): PostgreSQL Schema and Dataset

Start condition: explicit instruction from the project owner after approving the assumptions in `01_requirements.md`.

| Step | Output |
|---|---|
| 1. Schema script | Tables, constraints, views, indexes, roles and grants exactly as in `03_database_design.md` |
| 2. Generator | A seeded Python generator that reads the reference registry and produces all rows in dependency order |
| 3. Dataset script | One `.sql` file (or numbered parts) with the schema and `COPY` data blocks, for local setup |
| 4. Verification | A read-only SQL script that checks guarantees G-01 to G-38 and prints measured values |
| 5. Load guide | A short Markdown guide: prerequisites, load command, expected duration, how to verify |

Expected size: about 120,000 orders, 300,000 order lines, 6,000 customers, 120 SKUs, 120,000 weekly stock snapshots. The uncompressed script is expected to be in the range of 50 to 100 MB; a compressed copy can be provided.

Acceptance: the script loads into an empty PostgreSQL 16 database without errors, all guarantees pass, and the 51 SQL examples in the RAG sources return non-empty, plausible results where data is expected.

## 3. Phase 3 (Not Started): System Implementation

Start condition: explicit instruction after Phase 2 is accepted.

| Milestone | Content |
|---|---|
| M1 Foundation | uv project, Docker Compose (app, ui, db), configuration, PostgreSQL with pgvector, database roles |
| M2 RAG core | Ingestion and chunking, embeddings with all-MiniLM-L6-v2, retrieval, query rewriting, expansion, re-ranking, index build from `rag_sources/` |
| M3 Tools | SQL validator and tool, Pandas sandbox, regression tool, RAG tool |
| M4 Subgraphs | Knowledge Base, Data Analysis and Inventory subgraphs with retry and bypass logic |
| M5 Top-level graph | Input guard, translation, router, aggregator, back-translation, output guard |
| M6 Interface | FastAPI endpoints and Chainlit chat with streaming and source display |
| M7 Evaluation | Harness, reference queries, judges, reports; tuning until the targets in `06_evaluation_plan.md` are met |
| M8 Hardening | Security tests, performance, documentation, deployment guide |

## 4. Decisions Needed Before Phase 2

| ID | Decision | Default if not answered |
|---|---|---|
| D-1 | Confirm the model: `openai/gpt-oss-120b` on Groq (the document says "gpt-oss-1200") | Use `openai/gpt-oss-120b` |
| D-2 | Confirm the fictional company and domain (Nakhla Retail Group, Saudi multi-category retail) | Keep as delivered |
| D-3 | Approve the cross-encoder re-ranker `ms-marco-MiniLM-L-6-v2` or choose LLM re-ranking | Use the cross-encoder |
| D-4 | Approve pgvector inside the same PostgreSQL server | Use pgvector |
| D-5 | Confirm that employee salaries stay in the knowledge base with the privacy rule (named employee only, no bulk lists) | Keep as delivered |
| D-6 | Confirm Arabic answers keep Western digits and English entity names | Keep as delivered |
| D-7 | Confirm the reference date 2026-10-31 for all analysis | Keep as delivered |

## 5. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Embedding model truncation at 256 word pieces | Short, self-contained sections; descriptive text embedded for code chunks |
| Hallucinated numbers | Tools compute all numbers; output guard checks grounding |
| Unsafe SQL | Validator plus read-only role plus read-only transaction |
| Weak forecasts for new or censored series | Cold-start method, stockout adjustment, confidence labels, baseline comparison |
| Ambiguity in Arabic questions (dialect, transliteration) | Normalization, entity mapping tables in the Router RAG, language scenarios in the suite |
| Dataset and documents drifting apart | One registry; guarantees G-01 to G-38 verified after generation |
