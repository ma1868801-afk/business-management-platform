import numpy as np, pandas as pd, assemble as A, g_finalize as F
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
cu = pd.DataFrame(S["custs"])[["customer_id", "cls"]]
c = orders[orders.status == "Completed"].merge(cu, on="customer_id", how="left")
c["cls"] = c.cls.fillna("anon")
d = pd.to_datetime(c.order_date)
c["per"] = np.select([d.dt.year == 2024, d < "2025-11-01", d < "2026-01-01"], ["2024", "25JO", "25ND"], "26JO")
t = c.pivot_table(index="cls", columns="per", values="subtotal_amount", aggfunc="sum", margins=True).fillna(0) / 1e6
print(t.round(2)[["2024", "25JO", "25ND", "26JO", "All"]])
n = c.pivot_table(index="cls", columns="per", values="subtotal_amount", aggfunc="count", margins=True).fillna(0)
print(n[["2024", "25JO", "25ND", "26JO", "All"]].astype(int))
c25 = c[(pd.to_datetime(c.order_date).dt.year == 2025) & (c.cls != "anon") & (c.cls != "BZ")]
pc = c25.groupby(["cls", "customer_id"]).size().reset_index(name="n")
print(pc.groupby("cls").n.agg(purchasers="count", repeaters=lambda x: int((x >= 2).sum()), mean_orders="mean").round(1))
print("overall repeat rate", round(float((pc.n >= 2).mean()) * 100, 1), "purchasers", len(pc))
