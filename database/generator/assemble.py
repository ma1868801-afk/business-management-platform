"""Assemble orders and lines (customers, channels, stores, anonymous and business orders, baskets)."""
import numpy as np
import g_reference as GR
import g_customers as GC
import g_orders as GO
import g_channels as GCH
import g_baskets as GB
import g_lines as GL
import g_steer as GS
import g_balance as GB2
import g_inventory as GI
from g_reference import DAYS, ND

DC = 8
ANON_OVER = 0.14      # anonymous orders are over-generated and trimmed to exactly 8 percent after steering


def run(seed=327, verbose=True):
    rng = np.random.default_rng(seed)
    branches = GR.branches()
    cats = GR.categories()
    sups = GR.suppliers()
    prods = GR.products(rng)
    price, events = GR.price_table(rng, prods)
    cal = GR.calendar_rows()
    custs = GC.build(rng)
    w_in, w_on, _ = GO.day_weights()
    season = np.array([c["season"] for c in cal])
    ci, di, ki, fi = GO.plan(rng, custs, w_in, w_on)
    ch = GCH.channels(rng, custs, ci, di, season, None)
    store = np.full(len(ci), DC, dtype=np.int16)
    ins = ch == GCH.CH_IN
    st, logm = GCH.stores(rng, custs, ci[ins], di[ins], season)
    store[ins] = st
    ad, ast = GCH.anon_orders(rng, di[ins], st, season, w_in, share=ANON_OVER)
    bc, bd = GCH.b2b_plan(rng, custs, np.cumsum(0.5 * (w_in + w_on)))
    day = np.concatenate([di, ad, bd]).astype(np.int32)
    O = dict(
        day=day,
        channel=np.concatenate([ch, np.zeros(len(ad), np.int8), np.full(len(bd), GCH.CH_B2B, np.int8)]),
        cust=np.concatenate([ci, np.full(len(ad), -1), bc]).astype(np.int32),
        kind=np.concatenate([ki, np.zeros(len(ad), np.int8), np.full(len(bd), 2, np.int8)]),
        store=np.concatenate([store, ast.astype(np.int16), np.full(len(bd), DC, np.int16)]),
        first=np.concatenate([fi == 1, np.zeros(len(ad) + len(bd), bool)]),
        prot=np.concatenate([fi > 0, np.zeros(len(ad) + len(bd), bool)]),
    )
    # sort orders chronologically (stable) so that order ids follow time
    o = np.lexsort((np.arange(len(day)), day))
    O = {k: v[o] for k, v in O.items()}
    n_c = len(custs)
    kappa = np.array([c["kappa"] for c in custs])
    aff = rng.normal(-0.061, 0.35, (n_c, 8))
    cls = np.array([c["cls"] for c in custs])
    model = GB.Model(rng, prods, price, cal)
    L = GL.build(rng, model, O, custs, aff, kappa, cls)
    (O, L), short = GS.steer(rng, custs, O, L)
    O, L = GS.fit_anon(rng, O, L)
    O, L, growth = GB2.calibrate_growth(rng, O, L, custs)
    build_fn = lambda O2: GL.build(rng, model, O2, custs, aff, kappa, cls)
    O, L, bal = GB2.balance(rng, O, L, custs, build_fn, w_in)
    O, L = GS.fit_anon(rng, O, L, weight=GB2.cell_weight(O, L))
    O, L = GB2.retime_b2b(rng, O, L, custs, build_fn)
    pairs = GS.empty_store_days(O)
    n_fill = len(pairs)
    if n_fill:
        O2 = GS.fill_arrays(pairs, O)
        L2 = build_fn(O2)
        O, L = GS.merge(O, L, O2, L2)
    state = dict(rng=rng, branches=branches, cats=cats, sups=sups, prods=prods, price=price, events=events, cal=cal,
                 custs=custs, O=O, L=L, n_fill=n_fill, balance=bal, growth=growth, steer_short=short, model=model, w_in=w_in, w_on=w_on, season=season, store_logm=logm)
    GI.plan_windows(rng, state)
    return state


def report(S):
    O, L, custs = S["O"], S["L"], S["custs"]
    n = len(O["day"])
    val = L["qty"] * L["price"] * (1 - L["disc"] / 100.0)
    rev_o = np.bincount(L["order"], weights=val, minlength=n)
    yr = np.array([DAYS[d].year for d in O["day"]])
    print("orders", n, "lines", len(L["order"]), "lines/order", round(len(L["order"]) / n, 2), "units/line", round(L["qty"].mean(), 2))
    print("gross revenue (all statuses)", round(rev_o.sum() / 1e6, 1), "M; AOV", round(rev_o.mean()))
    for y in (2024, 2025, 2026):
        m = yr == y
        ch = O["channel"][m]
        r = rev_o[m]
        print(y, "orders", int(m.sum()), "rev", round(r.sum() / 1e6, 2), "online+app", round(r[(ch == 1) | (ch == 2)].sum() / r.sum(), 3),
              "b2b", round(r[ch == 3].sum() / r.sum(), 3), "AOV", round(r.mean()), "promo share", round(float((O["promo"][m] >= 0).mean()), 3))
    cls = np.array([c["cls"] for c in custs])
    oc = np.where(O["cust"] >= 0, cls[np.maximum(O["cust"], 0)], "--")
    for c in ("PL", "GD", "SE", "SB", "NC", "NL", "--", "BZ"):
        m = oc == c
        if m.any():
            print(" class", c, "orders", int(m.sum()), "AOV", round(rev_o[m].mean()))


if __name__ == "__main__":
    S = run()
    report(S)
