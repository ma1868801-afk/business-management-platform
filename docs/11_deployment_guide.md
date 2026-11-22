# 11. Deployment Guide

This guide covers bringing up the full Phase 3 system (FastAPI backend, Chainlit UI, PostgreSQL for business
data, ChromaDB for RAG storage, the RAG indexer) with Docker Compose, running it locally without Docker for
development, and running the test and evaluation suites against a live deployment. It assumes Phase 2's
dataset has already been built (`database/README.md`); it does not repeat that guide. RAG storage moved from
pgvector to ChromaDB after the original Phase 3 delivery -- see `docs/12_chromadb_migration.md` for why and
what changed; this guide reflects the current (Chroma) architecture throughout.

Everything here was written and, where a step needs nothing this sandbox lacks, run against the real,
live Phase 2 test cluster during M1-M8. Three specific steps could not be run here and are marked
**[not run in this sandbox]** below, each with the reason and what confirms it instead — this sandbox has
no outbound network access beyond the Python/Node package registries and GitHub (05_security_and_guardrails.md's
own principles do not change that), so it cannot pull Docker images, install compiled dependencies that need
a network-hosted wheel, or reach the Groq API. Nothing about the commands themselves is hypothetical; they
are the actual commands `docker-compose.yml`, `Dockerfile` and `pyproject.toml` already encode.

## 1. Prerequisites

| Requirement | Why |
|---|---|
| Docker and Docker Compose v2 | Runs `db`, `db-init`, `chroma`, `indexer`, `app`, `ui` as defined in `docker-compose.yml`. |
| A Groq API key | `GROQ_API_KEY`; the LLM (`openai/gpt-oss-120b`) and the embedding/reranker calls that need the LLM client all go through it. |
| ~150 MB free disk for the loaded database, ~2 GB for Docker images | Phase 2 dataset + the Chroma vector index (section 2 below) + Python dependencies (pandas/numpy/scipy/sentence-transformers/torch are not small). |
| Outbound network access to Docker Hub/GHCR, PyPI, and the Groq API | To pull images, install dependencies, and serve real requests. |

## 2. Configuration

Copy `.env.example` to `.env` and fill in the required secrets:

```bash
cp .env.example .env
```

| Variable | Required | Notes |
|---|---|---|
| `GROQ_API_KEY` | yes | From the Groq console. Never commit it; `.env` is gitignored. |
| `BMP_READONLY_PASSWORD` | yes | Password for the `bmp_readonly` role (`database/sql/04_roles.sql`), the only database credential the application needs — PostgreSQL now holds only business data (`docs/12_chromadb_migration.md`). Choose a real one — `app/config.py`'s own fallback default (`ro_test_pw`) is a local-sandbox-only value, not meant for any reachable deployment (see the M8 security test report, section 5.2). |
| `CHROMA_HOST`, `CHROMA_PORT` | set by `docker-compose.yml` | RAG storage (`docs/12_chromadb_migration.md`). Compose points `indexer` and `app` at the shared `chroma` service automatically; set these yourself only for a non-compose run against a remote/shared Chroma server (05_security_and_guardrails.md section 13 on why that server should not be reachable beyond the trusted network — it has no auth of its own). Leave `CHROMA_HOST` empty for a single-process/dev run with no Docker (section 4 below uses a local on-disk client instead, via `CHROMA_PERSIST_DIR`). |
| `POSTGRES_SUPERUSER_PASSWORD` | recommended | Defaults to `postgres` if unset; set a real value for anything beyond a local demo. |
| `BMP_CANARY_TOKEN` | optional | If unset, `app/config.py` generates a random one at process startup (section 5.3). Set it explicitly only if you need a stable value across restarts for log correlation. |
| `BMP_TEST_HOOKS` | must stay `0` | 05_security_and_guardrails.md section 8.2: "NEVER set this in production." It exists only so the evaluation harness can inject deterministic fault behavior; leave it unset or `0` everywhere outside a test run. |
| `REFERENCE_DATE` | optional | Defaults to `2026-10-31` (assumption A-03/D-7). The application never reads the system clock for analysis; change this only if the dataset itself is regenerated for a different reference date. |
| `RATE_LIMIT_PER_MINUTE`, `MAX_REQUEST_SECONDS`, `MAX_HISTORY_TURNS`, `MAX_INPUT_CHARS` | optional | Defaults match 05_security_and_guardrails.md section 14; override only if you understand the trade-off (e.g. raising `MAX_REQUEST_SECONDS` past 60s changes what "stays responsive" means for the service). |

