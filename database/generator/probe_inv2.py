import time, numpy as np, pandas as pd, assemble as A, g_finalize as F, g_inventory as I
t0 = time.time()
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
returns = F.make_returns(rng, S, orders, items)
R = I.run(S, orders, items, returns, rng)
print("secs", round(time.time() - t0, 1))
sim = R["sim_dc"]; pm = {p: i for i, p in enumerate(R["ps"][R["dc_idx"]])}; frag = np.array([pm[p] for p in R["fr_prods"]])
y0, y1 = I.DAY_INDEX[I.date(2025, 1, 1)], I.DAY_INDEX[I.date(2025, 12, 31)]
wk0 = (y0 - I.SAT0) // 7 + 1; wk1 = (y1 - I.SAT0) // 7
so25 = (sim["so"][:, wk0:wk1 + 1] > 0).sum(axis=1)
print("fragile series", len(frag), "weeks with stockout in 2025:", so25[frag].tolist())
print("DC series with >=3 stockout weeks in 2025:", int((so25 >= 3).sum()))

n_po, n_late, tgt = R["counters"]
print("late share by supplier (order time)", np.round(n_late / np.maximum(n_po, 1) * 100, 1).tolist())
print("targets late %", np.round(tgt * 100, 1).tolist())
print("DC events", len(sim["events"]), "store events", len(R["sim_st"]["events"]))
print("n_po", n_po.astype(int).tolist())
from collections import Counter
print("fragile by supplier", sorted(Counter(S["prods"][p]["supplier_id"] for p in R["fr_prods"]).items()))
print("scripted late events", Counter(S["prods"][p]["supplier_id"] for p in R["fr_prods"] for i in [pm[p]] for (r, q, ex) in R["script"][i]["cycles"] if r > ex and r > 0))
