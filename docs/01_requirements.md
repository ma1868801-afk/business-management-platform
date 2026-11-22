# 01. Requirements and Assumptions

This document restates the approved "Project Requirements & Architecture Document" as numbered requirements, maps every Phase 1 requirement to the files that satisfy it, and lists the assumptions that were made where the approved document is silent or ambiguous. Assumptions need confirmation before Phase 2 starts.

## 1. Project Summary

- **Project name:** Business Management Platform.
- **Objective (Goal 8):** an intelligent assistant for business analytics, forecasting and company knowledge base retrieval.
- **Core capabilities:** data analysis, knowledge base retrieval (RAG), inventory monitoring and forecasting, read-only SQL query execution.

## 2. Technology Stack (Approved)

| Area | Approved choice |
|---|---|
| Orchestration | LangGraph (multi-agent architecture, subgraph routing) |
| Backend | FastAPI |
| Database | PostgreSQL |
| RAG engine | Advanced RAG for company documents and knowledge bases |
| User interface | Chainlit |
| Containerization | Docker |
| Security | Prompt injection prevention, input validation, guardrails |
| Environment and packages | uv |
| Embedding model | all-MiniLM-L6-v2 |
| Core LLM | "gpt-oss-1200" served on Groq (see assumption A-01) |

## 3. Numbered Requirements

### 3.1 Data and Files

- **R-01** All datasets are comprehensive and fully prepared for all testing scenarios.
- **R-02** "Create a file" means generating a Markdown file.
- **R-03** All Markdown files are written in English because the embedding model processes English text only. All data formats are English.
- **R-04** Company Knowledge Base files match the structure of the documents provided by the user.
- **R-05** SQL executed by the system is strictly read-only.

### 3.2 Database (PostgreSQL)

- **R-06** Schemas and data for Sales, Customers and Inventory.
- **R-07** Historical data spans continuously from 2024 through October 2026.
- **R-08** Rich attributes (season, branch, timestamp and similar) on all entities.

### 3.3 RAG Pipeline

- **R-09** Every RAG module implements (A) query rewriting, (B) query expansion and (C) re-ranking.
- **R-10** A top-level Router RAG holds metadata descriptions of the three subgraphs.

### 3.4 Subgraphs

- **R-11 Data Analysis:** dedicated RAG (SQL extraction guidelines, Pandas execution instructions, domain analysis knowledge); Pandas for computation; hypothesis testing only when requested; Pandas bypass for raw extraction.
- **R-12 Inventory:** dedicated RAG (SQL extraction rules, regression input guidelines, inventory domain knowledge); regression forecasting upon request; regression bypass for current quantities.
- **R-13 Knowledge Base:** all official company documents and context; answers retrieved via RAG.

### 3.5 Evaluation

- **R-14** Evaluation suites cover all edge cases and scenarios of all subgraphs.
- **R-15** Benchmarks are mixed language: part English, part Arabic.
- **R-16** At least 200 scenarios.

### 3.6 Data Flow

- **R-17** The primary LLM receives the question, translates Arabic into English, and calls the Router RAG through a tool call.
- **R-18** The routed subgraph LLM queries its RAG, uses the PostgreSQL tool, then the Pandas tool or Regression Model when needed, and formats a node response.
- **R-19** The Knowledge Base subgraph interprets the query, extracts passages from the company RAG documents and formats a node response.
- **R-20** A final aggregator LLM merges node responses and translates the answer to Arabic if the user wrote in Arabic.

### 3.7 Execution Phases

- **Phase 1:** all Markdown documentation and RAG source files (this deliverable).
- **Phase 2:** the PostgreSQL schema and dataset as a .sql file. Starts only on explicit instruction.
- **Phase 3:** system architecture and full codebase. Starts only on explicit instruction after Phase 2.

## 4. Phase 1 Traceability