## 3. Bring Up The Stack

**[not run in this sandbox: no Docker daemon reachable here, and pulling `pgvector/pgvector:pg16`,
`chromadb/chroma:0.5.15` and building the app image all need outbound network access this sandbox does not
have. Every file this step depends on — `docker-compose.yml`, `Dockerfile`, `app/main.py`, `ui/chainlit_app.py`
— exists, was read for this guide, and was syntax-checked with `py_compile` (see the M7/M8 notes on
`fastapi`/`chainlit` not being installable here, and `docs/12_chromadb_migration.md`'s note on `chromadb`);
only the actual container build-and-run step itself could not be exercised.]**

```bash
docker compose up --build
```

This brings up, in dependency order:

1. `db` — PostgreSQL 16, loading the schema and Phase 2 business-data dataset from `database/sql/*.sql` via
   the standard `docker-entrypoint-initdb.d` mechanism (first start only; subsequent starts reuse the
   `pgdata` volume). No RAG data lives here (`docs/12_chromadb_migration.md`).
2. `db-init` — a one-off job that creates `bmp_readonly` with the password from your `.env` (it needs a
   password parameter `initdb.d` scripts can't supply, so it runs here instead).
3. `chroma` — the ChromaDB server RAG storage lives in, with its own `chromadata` volume.
4. `indexer` — builds the RAG index from `rag_sources/` into `chroma`'s collections (04_rag_design.md
   section 10.1's build-time checks, including the passage screen, run here) and exits.
5. `app` — the FastAPI backend (`uvicorn app.main:app`), internal to the compose network on port 8080.
6. `ui` — the Chainlit interface, published on `http://localhost:8000`.

Check it came up correctly:

```bash
docker compose ps                                    # db, chroma, app, ui should be "running" / "healthy"; db-init and indexer "exited (0)"
curl http://localhost:8000                            # the Chainlit UI should respond
docker compose exec app curl -s http://localhost:8080/healthz   # the FastAPI healthz endpoint, from inside the network
docker compose exec chroma curl -s http://localhost:8000/api/v1/heartbeat  # the Chroma server's own health check
```

To rebuild just the index after changing `rag_sources/` (no code or schema change):

```bash
docker compose run --rm indexer
```

## 4. Running Without Docker (Development)

For iterating on `app/` or `ui/` directly:

```bash
uv sync                      # installs from pyproject.toml; needs network access to PyPI
# or: pip install -e . --break-system-packages
export $(cat .env | xargs)   # or use python-dotenv, which app/config.py already loads automatically
python -m app.rag.indexer    # build the RAG index once (writes into ChromaDB -- see below)
uvicorn app.main:app --reload --port 8080
chainlit run ui/chainlit_app.py --port 8000            # in a second terminal; BACKEND_URL defaults to localhost:8080
```

With no `CHROMA_HOST` set, the indexer and the app both use a local on-disk Chroma `PersistentClient` under
`CHROMA_PERSIST_DIR` (default `.chroma/`) — no separate Chroma process to run for this path, since both
commands above are typically run from the same machine against the same directory. Running `uvicorn` and the
indexer from genuinely different machines (or wanting the same isolation Compose gives the `db`/`chroma`
services) needs a real Chroma server: run `chroma run --path ./chroma_data --port 8000` (or the
`chromadb/chroma` image directly) and set `CHROMA_HOST=localhost` for both processes instead.

This is the same code path the Docker images run; only the process supervision, networking, and (for the
`CHROMA_HOST` choice above) the Chroma client mode differ.

## 5. Verifying a Deployment

Three checks, cheapest first, each already proven as a real test in this repository:

1. **Health**: `GET /healthz` (via the FastAPI app directly, or `curl` from inside the compose network — see
   section 3) should return quickly with no error.
2. **A real chat turn**: `POST /chat` with `{"session_id": "smoke-1", "message": "What was the net revenue for 2025?"}`
   should return a non-error response with `status: "ok"` and at least one source.
3. **The evaluation harness smoke set** (53 of the 220 scenarios — 06_evaluation_plan.md section 8.1):

   ```bash
   python3 tests/evaluation/run_evaluation.py --mode smoke --run-id deploy-smoke-$(date +%Y%m%d)
   ```

   This needs `GROQ_API_KEY` to be real and reachable (the router/subgraph/aggregator decisions in this
   repository's own test files are stubbed only where this sandbox itself has no model access; the harness
   script's own default path calls the real `GroqClient`). Read the result in
   `evaluation/reports/deploy-smoke-<date>/summary.md`. A judge model must additionally be configured for the
   `answer` component's `must_include`/`must_not_include` items to grade as pass/fail rather than `ungraded`
   (06_evaluation_plan.md section 5) — this repository's own M7 work proved the harness's mechanics end to
   end but could not itself run a judge, for the same no-network reason noted throughout.

## 6. Running the Test and Security Suites

All `tests/test_*.py` files in this repository are plain scripts (`python3 tests/test_X.py`), not a
pytest-only suite, so they run the same way in CI, in a container, or on a laptop. Most need the live
database (`/tmp/pgsock:54329` in this sandbox's own dev cluster — point `tests/psql_executor.py`'s `PGARGS`
at a real deployment's database instead, or, once `psycopg` is installed, use `app/tools/postgres_tool`
directly, which this sandbox could never do). A few need nothing but the standard library and are safe to
run anywhere, including in CI with no database at all: `test_sql_validator_negative.py`,
`test_sql_red_team.py`, `test_pandas_validator_negative.py`, `test_pandas_sandbox_isolation.py`,
`test_injection_corpus.py` (reads the evaluation scenario files but needs no DB/LLM),
`test_secret_and_dependency_scan.py`, `test_chroma_store.py` (RAG storage logic against a faithful fake
of the `chromadb` client — see `docs/12_chromadb_migration.md`), `test_rag_readonly_serving_path.py`.

The M8 Security Test Plan (05_security_and_guardrails.md section 16) maps to these files — see
`10_phase3_completion_report.md` section 4 for the full table and results. Run them all:

```bash
for f in tests/test_*.py; do echo "=== $f ==="; python3 "$f"; done
```

A release gate (section 16: "They run in CI and must pass for a release") should run this whole loop, plus
the evaluation harness's smoke set, against a real deployment with a real `GROQ_API_KEY` and a real judge
model configured — the parts of M7/M8 this sandbox could only prove the mechanics of, not the full real-LLM
numbers for.

## 7. Operational Notes

- **Logs and traces** are capped and redacted by design (section 12): no customer contact details, user
  messages truncated to 500 characters, answers to 1,000. `TRACE_RETENTION_DAYS` (default 30) should be
  enforced by whatever log pipeline ingests the application's output; the application itself does not run a
  background deletion job.
- **Secrets rotation**: rotating `GROQ_API_KEY` or any database password only needs the corresponding `.env`
  value changed and the affected service(s) restarted — nothing is cached to disk outside the environment.
- **Scaling the `app` service** horizontally is safe: `SessionStore` (`app/sessions.py`) is in-process and
  per-session rate limiting/concurrency is therefore per-instance, not global, which is a real trade-off to
  know about before scaling past one replica — a user whose requests land on different instances gets a
  higher effective rate limit than `RATE_LIMIT_PER_MINUTE` implies. A production deployment that needs a
  hard global limit should move session state to a shared store (e.g. Redis) instead; this was not required
  by any Phase 3 document and was not built.
- **The Pandas sandbox** (section 7.2) runs as a subprocess of the `app` container today, not a separate
  container — `docker-compose.yml`'s `cap_drop`/`security_opt` hardening on the `app` service is the
  deployment-level backstop section 17 calls for ("the isolation must be tested as part of M8 and kept when
  the base image is upgraded"); `tests/test_pandas_sandbox_isolation.py` is the automated check that the
  subprocess-level resource limits still hold after any change to `app/tools/_pandas_worker.py` or the base
  image's Python build.
- **Chainlit authentication** (section 13: "enabled for any deployment beyond a local demonstration") is not
  configured in `ui/chainlit_app.py` as delivered — add it before exposing the `ui` service's port beyond a
  trusted network.
