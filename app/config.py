"""Central configuration, loaded from environment variables.

Defaults and names follow `02_architecture.md` section 11 and the additional
variables of `04_rag_design.md` section 12 and `05_security_and_guardrails.md`
sections 4.4 and 14. No file in this module ever reads the system clock for
business logic -- `REFERENCE_DATE` is the only date the application trusts
(assumption A-03, rule V-11).

Plain `os.environ` + dataclasses is used instead of `pydantic-settings` so that
this module has no dependency beyond the standard library and `pydantic`
itself (already required elsewhere); it also means configuration can be
imported and unit-tested without a database, a model, or network access.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - python-dotenv is a soft dependency
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    v = os.environ.get(name)
    return int(v) if v else default


def _float(name: str, default: float) -> float:
    v = os.environ.get(name)
    return float(v) if v else default


def _date(name: str, default: str) -> date:
    v = os.environ.get(name, default)
    return date.fromisoformat(v)


def _str(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    # --- 02_architecture.md section 11 --------------------------------------------------------
    groq_api_key: str = field(default_factory=lambda: _str("GROQ_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: _str("LLM_MODEL", "openai/gpt-oss-120b"))
    database_url_readonly: str = field(
        default_factory=lambda: _str(
            "DATABASE_URL_READONLY",
            "postgresql://bmp_readonly:ro_test_pw@localhost:54329/bmp",
        )
    )
    # RAG storage (docs/12_chromadb_migration.md): ChromaDB, not PostgreSQL. Postgres keeps
    # only business data from here on -- see database_url_readonly above, the only database
    # connection the application needs.
    #
    # chroma_host set (non-empty) -> an HttpClient against a shared Chroma server, the Docker
    # Compose topology: `indexer` and `app` are separate containers/processes pointed at one
    # `chroma` service, the same way they already share one `db` Postgres service.
    # chroma_host empty (the default, for a single-process/dev run with no Docker) -> a local
    # PersistentClient under chroma_persist_dir; see app/rag/store.py's connect().
    chroma_host: str = field(default_factory=lambda: _str("CHROMA_HOST", ""))
    chroma_port: int = field(default_factory=lambda: _int("CHROMA_PORT", 8000))
    chroma_persist_dir: Path = field(default_factory=lambda: Path(_str("CHROMA_PERSIST_DIR", str(REPO_ROOT / ".chroma"))))
    # Bounded wait for the Chroma *server* to actually be ready to serve requests, not just
    # for its container to have started -- `chromadb.HttpClient(...)` doesn't make a network
    # call at construction time, so without this, the first real operation (indexing, or the
    # app's first retrieval) is what hits the race and fails hard. This is a code-level
    # backstop for the same race docker-compose.yml's `chroma` healthcheck and the indexer's
    # `depends_on: condition: service_healthy` address at the infrastructure level -- it
    # also covers running these processes outside Compose (bare `python -m app.rag.indexer`
    # against an already-started but still-initializing `chroma run` server).
    chroma_connect_retries: int = field(default_factory=lambda: _int("CHROMA_CONNECT_RETRIES", 30))
    chroma_connect_retry_wait: float = field(default_factory=lambda: _float("CHROMA_CONNECT_RETRY_WAIT", 2.0))
    embedding_model: str = field(default_factory=lambda: _str("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    reranker_model: str = field(default_factory=lambda: _str("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"))
    reference_date: date = field(default_factory=lambda: _date("REFERENCE_DATE", "2026-10-31"))
    max_request_seconds: int = field(default_factory=lambda: max(90, _int("MAX_REQUEST_SECONDS", 90)))

    # --- 04_rag_design.md section 12 -----------------------------------------------------------
    rerank_mode: str = field(default_factory=lambda: _str("RERANK_MODE", "cross_encoder"))
    rag_top_k_per_query: int = field(default_factory=lambda: _int("RAG_TOP_K_PER_QUERY", 20))
    rag_llm_preprocess_enabled: bool = field(default_factory=lambda: _bool("RAG_LLM_PREPROCESS_ENABLED", False))
    rag_variants: int = field(default_factory=lambda: _int("RAG_VARIANTS", 3))
    rag_router_variants: int = field(default_factory=lambda: _int("RAG_ROUTER_VARIANTS", 2))
    rag_rrf_k: int = field(default_factory=lambda: _int("RAG_RRF_K", 60))
    rag_rerank_candidates: int = field(default_factory=lambda: _int("RAG_RERANK_CANDIDATES", 40))
    rag_final_top_n: int = field(default_factory=lambda: _int("RAG_FINAL_TOP_N", 6))
    rag_router_final_top_n: int = field(default_factory=lambda: _int("RAG_ROUTER_FINAL_TOP_N", 8))
    rag_max_per_doc: int = field(default_factory=lambda: _int("RAG_MAX_PER_DOC", 3))
    rag_min_rerank_score: float = field(default_factory=lambda: _float("RAG_MIN_RERANK_SCORE", -4.0))
    rag_entity_leg: bool = field(default_factory=lambda: _bool("RAG_ENTITY_LEG", True))
    rag_max_calls_per_subgraph: int = field(default_factory=lambda: _int("RAG_MAX_CALLS_PER_SUBGRAPH", 2))

    # --- 05_security_and_guardrails.md section 4.4 (session limits) --------------------------
    rate_limit_per_minute: int = field(default_factory=lambda: _int("RATE_LIMIT_PER_MINUTE", 20))
    max_history_turns: int = field(default_factory=lambda: _int("MAX_HISTORY_TURNS", 6))
    history_answer_chars: int = field(default_factory=lambda: _int("HISTORY_ANSWER_CHARS", 500))

    # --- 05_security_and_guardrails.md section 14 (resource limits) --------------------------
    max_input_chars: int = field(default_factory=lambda: _int("MAX_INPUT_CHARS", 2000))
    sql_max_chars: int = field(default_factory=lambda: _int("SQL_MAX_CHARS", 8000))
    sql_max_relations: int = field(default_factory=lambda: _int("SQL_MAX_RELATIONS", 12))
    sql_max_rows: int = field(default_factory=lambda: _int("SQL_MAX_ROWS", 500))
    sql_max_rows_for_pandas: int = field(default_factory=lambda: _int("SQL_MAX_ROWS_FOR_PANDAS", 50000))
    sql_statement_timeout_s: int = field(default_factory=lambda: _int("SQL_STATEMENT_TIMEOUT_S", 8))
    sql_lock_timeout_s: int = field(default_factory=lambda: _int("SQL_LOCK_TIMEOUT_S", 2))
    sql_idle_txn_timeout_s: int = field(default_factory=lambda: _int("SQL_IDLE_TXN_TIMEOUT_S", 10))
    pandas_max_chars: int = field(default_factory=lambda: _int("PANDAS_MAX_CHARS", 6000))
    pandas_max_lines: int = field(default_factory=lambda: _int("PANDAS_MAX_LINES", 120))
    pandas_timeout_s: int = field(default_factory=lambda: _int("PANDAS_TIMEOUT_S", 5))
    pandas_max_input_rows: int = field(default_factory=lambda: _int("PANDAS_MAX_INPUT_ROWS", 50000))
    pandas_max_output_rows: int = field(default_factory=lambda: _int("PANDAS_MAX_OUTPUT_ROWS", 200))
    forecast_max_horizon_weeks: int = field(default_factory=lambda: _int("FORECAST_MAX_HORIZON_WEEKS", 13))
    forecast_max_history_weeks: int = field(default_factory=lambda: _int("FORECAST_MAX_HISTORY_WEEKS", 200))
    sql_regen_limit: int = field(default_factory=lambda: _int("SQL_REGEN_LIMIT", 2))
    pandas_regen_limit: int = field(default_factory=lambda: _int("PANDAS_REGEN_LIMIT", 2))
    # LLM transport reliability (TechNova reference: src/llm_utils.py safe_invoke). This is
    # distinct from the semantic, schema-validation retries each node already does on its own
    # (e.g. app/graph/router.py's "one retry, then clarify"): llm_retry_limit governs retries of
    # the raw network call itself (timeouts, rate limits, transient provider errors) inside
    # `GroqClient.complete_json`, before the result ever reaches a node's own retry logic.
    llm_retry_limit: int = field(default_factory=lambda: min(1, max(0, _int("LLM_RETRY_LIMIT", 1))))
    llm_timeout_seconds: float = field(default_factory=lambda: min(15.0, max(5.0, _float("LLM_TIMEOUT_SECONDS", 15.0))))
    llm_retry_min_wait: float = field(default_factory=lambda: min(0.5, max(0.1, _float("LLM_RETRY_MIN_WAIT", 0.5))))
    llm_retry_max_wait: float = field(default_factory=lambda: min(3.0, max(0.5, _float("LLM_RETRY_MAX_WAIT", 3.0))))

    # --- misc ------------------------------------------------------------------------------------
    trace_retention_days: int = field(default_factory=lambda: _int("TRACE_RETENTION_DAYS", 30))
    company_email_domains: tuple[str, ...] = field(
        default_factory=lambda: tuple(_str("COMPANY_EMAIL_DOMAINS", "nakhla-retail.example").split(","))
    )
    judge_model: str = field(default_factory=lambda: _str("JUDGE_MODEL", "openai/gpt-oss-120b"))
    bmp_test_hooks: bool = field(default_factory=lambda: _bool("BMP_TEST_HOOKS", False))

    # Logging (TechNova reference: src/logging_utils.py). Structured JSON by default so a
    # deployment's log aggregator can parse it; plain text is easier to read locally.
    log_level: str = field(default_factory=lambda: _str("LOG_LEVEL", "INFO"))
    log_json: bool = field(default_factory=lambda: _bool("LOG_JSON", True))

    # Per-process canary token (05_security_and_guardrails.md section 5.3): a random string
    # minted once at startup, embedded in every system prompt, and checked for in every output.
    canary_token: str = field(default_factory=lambda: _str("BMP_CANARY_TOKEN", "") or secrets.token_hex(16))

    rag_sources_dir: Path = field(default_factory=lambda: REPO_ROOT / "rag_sources")
    evaluation_dir: Path = field(default_factory=lambda: REPO_ROOT / "evaluation")


settings = Settings()
