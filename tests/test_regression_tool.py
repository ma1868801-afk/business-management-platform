"""Exercises `app/tools/regression_tool.py` against synthetic histories covering every
history class (full/reduced/cold_start/insufficient/no_sales), the input-validation rules of
`05_security_and_guardrails.md` section 8, and the `reorder_advice` function. Also supports a
real end-to-end check against the live Phase 2 test database (see `main()`), pulling one
SKU's weekly demand with the INV-SQL-14 pattern and feeding it straight into the tool --
this is the integration proof that the tool works against real, irregular business data and
not only clean synthetic series.

Usage: python3 tests/test_regression_tool.py [--db]
  --db  also pull APPL-0004's real weekly history from the Phase 2 test cluster
        (/tmp/pgsock:54329) via psql and run it through the tool.
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.tools.regression_tool import regression_tool, reorder_advice  # noqa: E402

FAILURES = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global FAILURES
    status = "OK" if cond else "FAIL"
    if not cond:
        FAILURES += 1
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))


def make_hist(n_weeks, level=30, noise=4, zero_pct=0.0, start=datetime.date(2025, 1, 6), seed=1):
    rng = np.random.default_rng(seed)
    hist = []
    for i in range(n_weeks):
        wk = start + datetime.timedelta(weeks=i)
        units = max(0, round(level + rng.normal(0, noise)))
        if rng.random() < zero_pct:
            units = 0
        hist.append({"week_start_date": wk.isoformat(), "units_sold": units, "promo_units": 0, "stockout_days": 0})
    return hist


def run_synthetic():
    base = {"series_level": "sku_total", "entity": {"sku": "TEST"}, "horizon_weeks": 8,
             "interval": 0.8, "assumptions": {"promo": "none", "price": "current"},
             "with_reorder_advice": False}

    out = regression_tool({**base, "history": make_hist(90)})
    check("full history -> class full", out["history_class"] == "full")
    check("full history -> High confidence on clean seasonal data", out["confidence"] == "High", out["confidence"])
    check("full history -> 8 forecast rows", len(out["forecast"]) == 8)
    check("full history -> forecasts non-negative and ordered", all(r["lower"] <= r["forecast"] <= r["upper"] for r in out["forecast"]))

    out = regression_tool({**base, "history": make_hist(30)})
    check("30 weeks -> class reduced", out["history_class"] == "reduced", out["history_class"])
    check("reduced -> confidence capped at Medium", out["confidence"] in ("Medium", "Low"), out["confidence"])

    out = regression_tool({**base, "history": make_hist(12)})
    check("12 weeks -> class cold_start", out["history_class"] == "cold_start", out["history_class"])
    check("cold_start -> Low confidence", out["confidence"] == "Low")

    out = regression_tool({**base, "history": make_hist(5)})
    check("5 weeks -> class insufficient", out["history_class"] == "insufficient", out["history_class"])

    out = regression_tool({**base, "history": make_hist(10, level=0, noise=0)})
    check("all-zero history -> class no_sales, empty forecast", out["history_class"] == "no_sales" and out["forecast"] == [])

    # Input validation (05_security_and_guardrails.md section 8).
    bad = [
        ({**base, "history": make_hist(40), "foo": 1}, "schema_error"),
        ({**base, "history": make_hist(40), "series_level": "nope"}, "schema_error"),
        ({**base, "history": make_hist(40), "entity": {}}, "schema_error"),
        ({**base, "history": [{"week_start_date": "2026-01-05", "units_sold": -5, "promo_units": 0, "stockout_days": 0}]}, "schema_error"),
        ({**base, "history": make_hist(40), "interval": 0.99}, "schema_error"),
        ({**base, "history": make_hist(260)}, "schema_error"),
    ]
    for payload, expected_code in bad:
        out = regression_tool(payload)
        check(f"rejects bad input ({list(set(payload) - set(base))})", out.get("error", {}).get("code") == expected_code, str(out))

    out = regression_tool({**base, "history": make_hist(40), "horizon_weeks": 20})
    check("horizon_weeks clamped to 13", len(out["forecast"]) == 13 and "limited to 13" in out["notes"][0])

    # Reorder advice, standalone and wired through with_reorder_advice.
    ctx = {"available_stock": 100, "reorder_point": 80, "safety_stock": 40, "lead_time_days": 10,
           "min_order_quantity": 50, "quantity_on_order": 0, "lifecycle_status": "Active"}
    out = regression_tool({**base, "history": make_hist(60), "with_reorder_advice": True, "reorder_context": ctx})
    check("reorder advice attached when context supplied", "reorder_advice" in out)
    check("reorder advice recommends in multiples of MOQ", out["reorder_advice"]["recommended_order_units"] % ctx["min_order_quantity"] == 0)

    out = regression_tool({**base, "history": make_hist(60), "with_reorder_advice": True, "reorder_context": None})
    check("no reorder_context -> advice skipped with a warning, not crashed", "reorder_advice" not in out and out["warnings"])

    disc_ctx = {**ctx, "lifecycle_status": "Discontinued"}
    adv = reorder_advice([{"forecast": 10}] * 8, disc_ctx)
    check("discontinued SKU -> never recommends an order", adv["recommended_order_units"] == 0 and adv["reason"] == "discontinued")

    plenty_ctx = {**ctx, "available_stock": 100000}
    adv = reorder_advice([{"forecast": 10}] * 8, plenty_ctx)
    check("huge stock on hand -> no order recommended", adv["recommended_order_units"] == 0, str(adv))


def run_db_integration():
    pgargs = ["psql", "-h", "/tmp/pgsock", "-p", "54329", "-U", "bmp_readonly", "-d", "bmp"]
    sql = """
