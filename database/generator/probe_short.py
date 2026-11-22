import numpy as np, pandas as pd, assemble as A, g_finalize as F, g_inventory as I
from collections import Counter
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
returns = F.make_returns(rng, S, orders, items)
R = I.run(S, orders, items, returns, rng)
prods = S["prods"]
for name in ("sim_st", "sim_dc"):
    sim = R[name]
    sh = [(i, d, q) for (i, d, r, q) in sim["adj"] if r == "SHORT"]
    print(name, "SHORT", len(sh), "units", sum(q for _, _, q in sh))
    df = pd.DataFrame(sh, columns=["i", "d", "q"])
    df["year"] = (df.d // 365)
    print(" by year-ish", df.groupby("year").size().to_dict())
    df["lead"] = [int(sim["lead"][i]) for i in df.i]
    df["int"] = [bool(sim["internal"][i]) for i in df.i]
    print(" by internal", df.groupby("int").size().to_dict())
    print(" by lead", df.groupby("lead").size().to_dict())
    print(" top series", Counter(df.i).most_common(5))
    df["first_cycle"] = [d - int(sim["st"][i]) < int(sim["lead"][i]) + 10 for i, d in zip(df.i, df.d)]
    print(" within first cycle", int(df.first_cycle.sum()))
sim = R["sim_st"]
i = 294
print("series", i, "loc", sim["ser_l"][i], S["prods"][sim["ser_p"][i]]["sku"], "internal", sim["internal"][i], "lead", sim["lead"][i], "st", sim["st"][i], "cover", sim["cover"][i])
sh = [(d, q) for (j, d, r, q) in sim["adj"] if j == i and r == "SHORT"]
print(sh[:12])
D = sim["D"][i]; tr = sim["transfer"][i]
d0 = sh[3][0]
for t in range(d0 - 20, d0 + 3):
    print(t, "dow", I.WEEKDAY[t], "demand", D[t], "transfer ordered", tr[t])
print("snap tail", sim["snap"][i][-10:], "S_end", sim["S_end"][i])
