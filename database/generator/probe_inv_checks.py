import numpy as np, pandas as pd, assemble as A, g_finalize as F, g_inventory as I, g_invtables as T
from datetime import date
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
returns = F.make_returns(rng, S, orders, items)
R = I.run(S, orders, items, returns, rng)
tb = T.build(S, R, rng)
prods = S["prods"]; sku = [p["sku"] for p in prods]
lv, sn, po, poi, adj = tb["levels"], tb["snapshots"], tb["purchase_orders"], tb["purchase_order_items"], tb["stock_adjustments"]
lv["sku"] = [sku[p - 1] for p in lv.product_id]
print("dead SKUs with stock:", {s: int(lv[(lv.sku == s)].quantity_on_hand.sum()) for s in I.DEAD})
print("JED-THL (branch 2) has", [s for s in ("APPL-0002", "ELEC-0001") if ((lv.branch_id == 2) & (lv.sku == s)).any()])
# G-34
last = sn[sn.snapshot_date == date(2026, 10, 31)].merge(lv, on=["branch_id", "product_id"])
print("G-34 last snapshot == on hand:", bool((last.quantity_on_hand_x == last.quantity_on_hand_y).all()), len(last), "neg", int((sn.quantity_on_hand < 0).sum()))
per = sn.groupby(["branch_id", "product_id"]).size()
print("snapshots per series: max", int(per.max()), "series with 148:", int((per == 148).sum()), "of", len(per))
# G-33
d25 = sn[(sn.snapshot_date >= date(2025, 1, 1)) & (sn.snapshot_date <= date(2025, 12, 31)) & (sn.branch_id == 9) & (sn.stockout_days > 0)]
cnt = d25.groupby("product_id").size()
print("G-33 DC SKUs with >=3 stockout weeks in 2025:", int((cnt >= 3).sum()))
# zero sales in weeks with stockout_days = 7
it = items.merge(orders[["order_id", "branch_id", "order_date", "status"]], on="order_id")
it = it[it.status == "Completed"].copy()
it["wk_end"] = it.order_date.map(lambda d: d + pd.Timedelta(days=(5 - d.weekday()) % 7) if hasattr(d, "weekday") else d)
it["wk_end"] = pd.to_datetime(it.order_date) + pd.to_timedelta((5 - pd.to_datetime(it.order_date).dt.weekday) % 7, unit="D")
sales = it.groupby(["branch_id", "product_id", "wk_end"]).quantity.sum().reset_index()
sn7 = sn[sn.stockout_days == 7].copy(); sn7["wk_end"] = pd.to_datetime(sn7.snapshot_date)
m = sn7.merge(sales, on=["branch_id", "product_id", "wk_end"])
print("G-33 weeks with stockout_days=7:", len(sn7), "of which with sales:", len(m), "(units", int(m.quantity.sum()) if len(m) else 0, ")")
print("PO lines below MOQ:", int((poi.merge(po, on="po_id").assign(moq=lambda d: d.supplier_id.map(lambda s: S["sups"][s - 1]["min_order_qty"])).query("quantity_ordered < moq")).shape[0]))
rec = po[po.status.isin(["Received", "Partially Received"])]
rec = rec.assign(late=(pd.to_datetime(rec.actual_delivery_date) > pd.to_datetime(rec.expected_delivery_date)))
meas = 100 * (1 - rec.groupby("supplier_id").late.mean())
tgt = pd.Series({s["supplier_id"]: s["on_time_delivery_pct"] for s in S["sups"]})
print("G-35 max abs diff", round(float((meas - tgt).abs().max()), 2), "worst", (meas - tgt).abs().idxmax())
print("G-37 expiry w/o shelf life:", int(sum(1 for p in adj[adj.reason == "Expiry"].product_id if not prods[p - 1]["shelf_life_days"])))
