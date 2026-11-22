"""M8 Security Test Plan (05_security_and_guardrails.md section 16, "Database role" row):
"Connect as `bmp_readonly` and try writes, `SET default_transaction_read_only = off`
followed by writes, temp tables, `customers.email` -- all fail with permission errors."

This file no longer tests `rag` schema access (it did, until `docs/12_chromadb_migration.md`):
RAG storage is ChromaDB, not a Postgres schema, so there is nothing left in this database for
`bmp_readonly` to be denied against -- the schema does not exist at all, which is a stronger
guarantee than a `REVOKE`, not a weaker one. The RAG-side access-control trade-off this
migration introduced (Chroma has no Postgres-style per-role grant system) is covered instead
by `tests/test_rag_readonly_serving_path.py` and documented in
`05_security_and_guardrails.md` sections 13 and 17.

Unlike every other SQL test in this project, this one deliberately does NOT go through
`validate_sql` first -- the whole point is to prove layer 6 of section 3 ("enforcement
outside the app: database role, read-only transaction, sandbox process") holds even if
every layer above it (the validator, the router, the model) is bypassed or compromised,
per principle 2: "each layer assumes that the layers before it failed." It connects
directly to the real, live Phase 2 test cluster as `bmp_readonly` via `psql` (the same
stand-in `psycopg`'s absence from this sandbox forces everywhere else, see
`tests/psql_executor.py`) and sends raw hostile SQL.

Requires the Phase 2 test cluster running at /tmp/pgsock:54329 (see database/README.md).
Run directly: python3 tests/test_db_role_permissions.py
"""
from __future__ import annotations

import subprocess

PGARGS = ["psql", "-h", "/tmp/pgsock", "-p", "54329", "-U", "bmp_readonly", "-d", "bmp"]
ENV = {"PGPASSWORD": "ro_test_pw"}

FAILURES = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    status = "OK" if cond else "FAIL"
    if not cond:
        FAILURES += 1
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))


def run_sql(sql: str, *, new_connection: bool = True) -> tuple[int, str, str]:
    """Runs `sql` as a single `psql -c` call (one connection, one implicit transaction per
    statement sent) unless `new_connection` is False, in which case the caller passes a
    multi-statement script on stdin so it shares one *session* (but still separate
    transactions per statement, matching how a real application connection behaves)."""
    proc = subprocess.run(PGARGS + ["-At", "-c", sql], capture_output=True, text=True, env=ENV, timeout=15)
    return proc.returncode, proc.stdout, proc.stderr


def run_session_script(sql_script: str) -> tuple[int, str, str]:
    proc = subprocess.run(PGARGS, input=sql_script, capture_output=True, text=True, env=ENV, timeout=15)
    return proc.returncode, proc.stdout, proc.stderr


def expect_denied(name: str, sql: str, *, markers: tuple[str, ...]) -> None:
    rc, out, err = run_sql(sql)
    ok = rc != 0 and any(m in err for m in markers)
    check(name, ok, f"rc={rc} stderr={err.strip()[:200]!r}")


def main() -> int:
    # --- plain writes on real tables, each via its real own column (not a typo'd one) ---
    expect_denied(
        "UPDATE on products is denied",
        "UPDATE products SET unit_price = 0 WHERE product_id = 1;",
        markers=("permission denied", "read-only transaction"),
    )
    expect_denied(
        "INSERT on sales_orders is denied",
        "INSERT INTO sales_orders (order_id) VALUES (999999999);",
        markers=("permission denied", "read-only transaction"),
    )
    expect_denied(
        "DELETE on sales_orders is denied",
        "DELETE FROM sales_orders WHERE order_id = -1;",
        markers=("permission denied", "read-only transaction"),
    )
    expect_denied(
        "TRUNCATE on sales_order_items is denied",
        "TRUNCATE sales_order_items;",
        markers=("permission denied", "read-only transaction"),
    )

    # --- SET default_transaction_read_only = off, then write, in the SAME session ---
    # Section 6.4: "default_transaction_read_only is a default, not a barrier: a session
    # can switch it off with SET." This proves what actually stops the write once the
    # transaction-mode barrier is gone: the role has no write privilege at all.
    rc, out, err = run_session_script(
        "SET default_transaction_read_only = off;\nDELETE FROM sales_orders WHERE order_id = -1;\n"
    )
    # psql's own exit code for a piped multi-statement script reflects whether `psql`
    # itself ran cleanly, not whether every individual statement inside it succeeded (that
    # is `psql`'s documented default, without `-v ON_ERROR_STOP=1`) -- the actual per-
    # statement outcome is on stderr, which is what this check reads.
    check(
        "SET default_transaction_read_only=off then DELETE in the same session still fails "
        "(on a PRIVILEGE error, not merely the read-only transaction mode)",
        "permission denied" in err,
        f"rc={rc} stderr={err.strip()[:300]!r}",
    )

    # --- temp tables ---
    expect_denied(
        "CREATE TEMP TABLE is denied (read-only transaction)",
        "CREATE TEMP TABLE t_evil (x int);",
        markers=("read-only transaction",),
    )

    # --- customers.email / customers.phone (column-level grant, section 11) ---
    expect_denied(
        "SELECT customers.email is denied (column-level grant omits it)",
        "SELECT email FROM customers LIMIT 1;",
        markers=("permission denied for table customers",),
    )
    expect_denied(
        "SELECT customers.phone is denied (column-level grant omits it)",
        "SELECT phone FROM customers LIMIT 1;",
        markers=("permission denied for table customers",),
    )
    expect_denied(
        "SELECT * FROM customers is denied as a whole (the * expansion includes the omitted columns)",
        "SELECT * FROM customers LIMIT 1;",
        markers=("permission denied for table customers",),
    )
    # A column the role DOES have (customer_code) still works -- proves the above are a
    # real column-level grant, not the role being denied the whole table outright.
    rc, out, err = run_sql("SELECT customer_code FROM customers LIMIT 1;")
    check("SELECT customers.customer_code (a granted column) succeeds", rc == 0, f"rc={rc} stderr={err.strip()[:200]!r}")

    # --- privilege escalation attempts ---
    expect_denied(
        "GRANT is denied",
        "GRANT SELECT ON products TO public;",
        markers=("permission denied", "read-only transaction", "must be owner"),
    )
    expect_denied(
        "CREATE ROLE is denied (NOCREATEROLE)",
        "CREATE ROLE evil LOGIN SUPERUSER;",
        markers=("permission denied", "read-only transaction"),
    )
    expect_denied(
        "ALTER ROLE bmp_readonly SUPERUSER is denied (cannot self-escalate)",
        "ALTER ROLE bmp_readonly SUPERUSER;",
        markers=("permission denied", "read-only transaction"),
    )

    # --- role attribute sanity: confirm the role really is as unprivileged as assumed ---
    rc, out, err = run_sql(
        "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls FROM pg_roles WHERE rolname = 'bmp_readonly';"
    )
    check(
        "bmp_readonly has NOSUPERUSER/NOCREATEROLE/NOCREATEDB and does not bypass row-level security",
        rc == 0 and out.strip() == "f|f|f|f",
        f"rc={rc} out={out.strip()!r} stderr={err.strip()[:200]!r}",
    )

    print(f"\n{FAILURES} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
