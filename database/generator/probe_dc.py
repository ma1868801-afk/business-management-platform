import sys, numpy as np, pandas as pd, assemble as A, g_finalize as F, g_channels as GC, g_targets as T
from datetime import date
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
c = orders[orders.status == "Completed"].copy()
c["d"] = pd.to_datetime(c.order_date); c["y"] = c.d.dt.year; c["m"] = c.d.dt.month
c["grp"] = np.where(c.channel.isin(["Online", "Mobile App"]), "online", np.where(c.channel == "B2B", "b2b", "instore"))
yr = c.groupby(["y", "grp"]).subtotal_amount.sum().unstack() / 1e6
sh = (yr / yr.sum(axis=1).values[:, None] * 100).round(1)
jo = c[c.m <= 10].groupby(["y", "grp"]).subtotal_amount.sum().unstack() / 1e6
dc = (jo.online + jo.b2b)
print("share% full year: online", sh.online.tolist(), "b2b", sh.b2b.tolist(), "| total M", (yr.sum(axis=1)).round(2).tolist())
print("DC Jan-Oct M", dc.round(2).tolist(), "growth 26/24", round(dc[2026] / dc[2024], 3), "25/24", round(dc[2025] / dc[2024], 3), " total like-for-like 26/24", round(jo.sum(axis=1)[2026] / jo.sum(axis=1)[2024], 3))
tg, df = T.make_targets(rng, orders)
d9 = df[df.b == 9]
print("DC q25", d9.q25.round(2).tolist()); print("DC q26", d9.q26.round(2).tolist())
print("max DC q26 (must be <= 1.48):", round(d9.q26.max(), 3), " min", round(d9.q26.min(), 3))
tot = c.groupby(["y", c.m > 10]).subtotal_amount.sum().unstack() / 1e6
print("Jan-Oct vs Nov-Dec revenue M by year"); print(tot.round(2))
print("ND25/ND24", round(tot.loc[2025, True] / tot.loc[2024, True], 3), " JO25/JO24", round(tot.loc[2025, False] / tot.loc[2024, False], 3), " JO26/JO25", round(tot.loc[2026, False] / tot.loc[2025, False], 3))
