"""A `psql`-based stand-in for `app.tools.postgres_tool.postgres_tool`, used only in tests
(see `tests/db_smoke.py` for the original version of this technique). `psycopg` cannot be
installed in this sandbox, so `postgres_tool` itself always returns `driver_unavailable`;
this lets the subgraph tests exercise the full validate -> execute -> format control flow
against the real, live Phase 2 test database instead of stopping at that wall. It still
runs every SQL string through the real validator first (`app.guards.sql_validator`), exactly
as `postgres_tool` does -- only the final execution step is swapped out.
"""
from __future__ import annotations

import subprocess

from app.guards.sql_validator import validate_sql

PGARGS = ["psql", "-h", "/tmp/pgsock", "-p", "54329", "-U", "bmp_readonly", "-d", "bmp"]


def psql_postgres_tool(sql: str, max_rows: int = 500) -> dict:
    validation = validate_sql(sql, max_rows=max_rows)
    if not validation.ok:
        return validation.to_error()
    proc = subprocess.run(
        PGARGS + ["-At", "-F", "\t", "-c", validation.sql],
        capture_output=True, text=True, env={"PGPASSWORD": "ro_test_pw"}, timeout=15,
    )
    if proc.returncode != 0:
        return {"error": {"code": "db_error", "message": proc.stderr.strip()[:500]}}
    lines = [l for l in proc.stdout.split("\n") if l != ""] if proc.stdout.strip() else []
    rows = [line.split("\t") for line in lines]
    columns = _columns_of(validation.sql)
    return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": False, "elapsed_ms": 0}


def _columns_of(sql: str) -> list[str]:
    proc = subprocess.run(
        PGARGS + ["-At", "-F", "\t", "-c", f"SELECT * FROM ({sql.rstrip(';')}) t LIMIT 0"],
        capture_output=True, text=True, env={"PGPASSWORD": "ro_test_pw"}, timeout=15,
    )
    header_proc = subprocess.run(
        PGARGS + ["-c", f"SELECT * FROM ({sql.rstrip(';')}) t LIMIT 0"],
        capture_output=True, text=True, env={"PGPASSWORD": "ro_test_pw"}, timeout=15,
    )
    if header_proc.returncode == 0:
        lines = header_proc.stdout.splitlines()
        if lines:
            return [c.strip() for c in lines[0].split("|")]
    return []
