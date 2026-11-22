"""`postgres_tool` (02_architecture.md section 6.1): the only way any part of this system
touches business data. Every call is validated by `sql_validator.validate_sql` (V-01..V-15)
before anything is sent to the database; the connection itself is `bmp_readonly`, opened
read-only, with the statement/lock/idle timeouts of `05_security_and_guardrails.md`
section 6.3-6.4 applied again at the session level as a second, independent layer.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from app.config import settings
from app.guards.sql_validator import validate_sql

try:
    import psycopg
    from psycopg_pool import ConnectionPool

    _HAVE_PSYCOPG = True
except ImportError:  # pragma: no cover
    _HAVE_PSYCOPG = False

_pool: Optional["ConnectionPool"] = None


def _get_pool() -> "ConnectionPool":
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            settings.database_url_readonly,
            min_size=0,
            max_size=5,
            kwargs={
                "application_name": "bmp_assistant",
                "connect_timeout": 5,
                "autocommit": False,
            },
            open=True,
        )
    return _pool


def _session_setup_sql() -> str:
    return (
        f"SET statement_timeout = '{settings.sql_statement_timeout_s}s'; "
        f"SET lock_timeout = '{settings.sql_lock_timeout_s}s'; "
        f"SET idle_in_transaction_session_timeout = '{settings.sql_idle_txn_timeout_s}s';"
    )


def postgres_tool(sql: str, max_rows: int = 500) -> dict:
    max_rows = min(max_rows, settings.sql_max_rows_for_pandas)
    validation = validate_sql(
        sql, max_rows=max_rows, max_chars=settings.sql_max_chars, max_relations=settings.sql_max_relations,
    )
    if not validation.ok:
        return validation.to_error()

    if not _HAVE_PSYCOPG:
        return {
            "error": {
                "code": "driver_unavailable",
                "message": "psycopg is not installed in this environment.",
            }
        }

    t0 = time.monotonic()
    try:
        pool = _get_pool()
        with pool.connection(timeout=settings.sql_statement_timeout_s + 5) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(_session_setup_sql())
                cur.execute(validation.sql)
                columns = [d.name for d in cur.description] if cur.description else []
                rows = cur.fetchmany(max_rows + 1)
                truncated = len(rows) > max_rows
                if truncated:
                    rows = rows[:max_rows]
            conn.rollback()
    except Exception as e:  # noqa: BLE001
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        # Keep the original message for the existing retry feedback, but expose only
        # structured PostgreSQL diagnostics to application logs (never log SQL/params).
        diag = getattr(e, "diag", None)
        primary = getattr(diag, "message_primary", None) if diag is not None else None
        return {
            "error": {
                "code": "db_error",
                "message": str(e),
                "elapsed_ms": elapsed_ms,
                "exception_type": type(e).__name__,
                "sqlstate": getattr(e, "sqlstate", None),
                "message_primary": primary,
            }
        }

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return {
        "columns": columns,
        "rows": [list(r) for r in rows],
        "row_count": len(rows),
        "truncated": truncated,
        "elapsed_ms": elapsed_ms,
    }
