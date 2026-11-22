"""M8: performance ("Security tests, performance, documentation, deployment guide" per
08_phase_plan.md's M8 row). 05_security_and_guardrails.md section 16 has no dedicated
performance row (it is a security test plan), so this measures the budgets
section 14 ("Resource Limits") actually states, against the real, non-LLM parts of the
pipeline this sandbox can run: the SQL validator, the live database, and the real isolated
Pandas subprocess. It measures wall-clock time, not request count or memory, and reports
numbers rather than asserting hard pass/fail thresholds where no threshold is documented.

Honest scope limit: there is no network access to Groq in this sandbox (section 13: no
PyPI either, but that is unrelated -- this is simply no outbound network to the LLM
provider), so no number here includes a real LLM call's latency, and no meaningful
end-to-end "time to answer a question" figure can be produced -- that number is dominated by
the LLM call in the real system, and Section 14's `MAX_REQUEST_SECONDS` = 60s budget exists
specifically to bound that, unmeasurable-here, cost. What IS measured is everything else in
the request path: the input guard, the SQL validator (over all 51 real RAG-source
examples), a live database round trip, and the isolated Pandas subprocess -- together, the
part of the 60-second budget that is NOT the model call, so a deployment can see how much
of that budget the rest of the pipeline actually spends.

Requires the Phase 2 test cluster running at /tmp/pgsock:54329 (see database/README.md).
Run directly: python3 tests/test_performance_m8.py
"""
from __future__ import annotations

import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from app.guards.input_guard import input_guard  # noqa: E402
from app.guards.sql_validator import validate_sql  # noqa: E402
from app.tools.pandas_tool import pandas_tool  # noqa: E402
from psql_executor import psql_postgres_tool  # noqa: E402

FAILURES = 0
_PAT = re.compile(r"```sql\n(.*?)```", re.S)


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    status = "OK" if cond else "FAIL"
    if not cond:
        FAILURES += 1
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))


def timed(fn, n: int = 20) -> list[float]:
    out = []
    for _ in range(n):
        t0 = time.monotonic()
        fn()
        out.append((time.monotonic() - t0) * 1000)
    return out


def main() -> int:
    # --- input guard: a realistic business question, measured 50 times ---
    q = "What was the net revenue for the electronics category in the third quarter of 2025, and how does it compare to the same quarter in 2024?"
    guard_times = timed(lambda: input_guard(q), n=50)
    p50, p95 = statistics.median(guard_times), sorted(guard_times)[int(0.95 * len(guard_times)) - 1]
    print(f"input_guard: p50={p50:.2f}ms p95={p95:.2f}ms (n=50)")
    check("input_guard p95 stays well under a second (it must run before every model call)", p95 < 1000, f"{p95:.2f}ms")

    # --- SQL validator: all 51 real examples from the RAG sources, one pass ---
    examples = []
    for f in sorted((ROOT / "rag_sources").rglob("*.md")):
        text = f.read_text()
        for m in _PAT.finditer(text):
            examples.append(m.group(1).strip())
    check("found the expected 51 real SQL examples to time", len(examples) == 51, len(examples))
    t0 = time.monotonic()
    for sql in examples:
        max_rows = 50000 if "LIMIT 50000" in sql else 500
        validate_sql(sql, max_rows=max_rows)
    total_ms = (time.monotonic() - t0) * 1000
    print(f"validate_sql: {total_ms:.1f}ms total for 51 real examples ({total_ms/51:.2f}ms/query average)")
    check("validating all 51 real SQL examples takes well under a second combined",
          total_ms < 1000, f"{total_ms:.1f}ms")

    # --- live database: a real, representative read-only query, 10 round trips ---
    sql = (
        "SELECT pc.category_name, ROUND(SUM(soi.line_total), 2) AS net_revenue "
        "FROM sales_order_items soi JOIN sales_orders so ON so.order_id = soi.order_id "
        "JOIN products p ON p.product_id = soi.product_id "
        "JOIN product_categories pc ON pc.category_id = p.category_id "
        "WHERE so.status = 'Completed' AND so.order_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31' "
        "GROUP BY pc.category_name ORDER BY net_revenue DESC;"
    )
    db_times = []
    for _ in range(10):
        t0 = time.monotonic()
        result = psql_postgres_tool(sql, max_rows=500)
        db_times.append((time.monotonic() - t0) * 1000)
    check("the live database round trip returns real rows, not an error", "error" not in result and result["row_count"] > 0, result.get("error"))
    p50_db, p95_db = statistics.median(db_times), max(db_times)
    print(f"live DB round trip (psql subprocess, 10 runs): p50={p50_db:.1f}ms max={p95_db:.1f}ms")
    check(
        "a representative aggregate query comfortably fits inside the 8-second statement "
        "timeout (section 14) -- note: this path goes through the psql CLI stand-in, which "
        "has its own process-spawn overhead a real psycopg connection pool would not pay, "
        "so this is a conservative (slower) number, not an optimistic one",
        p95_db < 8000, f"{p95_db:.1f}ms",
    )

    # --- real isolated Pandas subprocess: a representative computation, 5 round trips ---
    code = "x = df.groupby('category')['units'].sum()\nresult = x.sort_values(ascending=False).to_dict()"
    df = [{"category": c, "units": i * 3} for i, c in enumerate((["A", "B", "C"] * 200))]
    pandas_times = []
    for _ in range(5):
        t0 = time.monotonic()
        out = pandas_tool(code, df=df)
        pandas_times.append((time.monotonic() - t0) * 1000)
    check("the real isolated Pandas subprocess returns a correct result, not an error", "error" not in out, out.get("error"))
    p50_pd, p95_pd = statistics.median(pandas_times), max(pandas_times)
    print(f"pandas_tool (real isolated subprocess, 5 runs): p50={p50_pd:.1f}ms max={p95_pd:.1f}ms")
    check(
        "a representative Pandas computation (process spawn + import pandas/numpy/scipy + "
        "exec + serialize) comfortably fits inside the 60-second request budget, with ample "
        "room left for a real model call",
        p95_pd < 10_000, f"{p95_pd:.1f}ms",
    )

    print(
        "\n[NOTE] No LLM-call latency is included above (no network access to Groq in this "
        "sandbox -- see the module docstring). A deployment with network access should add "
        "a p50/p95 measurement of the real router/subgraph/aggregator LLM calls against "
        "MAX_REQUEST_SECONDS=60s; that number, not any of the above, is what actually "
        "determines whether a real request finishes inside the budget."
    )
    print(f"\n{FAILURES} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
