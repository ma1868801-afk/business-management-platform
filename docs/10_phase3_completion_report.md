# 10. Phase 3 Completion Report

Phase 3 (system implementation) is delivered through all eight milestones of `08_phase_plan.md` section 3:
M1 Foundation, M2 RAG core, M3 Tools, M4 Subgraphs, M5 Top-level graph, M6 Interface, M7 Evaluation, M8
Hardening. This report records what was built, what was verified and how, every sandbox limitation that
forced an honest degradation rather than a silent shortcut, and the real bugs this build's own tests found
and fixed. It does not repeat `09_phase2_completion_report.md` (Phase 2, already delivered beforehand).

## 1. What Was Built

| Milestone | Delivered as | Key files |
|---|---|---|
| M1 Foundation | uv project, Docker Compose (db/db-init/indexer/app/ui), configuration, pgvector schema, roles | `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `app/config.py`, `database/sql/06_rag_schema.sql`, `database/sql/07_rag_roles.sql` |
| M2 RAG core | Ingestion/chunking, embeddings, retrieval, query rewriting/expansion, re-ranking, passage screen, index build | `app/rag/` (`chunker.py`, `embeddings.py`, `indexer.py`, `retrieval.py`, `reranker.py`, `entities.py`), `app/guards/passage_screen.py` |
| M3 Tools | SQL validator and tool, Pandas sandbox, regression tool, RAG tool | `app/guards/sql_parser.py`, `sql_validator.py`, `pandas_validator.py`; `app/tools/postgres_tool.py`, `pandas_tool.py`, `_pandas_worker.py`, `regression_tool.py`, `rag_tool.py` |
| M4 Subgraphs | Knowledge Base, Data Analysis, Inventory, with retry/bypass logic | `app/graph/knowledge_base.py`, `data_analysis.py`, `inventory.py`, `citation_check.py` |
| M5 Top-level graph | Input guard, translation, router, aggregator, back-translation, output guard | `app/guards/input_guard.py`, `output_guard.py`, `injection_patterns.py`; `app/graph/router.py`, `aggregator.py`, `translate.py`, `top_level.py` |
| M6 Interface | FastAPI endpoints, Chainlit chat, session/rate/concurrency/timeout handling | `app/main.py`, `app/api_core.py`, `app/sessions.py`, `ui/chainlit_app.py` |
| M7 Evaluation | Harness, scenario loader/self-check, grader, oracle store, report writer | `tests/evaluation/` (`scenario_loader.py`, `grader.py`, `oracles.py`/`oracles.yaml`, `report.py`, `run_evaluation.py`) |
| M8 Hardening | Security test suite (section 16's own rows), performance measurements, this report, the deployment guide | `tests/test_sql_red_team.py`, `test_db_role_permissions.py`, `test_pandas_sandbox_isolation.py`, `test_injection_corpus.py`, `test_rate_and_size_limits.py`, `test_secret_and_dependency_scan.py`, `test_performance_m8.py`, `11_deployment_guide.md` |

22 `tests/test_*.py` files (2,946 lines) cover this build; `app/` is 6,756 lines, `ui/chainlit_app.py` 91.
Every test file is a standalone script (`python3 tests/test_X.py`), runnable without pytest, so the same
command works in CI, in a container, or by hand.

## 2. Sandbox Limitations, Honestly Degraded Throughout

This sandbox has no PyPI/npm network access beyond what was pre-installed, no reachable Docker daemon, and
no network path to the Groq API. Every place this mattered got a real `try/except ImportError` (or
equivalent) with a documented, working fallback — never a silent approximation of what the real dependency
would do:

| Missing | Where it matters | What stands in for it here |
|---|---|---|
| `langgraph`, `groq` (real client) | The multi-agent graph itself | Hand-written graph functions with the exact same node contracts (`app/graph/*.py`); `GroqClient` wraps `httpx`/`requests` directly against Groq's OpenAI-compatible endpoint, with no network to actually call it |
| `fastapi`, `chainlit`, `uvicorn[standard]` | M6's interface layer | `app/api_core.py`'s `ChatService` holds 100% of the testable logic (rate limit, concurrency, timeout, response shape); `app/main.py`/`ui/chainlit_app.py` are real, complete, `py_compile`-checked code that could not be imported or run here |
| `psycopg`, `pgvector` (Python package) | The real database driver | `tests/psql_executor.py`/`db_smoke.py` run the exact same validated SQL through the `psql` CLI against the real, live Phase 2 test cluster; `app/tools/postgres_tool.py`'s real `psycopg` path returns a clean `driver_unavailable` error here, never a silent stub |
| `sentence-transformers`, `torch`, `transformers` | Embeddings and the cross-encoder reranker | Deterministic hash-based stand-ins behind the same interface (documented in `app/rag/embeddings.py`/`reranker.py`); retrieval *logic* (chunking, candidate selection, screening) is still exercised for real, only the vector math is substituted |
| `pglast` | The SQL validator's parser | A hand-written, audited recursive-descent parser for exactly the read-only grammar subset this system needs (`app/guards/sql_parser.py`) — not a stub, a real alternative implementation, with its own found grammar gap documented in section 4 below |
| Outbound network to Groq | Every LLM-only judgment (routing, translation, SQL/Pandas generation, the M7 judge) | The dependency-injection pattern used everywhere in this build: every such step is an injectable callable defaulting to a real `GroqClient`-backed closure; tests inject deterministic stubs and say so |
| A reachable Docker daemon | Container-level isolation, image builds | `docker-compose.yml`/`Dockerfile` are real and complete; the **process**-level isolation they wrap (`app/tools/_pandas_worker.py`'s resource limits) is fully real and was exercised directly by `tests/test_pandas_sandbox_isolation.py` without Docker |
| `pip-audit`, `gitleaks`/`trufflehog`, `uv.lock` | M8's dependency/secret scan | A narrower, hand-written regex secret scanner (`tests/test_secret_and_dependency_scan.py`) and a pyproject-only pinning check, both honestly declared as partial substitutes, not equivalents |

## 3. Real Bugs Found and Fixed by This Build's Own Tests

Consistent with the pattern used throughout Phase 3: every bug below was caught by a test in this
repository, not reported by anyone, and fixed with real code before moving on.

1. **`app/graph/translate.py`**: `run_detect_and_translate` returned an English follow-up's literal text
   unresolved against conversation history (treating "needs translation" and "needs follow-up resolution"
   as the same condition, when an English message with history needs the second without the first). Found
   by `tests/test_evaluation_harness.py` replaying real scenario `EV-GR-008`.
2. **`tests/evaluation/grader.py`**: `_check_numeric_item` treated any `must_include` item containing a
   digit as a literal numeric claim against the final answer, false-failing `EV-RT-001` (whose item
   describes the *sub_question's* date range, not a figure the delivered answer should contain). Fixed with
   `_is_short_literal_item`, deferring longer semantic items to the judge instead of a deterministic check.
3. **`app/graph/inventory.py`**: had no production default SQL generator (unlike `data_analysis.py`'s
   `_default_sql_generator`), a real gap no existing M4 test exercised. Added `_default_sql_generator` for
   inventory, mirroring the data_analysis pattern.
4. **(M8) `app/guards/injection_patterns.py`/`input_guard.py`**: the Arabic halves of the injection screen
   were a documented placeholder ("deferred to M8"), not implemented. Added them for all five high-confidence
   categories and the five medium categories, verified against the two real Arabic attack scenarios already
   in the evaluation suite (`EV-RT-037`, `EV-GR-002`) and against all 105 real Arabic/mixed scenarios in the
   full 220-scenario suite (0 misses on the 2 real injection ones, 0 false positives on the other 103).
5. **(M8) `app/guards/input_guard.py`**: `normalize()` did not strip Arabic diacritics (tashkeel), so a
   diacritized attack phrase (e.g. "فصاعدًا" with a tanween mark) silently failed to match the
   undiacritized pattern text. Added diacritic stripping, the same kind of normalization section 4.1.1
   already does for zero-width/bidi characters and tatweel. Found by `tests/test_injection_corpus.py`.
6. **(M8, considered and reverted)** Two attempts to close remaining synthetic-corpus misses in
   `injection_patterns.py` — dropping the `override` category's required qualifier word, and loosening
   `privilege_claim` to match bare "I am/have [a] developer" regardless of context — were both reverted
   after they immediately produced false positives on ordinary benign sentences ("I am a developer working
   on this project, what were last month's sales?"). This is recorded as a finding, not hidden: the
   pre-existing, unmodified `privilege_claim` rule already has this exact narrow false-positive source
   (section 10 below), which this work did not introduce but did surface.

## 4. M8 Security Test Plan Results (05_security_and_guardrails.md section 16)

| Section 16 row | Test file | Result |
|---|---|---|
| SQL validator (one case per V-01..V-15, plus the 51 RAG examples) | `test_sql_validator_negative.py` (34 negative + 4 positive cases), `test_sql_parser_corpus.py`/`test_sql_validator_corpus.py` (51 real examples) | All pass; the one pre-existing, documented exception is a 50,000-row Pandas-feeding pattern that legitimately exceeds the 500-row SQL cap by design, not a validator defect |
| SQL red team (≥50 hostile statements: stacked statements, comments, quoting tricks, catalog access, locking clauses, side-effect functions, SET ROLE, COPY ... PROGRAM) | `test_sql_red_team.py` | 71 hostile statements across 9 categories, **0 reach an accepted result** |
| Database role (writes, `SET ... read_only=off` + write, temp tables, `rag` access, `customers.email`) | `test_db_role_permissions.py` | 15/15 checks pass against the real, live `bmp_readonly` role — including that toggling `default_transaction_read_only` off in a persistent session still fails on a privilege error, not merely the transaction mode |
| Pandas validator (≥30 escape attempts + the 20 sandbox examples) | `test_pandas_validator_negative.py` | 30 negative + 5 positive cases, 0 unexpected results (meets the ≥30 minimum exactly) |
| Sandbox (infinite loop, memory, file read, network, env read; validator disabled) | `test_pandas_sandbox_isolation.py` | 9/9 checks pass against the real, live isolated subprocess (`_pandas_worker.py`) with the AST validator bypassed — CPU/memory limits hold, no network path exists, the planted secret never leaks, and `import os`/`sys.modules` are blocked by the worker's own restricted namespace as a second, independent layer beneath RLIMIT_NPROC |
| Injection corpus (≥100 EN + ≥100 AR attacks, ≥100 benign) | `test_injection_corpus.py` | 178 EN + 155 AR attacks: 98.5% blocked-or-flagged-for-the-router (meets the ≥98% target under that reading), 97.3% blocked outright with no router involved at all (a stricter number, falls just short — see section 3 items 4-6 above for why the remaining gaps were not force-closed); 226 benign prompts (220-suite real prompts + hand-written): 0.44% false-positive rate (meets the ≤1% target); 0 false positives on the real evaluation suite specifically |
| Indirect injection (poisoned passage per index) | Already covered by M4/M5 work: `04_rag_design.md` section 10.1's passage screen, exercised end to end by `EV-GR-007`'s scenario and `app/guards/passage_screen.py`'s own build-time check | Pass (not re-tested in M8; no new work needed) |
| Output guard (emails, phones, keys, canary, salary lists, unsupported numbers, remote images) | `test_guards_and_graph_m5.py` (42 checks, M5) | Pass (not re-tested in M8; M5's own suite already covers every check in section 10.1's order) |
| Rate and size limits (2,000/2,001/100,000-char messages; bursts) | `test_rate_and_size_limits.py` | 9/9 checks pass: exact boundary behavior at 2,000/2,001 chars, a 100,000-char message rejected in <1s, the length check confirmed to run before the injection screen, and a 30-request burst against a 20/minute limit handled in under 5 seconds with exactly the right 20 accepted / 10 rejected |
| Dependency and secret scan | `test_secret_and_dependency_scan.py` | 228 text files scanned; 3 findings, all reviewed and accepted as low severity (local-sandbox-only test database passwords in `app/config.py`'s fallback defaults — see section 5.2); every `pyproject.toml` dependency has a version floor; `uv.lock`/`pip-audit` honestly noted as not runnable here (no network) |

**Net**: every section-16 row has either a passing automated test in this repository or an honest note on
why it could not be fully exercised here, with the real reason stated and the test that *is* possible
included instead.

## 5. Residual Risks (update to `05_security_and_guardrails.md` section 17)

1. **Arabic coverage**: M8 implemented the Arabic halves of the injection screen (previously a documented
   placeholder) and verified them against the real evaluation suite with zero false positives and zero
   missed real attacks, but this is explicitly *not* the native-speaker dialect review section 17 itself
   still calls for — only Modern Standard Arabic phrasings were covered, built and checked by this build's
   own (non-native-speaker) construction. Recommend a native-speaker pass before relying on this for
   anything beyond the current evaluation suite's own two Arabic attack scenarios.
2. **Local dev credentials in `app/config.py`**: three hardcoded fallback database passwords
   (`ro_test_pw`, `bmp_rag_writer_pw`, `bmp_rag_reader_pw`), all bound to `localhost:54329` and only used
   when the corresponding environment variable is unset. Reviewed and accepted as low severity (not
   reachable, not a production credential) by `test_secret_and_dependency_scan.py`, but worth a second look
   before any deployment that might run with those environment variables accidentally unset.
3. **SQL parser grammar gap**: the hand-written parser (`app/guards/sql_parser.py`, standing in for
   `pglast`, which cannot be installed here) recognizes `FOR UPDATE`/`FOR SHARE` only in the position
   directly after `WHERE`/`HAVING`, not PostgreSQL's standard trailing position after `LIMIT`/`OFFSET`. Found
   by `test_sql_red_team.py`. This is **not a security hole** — a statement using the standard position still
   fails to parse and is rejected (`V-13`, fail-closed) — but the error classification is less precise than
   it could be. Worth a grammar fix in a future pass, not urgent.
4. **Injection screen residual gaps**: five specific phrasings (documented in `test_injection_corpus.py`'s
   own docstring and assertions) produce no signal at all from the guard: two stylistic English jailbreak
   variants ("repeat everything above this line", "I am the lead developer... bypass the guardrails" without
   a qualifier word), and three Arabic variants (a "repeat what's above" phrasing with no named object, a
   self-identification-as-authority phrasing with no "نظام" word nearby, and zero-width-space obfuscation
   *between* Arabic words, which this build's normalization currently fuses into one word rather than
   preserving as a boundary). None were patched reflexively, because the two patches actually tried both
   introduced real false positives on ordinary benign sentences (section 3 item 6) — left as named, tracked
   gaps for the ongoing tuning section 16/06_evaluation_plan.md section 8.2 both describe this work as.
5. **Everything already listed in section 17** (no per-user authorization, small-group re-identification,
   language-model wording not guaranteed, static Pandas checks needing process isolation to actually hold,
   provider data handling) is unchanged by Phase 3's implementation and is not re-litigated here.

## 6. Status

Phase 3 is complete through M8. `08_phase_plan.md` still shows Phase 3 as "Not Started" in its own table and
the README's status line still reads "In progress" — both can be updated to reflect this delivery, but
neither has been changed here, since the standing instruction was not to touch docs 01/02/03/08 without
being asked, and the README's status table mirrors that same table.

No further milestone is defined in `08_phase_plan.md` beyond M8.
