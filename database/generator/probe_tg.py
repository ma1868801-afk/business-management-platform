import numpy as np, pandas as pd, assemble as A, g_finalize as F, g_targets as T
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
tg, df = T.make_targets(rng, orders)
df["feas"] = df.a < df.z
print("infeasible cells:", int((~df.feas).sum()), "of", len(df))
print(df[~df.feas][["b", "m", "q25", "q26", "a", "z"]].round(3).to_string())
print("q25 range", df.q25.min().round(3), df.q25.max().round(3), " q26 range", df.q26.min().round(3), df.q26.max().round(3))
# attainment with chosen targets
c = orders[orders.status == "Completed"].copy()
c["ym"] = pd.to_datetime(c.order_date).dt.to_period("M").astype(str)
rev = c.groupby(["branch_id", "ym"]).subtotal_amount.sum().reset_index()
tg["ym"] = pd.to_datetime(tg.target_month).dt.to_period("M").astype(str)
j = tg.merge(rev, on=["branch_id", "ym"], how="left")
j["att"] = j.subtotal_amount / j.target_revenue
print("rows", len(j), "att range", j.att.min().round(3), j.att.max().round(3), "<0.8", int((j.att < 0.8).sum()), ">1.2", int((j.att > 1.2).sum()), "<0.9", int((j.att < 0.9).sum()), ">1.1", int((j.att > 1.1).sum()))
o = j[j.ym == "2026-10"]
print("Oct 2026 att", o.att.round(3).tolist())
pd.set_option("display.width", 200)
print("q25 matrix (rows branch 1-9, cols month 1-12)")
print(df.pivot(index="b", columns="m", values="q25").round(2).to_string())
print("q26 matrix")
print(df.pivot(index="b", columns="m", values="q26").round(2).to_string())
c = orders[orders.status == "Completed"].copy()
c["d"] = pd.to_datetime(c.order_date); c["y"] = c.d.dt.year; c["m"] = c.d.dt.month
c["grp"] = np.where(c.channel.isin(["Online", "Mobile App"]), "online", np.where(c.channel == "B2B", "b2b", "instore"))
tot = c[c.m <= 10].groupby(["y", "grp"]).subtotal_amount.sum().unstack() / 1e6
print("Jan-Oct revenue M by group"); print(tot.round(2)); print((tot / tot.sum(axis=1).values[:, None] * 100).round(1))
print("growth like-for-like (Jan-Oct):", (tot.loc[2026] / tot.loc[2024]).round(2).to_dict())
yr = c.groupby(["y", "grp"]).subtotal_amount.sum().unstack() / 1e6
print("full year share %"); print((yr / yr.sum(axis=1).values[:, None] * 100).round(1))
