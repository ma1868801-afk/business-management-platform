import numpy as np, pandas as pd, assemble as A, g_finalize as F
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
c = orders[orders.status == "Completed"].copy()
c["y"] = pd.to_datetime(c.order_date).dt.year; c["m"] = pd.to_datetime(c.order_date).dt.month
r = c.groupby(["branch_id", "m", "y"]).subtotal_amount.sum().unstack("y")
q = pd.DataFrame({"a": r[2024], "b": r[2025] / 1.10, "c": r[2026] / 1.21})
q["spread"] = q.max(axis=1) / q.min(axis=1)
print("cells", len(q), "feasible (spread<=1.5)", int((q.spread <= 1.5).sum()), " spread quantiles", q.spread.quantile([.5, .75, .9, .99]).round(2).to_dict())
print(q.spread.unstack().round(2).to_string())
