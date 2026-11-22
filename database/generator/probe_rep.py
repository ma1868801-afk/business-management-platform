import numpy as np, pandas as pd, assemble as A, g_finalize as F
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
cu = pd.DataFrame(S["custs"])
o = orders[(orders.status == "Completed") & orders.customer_id.notna()].copy()
o["y"] = pd.to_datetime(o.order_date).dt.year
c25 = o[o.y == 2025].groupby("customer_id").size().rename("n").reset_index()
c25 = c25.merge(cu[["customer_id", "cls", "customer_type", "reg"]], on="customer_id")
c25 = c25[c25.customer_type == "Individual"]
c25["rep"] = c25.n >= 2
c25["ry"] = pd.to_datetime(c25.reg).dt.year.clip(upper=2025)
print(c25.groupby("cls").agg(purch=("n", "size"), repeaters=("rep", "sum"), rate=("rep", "mean"), mean_orders=("n", "mean")).round(3))
print(c25.groupby("ry").agg(purch=("n", "size"), rate=("rep", "mean")).round(3))
print("overall", round(c25.rep.mean() * 100, 2), len(c25))
