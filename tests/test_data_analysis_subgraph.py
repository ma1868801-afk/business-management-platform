"""Exercises app/graph/data_analysis.py end to end against the real, live Phase 2 test
database: the retry-on-validation-failure loop, retry exhaustion, the bypass-vs-pandas
branch, and response formatting. `generate_sql`/`generate_pandas_code` are stubbed (see the
module docstring in data_analysis.py for why -- they are the two LLM-driven steps, and this
sandbox has no LLM); `postgres_tool` execution is swapped for the `psql`-based stand-in in
`tests/psql_executor.py` because `psycopg` cannot be installed here, but every SQL string
still passes through the real validator first, exactly as the real tool does.

Requires the Phase 2 test cluster running at /tmp/pgsock:54329 (see database/README.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from app.config import settings  # noqa: E402
from app.graph.data_analysis import run_data_analysis_subgraph  # noqa: E402
from app.llm.client import GroqClient  # noqa: E402
from app.rag.embeddings import Embedder  # noqa: E402
from app.rag.indexer import run_indexer  # noqa: E402
from app.rag.reranker import CrossEncoderReranker  # noqa: E402
from psql_executor import psql_postgres_tool  # noqa: E402

FAILURES = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    status = "OK" if cond else "FAIL"
    if not cond:
        FAILURES += 1
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))


def main() -> int:
    report, store = run_indexer(ROOT / "rag_sources")
    embedder = Embedder(settings.embedding_model)
    reranker = CrossEncoderReranker(settings.reranker_model)
    llm = GroqClient(api_key=settings.groq_api_key, model=settings.llm_model)

    def good_monthly_revenue(question, passages, prior_error):
        return (
            "SELECT date_trunc('month', order_date)::date AS order_month, "
            "ROUND(SUM(line_total), 2) AS net_revenue_sar FROM v_sales_detail "
            "WHERE status = 'Completed' AND order_date BETWEEN DATE '2024-01-01' AND DATE '2026-10-31' "
            "GROUP BY 1 ORDER BY 1 LIMIT 500;"
        )

    resp, trace = run_data_analysis_subgraph(
        "What is the monthly net revenue trend?", hints={"needs_computation": False},
        store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
        sql_generator=good_monthly_revenue, postgres_executor=psql_postgres_tool,
    )
    check("bypass path returns status ok against the live DB", resp["status"] == "ok", resp)
    check("bypass path records pandas_tool as bypassed", resp["method"]["bypassed"] == ["pandas_tool"])
    check("bypass path cites v_sales_detail", any(s["name"] == "v_sales_detail" for s in resp["sources"]))

    calls = {"n": 0}

    def retry_then_succeed(question, passages, prior_error):
        calls["n"] += 1
        if calls["n"] == 1:
            return "SELECT * FROM customers"  # fails the validator (V-06/V-07/V-09)
        return "SELECT order_id, line_total FROM v_sales_detail WHERE status='Completed' LIMIT 20"

    resp2, trace2 = run_data_analysis_subgraph(
        "Show some completed order totals", hints={}, store=store, embedder=embedder, reranker=reranker,
        llm=llm, settings=settings, sql_generator=retry_then_succeed, postgres_executor=psql_postgres_tool,
    )
    check("validator rejection triggers a regeneration retry, not an immediate failure", resp2["status"] == "ok", resp2)
    check("retry count is recorded", resp2["method"]["queries"] == 2 and calls["n"] == 2)

    def always_invalid(question, passages, prior_error):
        return "DROP TABLE customers"

    resp3, trace3 = run_data_analysis_subgraph(
        "Drop the customers table", hints={}, store=store, embedder=embedder, reranker=reranker,
        llm=llm, settings=settings, sql_generator=always_invalid, postgres_executor=psql_postgres_tool,
    )
    check("retry budget is exhausted and the node fails cleanly (never executes a write)",
          resp3["status"] == "failed" and resp3["error"]["code"] == "sql_failed", resp3)
    check("retry budget matches settings.sql_regen_limit + 1 attempts",
          resp3["method"]["queries"] == settings.sql_regen_limit + 1, resp3["method"])

    def october_sql(question, passages, prior_error):
        return (
            "SELECT order_id, line_total FROM v_sales_detail WHERE status='Completed' "
            "AND order_date >= DATE '2026-10-01' LIMIT 500"
        )

    def sum_revenue_pandas(question, sql_result, prior_error):
        return 'result = df["line_total"].astype(float).sum()\nfacts = {"total_oct_revenue": float(result)}'

    resp4, trace4 = run_data_analysis_subgraph(
        "What is total revenue in October 2026?", hints={"needs_computation": True},
        store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
        sql_generator=october_sql, postgres_executor=psql_postgres_tool, pandas_generator=sum_revenue_pandas,
    )
    check("needs_computation routes through both postgres_tool and pandas_tool",
          resp4["method"]["tools_used"] == ["postgres_tool", "pandas_tool"] and resp4["status"] == "ok", resp4)
    check("pandas facts become key_figures", resp4["key_figures"] and resp4["key_figures"][0]["label"] == "total_oct_revenue")
    check("key_figure value is a positive real number from the live DB", resp4["key_figures"][0]["value"] > 0)

    def no_rows_sql(question, passages, prior_error):
        return "SELECT order_id FROM v_sales_detail WHERE order_date > DATE '2099-01-01' LIMIT 10"

    resp5, _ = run_data_analysis_subgraph(
        "Revenue after the year 2099", hints={}, store=store, embedder=embedder, reranker=reranker,
        llm=llm, settings=settings, sql_generator=no_rows_sql, postgres_executor=psql_postgres_tool,
    )
    check("an empty result is reported as 'no matching data', not fabricated", resp5["status"] == "ok" and "No matching data" in resp5["answer_en"], resp5)

    def no_llm_sql(question, passages, prior_error):
        return None  # simulates the real default generator when the LLM is unavailable

    resp6, _ = run_data_analysis_subgraph(
        "Any question", hints={}, store=store, embedder=embedder, reranker=reranker,
        llm=llm, settings=settings, sql_generator=no_llm_sql, postgres_executor=psql_postgres_tool,
    )
    check("no SQL generator available -> clean llm_unavailable failure, not a crash",
          resp6["status"] == "failed" and resp6["error"]["code"] == "llm_unavailable", resp6)

    print(f"\n{FAILURES} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
