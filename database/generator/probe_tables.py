import time, sys, numpy as np, pandas as pd, assemble as A, g_finalize as F, g_inventory as I, g_invtables as T
t0 = time.time()
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
returns = F.make_returns(rng, S, orders, items)
R = I.run(S, orders, items, returns, rng)
tb = T.build(S, R, rng)
print("secs", round(time.time() - t0, 1))
lv = tb["levels"]
lv["status"] = T.status_of(lv)
print("levels", len(lv), lv.groupby("branch_id").size().tolist())
print(lv.status.value_counts().to_dict(), "healthy %", round((lv.status == "Healthy").mean() * 100, 1))
prods = S["prods"]
lv["lifecycle"] = [prods[p - 1]["lifecycle_status"] for p in lv.product_id]
print("discontinued with stock", sorted(set(prods[p - 1]["sku"] for p in lv[(lv.lifecycle == "Discontinued") & (lv.quantity_on_hand > 0)].product_id)))
print("snapshots", len(tb["snapshots"]))
po, poi = tb["purchase_orders"], tb["purchase_order_items"]
print("POs", len(po), "items", len(poi), po.status.value_counts().to_dict())
print("open+transit", int(po.status.isin(["Open", "In Transit"]).sum()))
adj = tb["stock_adjustments"]
print("adjustments", len(adj), adj.reason.value_counts().to_dict())
print("short corrections", sum(1 for sm in (R["sim_st"], R["sim_dc"]) for a in sm["adj"] if a[2] == "SHORT"))
print("stuck", int(R["sim_st"]["was_stuck"].sum()), int(R["sim_dc"]["was_stuck"].sum()))
sims = {"st": R["sim_st"], "dc": R["sim_dc"]}
lv["is_dc"] = lv.branch_id == 9
internal = {}
for key, sim in sims.items():
    for i in range(len(sim["ser_l"])):
        internal[(int(sim["ser_l"][i]) + 1, int(sim["ser_p"][i]) + 1)] = bool(sim["internal"][i])
lv["internal"] = [internal[(b, p)] for b, p in zip(lv.branch_id, lv.product_id)]
lv["lead"] = [S["sups"][prods[p - 1]["supplier_id"] - 1]["lead_time_days"] for p in lv.product_id]
print(pd.crosstab([lv.is_dc, lv.internal], lv.status))
print(pd.crosstab(pd.cut(lv.lead, [0, 7, 14, 24, 35, 50]), lv.status))
lv["sku"] = [prods[p - 1]["sku"] for p in lv.product_id]
lv["ratio"] = lv.quantity_on_hand / lv.safety_stock
print(lv[lv.status == "Critical"][["sku", "branch_id", "quantity_on_hand", "safety_stock", "reorder_point", "max_stock_level", "lead", "internal"]].head(15).to_string())
print(lv.groupby("status")[["safety_stock", "reorder_point", "reorder_quantity"]].median())
print("------ store internal reorder-now detail")
lv["rate"] = lv.reorder_point  # placeholder
x = lv[(lv.internal) & (~lv.is_dc)].copy()
x["rate90"] = [R["sim_st"]["D"][list(zip(R["sim_st"]["ser_l"] + 1, R["sim_st"]["ser_p"] + 1)).index((b, p))][-90:].mean() for b, p in zip(x.branch_id[:0], x.product_id[:0])] if False else 0
idx = {(int(R["sim_st"]["ser_l"][i]) + 1, int(R["sim_st"]["ser_p"][i]) + 1): i for i in range(len(R["sim_st"]["ser_l"]))}
x["rate90"] = [R["sim_st"]["D"][idx[(b, p)]][-90:].mean() for b, p in zip(x.branch_id, x.product_id)]
x["band"] = pd.cut(x.rate90, [-1, 0.0001, 0.1, 0.25, 0.5, 1, 100])
print(pd.crosstab(x.band, x.status))
print(x[x.status == "Reorder Now"][["sku", "branch_id", "quantity_on_hand", "safety_stock", "reorder_point", "max_stock_level", "rate90", "lead"]].head(12).to_string())
