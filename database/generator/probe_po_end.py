import numpy as np, pandas as pd, assemble as A, g_finalize as F, g_inventory as I
S = A.run(); rng = S["rng"]
orders, items = F.finalize(S, rng)
returns = F.make_returns(rng, S, orders, items)
R = I.run(S, orders, items, returns, rng)
END = I.END
for name in ("sim_st", "sim_dc"):
    sim = R[name]
    ev = pd.DataFrame(sim["events"], columns=["i", "od", "qo", "qr", "ex", "act", "canc", "part"])
    ev["age"] = END - ev.od
    print(name, "events", len(ev), "od in last 14d", int((ev.age < 14).sum()), "last 28d", int((ev.age < 28).sum()), "last 56d", int((ev.age < 56).sum()),
          "act>END", int((ev.act > END).sum()), "ex>END", int((ev.ex > END).sum()))
    # orders per weekday in last 28 days
    last = ev[ev.age < 28]
    print(" POs (distinct sup/day) last 28d", last.assign(sup=sim["sup"][last.i.to_numpy()]).groupby(["sup", "od"]).ngroups)
    ns = len(sim["ser_l"])
    print(" series with pend at end", int((sim["pend_day"] >= 0).sum()), "of", ns, "; with stock 0 at end", int((sim["S_end"] == 0).sum()))
