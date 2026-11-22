import numpy as np, pandas as pd, assemble as A, g_finalize as F
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
cu = pd.DataFrame(S["custs"])
ind = cu[cu.customer_type == "Individual"]
print(pd.crosstab(ind.cls, ind.loyalty_tier, margins=True))
print(ind.groupby("cls").spend_ttm.describe(percentiles=[.1,.5,.9]).round(0))
tot = ind.spend_ttm.sum()
print("TTM identified individual spend M", round(tot/1e6,2))
comp = orders[orders.status=="Completed"]
d = pd.to_datetime(comp.order_date)
ttm = comp[d >= "2025-11-01"]
print("TTM total revenue M", round(ttm.subtotal_amount.sum()/1e6,2), " b2b M", round(ttm[ttm.channel=="B2B"].subtotal_amount.sum()/1e6,2),
      " anon M", round(ttm[ttm.customer_id.isna()].subtotal_amount.sum()/1e6,2))
m = comp.merge(cu[["customer_id","cls"]], on="customer_id", how="left")
m["cls"] = m.cls.fillna("anon")
print(m.groupby("cls").subtotal_amount.agg(["count","mean","sum"]).round(0))