| Requirement | Satisfied by |
|---|---|
| R-01, R-07, R-08 | `03_database_design.md` (schema, volumes, seeded patterns that guarantee every evaluation scenario can be answered) |
| R-02, R-03 | All deliverables are Markdown in English. The only Arabic text is in evaluation prompt fields (assumption A-08) |
| R-04 | `rag_sources/knowledge_base/` (company, contracts, employees, products, same layout and section style as the provided sample) |
| R-05 | `05_security_and_guardrails.md`, `rag_sources/data_analysis/01_sql_extraction_guidelines.md`, `rag_sources/inventory/01_inventory_sql_extraction_rules.md` |
| R-06 | `03_database_design.md`, both `02_schema_reference.md` files |
| R-09, R-10 | `04_rag_design.md`, `rag_sources/router/` |
| R-11 | `rag_sources/data_analysis/` (11 files) |
| R-12 | `rag_sources/inventory/` (10 files) |
| R-13 | `rag_sources/knowledge_base/` (77 files) |
| R-14, R-15, R-16 | `evaluation/` and `06_evaluation_plan.md` |
| R-17 to R-20 | `02_architecture.md` |

## 5. Assumptions and Open Items

| ID | Assumption | Why | Action needed |
|---|---|---|---|
| A-01 | The model name "gpt-oss-1200" is a typo for `openai/gpt-oss-120b` on Groq. | Groq serves gpt-oss-120b and gpt-oss-20b; no 1200 model exists. | Confirm before Phase 3. The model id is a single environment variable. |
| A-02 | The business is a fictional Saudi multi-category retailer, Nakhla Retail Group (nine locations, 120 SKUs, eight product lines). | The approved document defines no business domain. The sample knowledge base provided belongs to a different fictional company, so only its structure is reused. | Confirm or provide a different domain. |
| A-03 | The data reference date ("today" for analysis) is 2026-10-31, the last day of data. | Makes every relative date ("last month") deterministic and testable. | Confirm. The system must never use the real clock for analysis. |
| A-04 | Re-ranking uses a small cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`). | Approved stack names only the embedding model and the core LLM. A cross-encoder is the standard low-cost re-ranker. Fallback: LLM-based re-ranking with the core LLM. | Approve the extra model or choose the fallback. |
| A-05 | The vector store is pgvector in a separate `rag` schema of the same PostgreSQL server. | Avoids an extra service; the read-only SQL role has no access to the `rag` schema. Alternative: Chroma or FAISS on a Docker volume. | Approve. |
| A-06 | Forecasting uses scikit-learn regression (Ridge on log1p units, gradient boosting) with a seasonal-naive baseline. | Meets "regression models for demand forecasting" with small, explainable models. | Approve. |
| A-07 | Hypothesis tests use `scipy.stats`. | Standard library for Welch t-test, Mann-Whitney U, chi-square, ANOVA and correlation tests. | None. |
| A-08 | Evaluation prompts contain Arabic text; every other file is English. | The requirement demands Arabic benchmark prompts. Arabic appears only in the prompt field of an evaluation scenario, with an English translation next to it. | None. |
| A-09 | Employee HR records (including salaries) are part of the knowledge base, with a data privacy document describing role-based access. | The provided sample knowledge base includes employee records with compensation. All persons are fictional. | Confirm whether salaries should stay in the retrieval corpus. |
| A-10 | Customer email and phone exist in the database but are blocked by column-level grants. | Realistic schema; protects PII; tests the guardrail. | None. |
| A-11 | Arabic answers keep Western digits (0-9) and keep entity names (branches, SKUs, suppliers, people) in English. | Matches Saudi business reporting practice and keeps identifiers searchable. | Confirm the digit style. |
| A-12 | Language detection and translation are done by the primary LLM, with no separate translation model. | Matches the approved flow. | None. |
| A-13 | Time zone is Asia/Riyadh (UTC+3); timestamps are stored as local time without zone; currency is SAR; VAT is 15 percent and revenue excludes VAT. | Saudi context. | None. |
| A-14 | Ramadan, Eid and Hajj dates before November 2026 are fixed facts in the calendar table; dates after that are planning estimates. | Islamic calendar dates depend on moon sighting. | None. |
| A-15 | The forecast horizon is limited to 13 weeks and the first forecast week starts on 2026-11-01. | Weekly history ends on Saturday 2026-10-31. Longer horizons are unreliable with under three years of history. | None. |

## 6. Out of Scope

- Any write operation on business data (insert, update, delete, DDL) by the assistant.
- Real customer data. All people, companies and figures are fictional.
- Automatic creation of purchase orders or price changes.
- Authentication and multi-user permission management beyond the guardrails described in the security document.
