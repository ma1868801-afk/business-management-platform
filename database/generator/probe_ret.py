import numpy as np, pandas as pd, assemble as A, g_finalize as F
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
cu = pd.DataFrame(S["custs"])
cu = cu[(cu.customer_type == "Individual") & (pd.to_datetime(cu.reg).dt.year == 2025)][["customer_id", "reg", "cls"]].copy()
cu["m0"] = pd.to_datetime(cu.reg).dt.to_period("M")
oc = orders[(orders.status == "Completed") & orders.customer_id.notna()][["customer_id", "order_date"]].copy()
oc["om"] = pd.to_datetime(oc.order_date).dt.to_period("M")
j = cu.merge(oc, on="customer_id")
j["k"] = (j.om - j.m0).apply(lambda x: x.n)
ret = j[(j.k >= 1) & (j.k <= 3)].customer_id.unique()
cu["ret"] = cu.customer_id.isin(ret)
print(cu.groupby("cls").ret.agg(["count", "mean"]).round(3))
print((cu.groupby("m0").ret.mean() * 100).round(1).to_dict())
nov = cu[cu.m0 == pd.Period("2025-11")]
print(nov.groupby("cls").ret.agg(["count", "mean"]))
bad = nov[(nov.cls.isin(["GD", "SE", "PL"])) & (~nov.ret)]
print(bad.head())
if len(bad):
    cid = bad.customer_id.iloc[0]
    print(orders[orders.customer_id == cid][["order_date", "status", "channel"]])
