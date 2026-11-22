"""Phase 2 dataset builder: runs the whole seeded pipeline and returns one DataFrame per table, in schema column order.

    python3 build_dataset.py [seed]          build, run internal sanity checks and print row counts

The sales model and the stock model use separate random streams, so a change in one never reshuffles the other.
"""
import re
import sys
import time
import pathlib
import numpy as np
import pandas as pd
import registry as R
import assemble as A
import g_reference as GR
import g_finalize as F
import g_targets as T
import g_inventory as I
import g_invtables as IT

DEFAULT_SEED = 327
ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "database" / "sql" / "01_schema.sql"
ORDER = ["branches", "product_categories", "suppliers", "products", "customers", "promotions", "calendar",
         "monthly_sales_targets", "sales_orders", "sales_order_items", "sales_returns", "inventory_levels",
         "inventory_snapshots", "purchase_orders", "purchase_order_items", "stock_adjustments"]


def table_columns():
    """Column names of every table in the order of the CREATE TABLE statements (generated columns are left out)."""
    txt = SCHEMA.read_text()
    out = {}
    for m in re.finditer(r"CREATE TABLE (\w+) \((.*?)\n\);", txt, re.S):
        cols = []
        for line in m.group(2).split("\n"):
            line = line.strip()
            if not line or line.startswith("CONSTRAINT"):
                continue
            if "GENERATED ALWAYS" in line:
                continue
            cols.append(line.split()[0])
        out[m.group(1)] = cols
    return out


def build_all(seed=DEFAULT_SEED, verbose=True):
    t0 = time.time()
    S = A.run(seed=seed)
    rng = S["rng"]
    orders, items = F.finalize(S, rng)
    returns = F.make_returns(rng, S, orders, items)
    targets, _ = T.make_targets(rng, orders)
    irng = np.random.default_rng([seed, 17])                # independent stream for the stock model
    Rr = I.run(S, orders, items, returns, irng)
    tb = IT.build(S, Rr, irng)
    returns = Rr["returns"]
    if verbose:
        print("pipeline seconds", round(time.time() - t0, 1))

    br = pd.DataFrame(GR.branches())
    code_to_id = dict(zip(br.branch_code, br.branch_id))
    br = br.drop(columns=["weight"])
    cats = pd.DataFrame(GR.categories())
    sups = pd.DataFrame(GR.suppliers())
    prods = pd.DataFrame(S["prods"])
    promos = pd.DataFrame(GR.promotions())
    cal = pd.DataFrame(S["cal"])
    cu = pd.DataFrame(S["custs"])
    cu["preferred_branch_id"] = cu.store.map(code_to_id)
    cu["registration_date"] = cu.reg
    cust = cu
    orders = orders.copy()
    orders["order_timestamp"] = pd.to_datetime(orders.order_timestamp)

    tables = dict(branches=br, product_categories=cats, suppliers=sups, products=prods, customers=cust, promotions=promos,
                  calendar=cal, monthly_sales_targets=targets, sales_orders=orders, sales_order_items=items, sales_returns=returns,
                  inventory_levels=tb["levels"], inventory_snapshots=tb["snapshots"], purchase_orders=tb["purchase_orders"],
                  purchase_order_items=tb["purchase_order_items"], stock_adjustments=tb["stock_adjustments"])
    cols = table_columns()
    out = {}
    for name in ORDER:
        df = tables[name]
        missing = [c for c in cols[name] if c not in df.columns]
        assert not missing, (name, missing)
        out[name] = df[cols[name]].reset_index(drop=True)
    out["_state"] = S
    out["_stock"] = Rr
    return out


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SEED
    D = build_all(seed)
    for name in ORDER:
        print(f"{name:24s} {len(D[name]):>9,d}")
