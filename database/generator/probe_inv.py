import time, numpy as np, pandas as pd, assemble as A, g_finalize as F, g_inventory as I
t0 = time.time()
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
returns = F.make_returns(rng, S, orders, items)
for p in S["prods"]:
    pass
Dm, Rm, Res = I.demand_arrays(S, orders, items, returns)
ls, ps = I.choose_series(rng, S, Dm)
print("series", len(ls), "built", round(time.time() - t0, 1))
adj = I.adjustment_plan(rng, S, ls, ps, Dm)

w = Dm[:, :, -365:].sum(axis=2)[ls, ps] / 52.0
moq = np.array([S["sups"][S["prods"][q]["supplier_id"] - 1]["min_order_qty"] for q in ps])
internal = (ls != I.DC) & (moq > 10 * w)
print("store series", int((ls != I.DC).sum()), "internal", int(internal.sum()))
st_idx = np.where(ls != I.DC)[0]; dc_idx = np.where(ls == I.DC)[0]
sim_st = I.simulate(rng, S, ls[st_idx], ps[st_idx], Dm, Rm, np.ones(16), np.array([], dtype=int), [(0, 0, "Shrinkage", 0)], internal=internal[st_idx])
Dx = np.zeros((len(dc_idx), I.ND), dtype=np.int64)
pmap = {p: i for i, p in enumerate(ps[dc_idx])}
for k, i in enumerate(st_idx):
    if internal[i]:
        Dx[pmap[ps[i]]] += sim_st["transfer"][k]
print("transfers total units", int(Dx.sum()), "vs DC own demand", int(Dm[I.DC].sum()))
sim = I.simulate(rng, S, ls[dc_idx], ps[dc_idx], Dm, Rm, np.ones(16), np.array([], dtype=int), [(0, 0, "Shrinkage", 0)], Dx=Dx)
for name, sm in (("stores", sim_st), ("dc", sim)):
    ev = pd.DataFrame(sm["events"], columns=["s", "t", "qo", "qr", "exp", "act", "canc", "part"])
    short = [a for a in sm["adj"] if a[2] == "SHORT"]
    g = ev.groupby([sm["sup"][ev.s], sm["ser_l"][ev.s], ev.t]).size() if len(ev) else []
    print(name, "events", len(ev), "POs", len(g), "shortfalls", len(short), "series affected", len({a[0] for a in short}), "zero end", int((sm["S_end"] == 0).sum()))
