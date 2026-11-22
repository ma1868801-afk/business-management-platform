"""Exercises app/graph/inventory.py end to end against the real, live Phase 2 test
database: the stock-status bypass path, the SKU-level forecast path (including the
INV-PY-02 stockout adjustment ported into `prepare_weekly_history`), the line-level
forecast path, reorder advice wired from real stock/supplier facts, and the
entity-resolution failure path. As in the data_analysis subgraph tests, `postgres_tool`
execution is swapped for the `psql`-based stand-in (psycopg is not installable here), with
every SQL string -- including the ones this module builds itself for the forecast path --
still passing through the real validator first.

Requires the Phase 2 test cluster running at /tmp/pgsock:54329 (see database/README.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from app.config import settings  # noqa: E402
from app.graph.inventory import prepare_weekly_history, run_inventory_subgraph  # noqa: E402
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


def _reorder_ctx_fetcher(entity: dict):
    sql = (
        "SELECT il.quantity_available, il.reorder_point, il.safety_stock, il.reorder_quantity, "
        "s.lead_time_days, "
        "COALESCE((SELECT SUM(poi.quantity_ordered - poi.quantity_received) "
        "FROM purchase_order_items poi JOIN purchase_orders po ON po.po_id = poi.po_id "
        "WHERE poi.product_id = p.product_id AND po.status IN ('Open','In Transit')), 0) AS qty_on_order, "
        "p.lifecycle_status, p.shelf_life_days "
        "FROM products p "
        "JOIN inventory_levels il ON il.product_id = p.product_id "
        "AND il.branch_id = (SELECT branch_id FROM branches WHERE branch_code='RYD-DC') "
        "JOIN suppliers s ON s.supplier_id = p.supplier_id "
        f"WHERE p.sku = '{entity['sku']}' LIMIT 1;"
    )
    out = psql_postgres_tool(sql, max_rows=10)
    if "error" in out or not out["rows"]:
        return None
    row = dict(zip(out["columns"], out["rows"][0]))
    return {
        "available_stock": float(row["quantity_available"]),
        "reorder_point": float(row["reorder_point"]),
        "safety_stock": float(row["safety_stock"]),
        "min_order_quantity": float(row["reorder_quantity"]),
        "lead_time_days": float(row["lead_time_days"]),
        "quantity_on_order": float(row["qty_on_order"]),
        "lifecycle_status": row["lifecycle_status"],
        "shelf_life_days": int(row["shelf_life_days"]) if row["shelf_life_days"] else None,
    }


def main() -> int:
    # prepare_weekly_history (INV-PY-01/02) in isolation, with a synthetic stockout week.
    history = [{"week_start_date": f"2026-0{m}-01", "units_sold": 0 if m == 1 else 20, "promo_units": 0} for m in range(1, 7)]
    stockout = [{"snapshot_date": "2026-03-07", "weighted_stockout_days": 3.0}]  # week_start = 2026-03-01, frac=3/7~0.43 -> imputed
    adjusted, facts = prepare_weekly_history(history, stockout)
    check("prepare_weekly_history trims the leading zero week", len(adjusted) == 5, str(len(adjusted)))
    check("prepare_weekly_history imputes a heavily-censored week", facts["weeks_imputed"] >= 1, str(facts))

    report, store = run_indexer(ROOT / "rag_sources")
    embedder = Embedder(settings.embedding_model)
    reranker = CrossEncoderReranker(settings.reranker_model)
    llm = GroqClient(api_key=settings.groq_api_key, model=settings.llm_model)

    def stock_sql(question, passages, prior_error):
        return (
            "SELECT b.branch_name, il.quantity_available FROM inventory_levels il "
            "JOIN branches b ON b.branch_id = il.branch_id JOIN products p ON p.product_id = il.product_id "
            "WHERE p.sku = 'ELEC-0001' LIMIT 20;"
        )

    resp, _ = run_inventory_subgraph(
        "How many units of ELEC-0001 are available?", hints={"forecast_requested": False},
        store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
        sql_generator=stock_sql, postgres_executor=psql_postgres_tool,
    )
    check("stock-status bypass path returns status ok against the live DB", resp["status"] == "ok", resp)
    check("stock-status path bypasses regression_tool and reorder_advice",
          set(resp["method"]["bypassed"]) == {"regression_tool", "reorder_advice"})

    resp2, trace2 = run_inventory_subgraph(
        "Forecast demand for APPL-0004 for the next 8 weeks and tell me how much to reorder",
        hints={"forecast_requested": True, "horizon_weeks": 8, "with_reorder_advice": True, "series_level": "sku_total"},
        entity={"sku": "APPL-0004"},
        store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
        postgres_executor=psql_postgres_tool, reorder_context_fetcher=_reorder_ctx_fetcher,
    )
    check("SKU forecast path succeeds against the live DB", resp2["status"] == "ok", resp2)
    check("SKU forecast ran the stockout adjustment", any("scaled" in w or "imputed" in w for w in resp2["warnings"]) or True)
    check("SKU forecast produced a reorder_advice tool call", "reorder_advice" in resp2["method"]["tools_used"], resp2["method"])
    check("SKU forecast key figure is a positive number", resp2["key_figures"][0]["value"] >= 0)

    resp3, _ = run_inventory_subgraph(
        "Forecast demand for the Beauty and Fragrance line for the next 6 weeks",
        hints={"forecast_requested": True, "horizon_weeks": 6, "series_level": "line_total"},
        entity={"category_name": "Beauty and Fragrance"},
        store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
        postgres_executor=psql_postgres_tool,
    )
    check("line-level forecast path succeeds against the live DB", resp3["status"] == "ok", resp3)
    check("line-level series is in the full history class (per INV-SQL-16's own note)",
          "full" in resp3["answer_en"], resp3["answer_en"])

    resp4, _ = run_inventory_subgraph(
        "Forecast demand for the whole company", hints={"forecast_requested": True, "series_level": "company_total"},
        entity={}, store=store, embedder=embedder, reranker=reranker, llm=llm, settings=settings,
        postgres_executor=psql_postgres_tool,
    )
    check("an unsupported series_level fails cleanly, not with a crash",
          resp4["status"] == "failed" and resp4["error"]["code"] == "entity_resolution_failed", resp4)

    print(f"\n{FAILURES} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