WITH weeks AS (
  SELECT DISTINCT week_start_date FROM calendar
  WHERE week_start_date BETWEEN DATE '2024-01-07' AND DATE '2026-10-25'
), demand AS (
  SELECT week_start_date, SUM(units_sold) AS units_sold, SUM(promo_units) AS promo_units
  FROM v_weekly_product_demand WHERE sku = 'APPL-0004' GROUP BY week_start_date
)
SELECT w.week_start_date, COALESCE(d.units_sold, 0), COALESCE(d.promo_units, 0)
FROM weeks w LEFT JOIN demand d ON d.week_start_date = w.week_start_date
ORDER BY w.week_start_date LIMIT 500;
"""
    proc = subprocess.run(pgargs + ["-t", "-A", "-F,", "-c", sql], capture_output=True, text=True,
                           env={"PGPASSWORD": "ro_test_pw"}, timeout=15)
    if proc.returncode != 0:
        check("db integration (APPL-0004 real history)", False, proc.stderr.strip()[:300])
        return
    hist = []
    for line in proc.stdout.strip().splitlines():
        wk, units, promo = line.split(",")
        hist.append({"week_start_date": wk, "units_sold": float(units), "promo_units": float(promo), "stockout_days": 0})

    out = regression_tool({
        "history": hist, "series_level": "sku_total", "entity": {"sku": "APPL-0004"},
        "horizon_weeks": 13, "interval": 0.8, "assumptions": {"promo": "none", "price": "current"},
        "with_reorder_advice": True,
        "reorder_context": {"available_stock": 60, "reorder_point": 50, "safety_stock": 20,
                             "lead_time_days": 14, "min_order_quantity": 24, "quantity_on_order": 0,
                             "lifecycle_status": "Active"},
    })
    check("real APPL-0004 history -> class full (147 weeks)", out["history_class"] == "full", out["history_class"])
    check("real APPL-0004 -> 13 forecast rows", len(out["forecast"]) == 13)
    check("real APPL-0004 -> reorder advice computed", "reorder_advice" in out)
    print(json.dumps({k: v for k, v in out.items() if k != "forecast"}, indent=2))


if __name__ == "__main__":
    run_synthetic()
    if "--db" in sys.argv:
        run_db_integration()
    print(f"\n{FAILURES} failure(s)")
    raise SystemExit(1 if FAILURES else 0)
