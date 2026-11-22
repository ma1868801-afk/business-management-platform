"""Development tool: score generator seeds against the main guarantees (margin = distance to the nearest bound / band width)."""
import sys, json, time, numpy as np, pandas as pd
from scipy import stats
import assemble as A, g_finalize as F, g_targets as T


def metrics(S, orders, items, returns):
    o = orders.copy()
    o["d"] = pd.to_datetime(o.order_date); o["y"] = o.d.dt.year; o["m"] = o.d.dt.month
    comp = o[o.status == "Completed"]
    M = {}
    M["orders"] = (len(o), 108000, 132000)
    M["lines"] = (len(items), 270000, 330000)
    rev = comp.subtotal_amount.sum() / 1e6
    M["revenue_M"] = (rev, 85, 95)
    M["aov"] = (comp.subtotal_amount.mean(), 700, 800)
    r = comp.groupby("y").subtotal_amount.sum()
    r25y = comp[(comp.y == 2025) & (comp.m <= 10)].subtotal_amount.sum()
    M["g25_pct"] = ((r[2025] / r[2024] - 1) * 100, 10.5, 13.5)
    M["g26_pct"] = ((r[2026] / r25y - 1) * 100, 7.5, 10.5)
    grp = np.where(comp.channel.isin(["Online", "Mobile App"]), "on", np.where(comp.channel == "B2B", "b2b", "in"))
    sh = comp.assign(g=grp).groupby(["y", "g"]).subtotal_amount.sum().unstack()
    sh = sh.div(sh.sum(axis=1), axis=0) * 100
    for y, (lo, hi) in {2024: (12.5, 15.5), 2025: (17.5, 20.5), 2026: (22.5, 25.5)}.items():
        M[f"online_{y}"] = (sh.loc[y, "on"], lo, hi)
        M[f"b2b_{y}"] = (sh.loc[y, "b2b"], 6.0, 9.0)
    st = comp[(comp.y == 2025) & (comp.branch_id <= 8)].groupby("branch_id").subtotal_amount.sum()
    M["khb_dmm"] = (st[5] / st[4], 0.92, 1.0)
    M["obh_abh"] = (st[7] / st[8], 1.10, 3.0)
    rank_ok = list(st.sort_values(ascending=False).index) == [1, 2, 3, 4, 5, 6, 7, 8]
    M["store_rank"] = (1.0 if rank_ok else 0.0, 0.5, 1.5)
    cu = pd.DataFrame(S["custs"]); ind = cu[cu.customer_type == "Individual"]
    tv = ind.loyalty_tier.value_counts(normalize=True) * 100
    for t, (lo, hi) in {"None": (43, 47), "Silver": (28, 32), "Gold": (16, 20), "Platinum": (5, 9)}.items():
        M[f"tier_{t}"] = (tv.get(t, 0), lo, hi)
    c25 = comp[(comp.y == 2025) & comp.customer_id.notna()].merge(cu[["customer_id", "customer_type", "loyalty_tier"]], on="customer_id")
    ci = c25[c25.customer_type == "Individual"]
    per = ci.groupby("customer_id").size()
    M["repeat_pct"] = ((per >= 2).mean() * 100, 30, 45)
    reg = ind[pd.to_datetime(ind.reg).dt.year == 2025][["customer_id", "reg"]].copy()
    reg["m0"] = pd.to_datetime(reg.reg).dt.to_period("M")
    oc = comp[comp.customer_id.notna()][["customer_id", "order_date"]].copy()
    oc["om"] = pd.to_datetime(oc.order_date).dt.to_period("M")
    j = reg.merge(oc, on="customer_id"); j["k"] = (j.om - j.m0).apply(lambda x: x.n)
    retained = j[(j.k >= 1) & (j.k <= 3)].customer_id.unique()
    reg["ret"] = reg.customer_id.isin(retained)
    rr = reg.groupby("m0").ret.mean() * 100
    M["cohort_min"] = (rr.min(), 25, 40); M["cohort_max"] = (rr.max(), 25, 40)
    aov = ci.groupby("loyalty_tier").subtotal_amount.mean()
    M["aov_order"] = (float(aov["Platinum"] > aov["Gold"] > aov["Silver"] > aov["None"]), 0.5, 1.5)
    p = stats.ttest_ind(ci[ci.loyalty_tier == "Gold"].subtotal_amount, ci[ci.loyalty_tier == "Silver"].subtotal_amount, equal_var=False).pvalue
    M["gold_silver_p"] = (p, 0, 0.05)
    c25a = comp[comp.y == 2025]
    dig = c25a[c25a.channel.isin(["Online", "Mobile App"])].subtotal_amount; ins = c25a[c25a.channel == "In-Store"].subtotal_amount
    M["digital_aov_uplift"] = ((dig.mean() / ins.mean() - 1) * 100, 15, 200)
    dm, kh = c25a[c25a.branch_id == 4].subtotal_amount, c25a[c25a.branch_id == 5].subtotal_amount
    M["dmm_khb_aov_diff"] = (abs(kh.mean() / dm.mean() - 1) * 100, 0, 2)
    M["dmm_khb_p"] = (stats.ttest_ind(dm, kh, equal_var=False).pvalue, 0.10, 1.0)
    insto = o[o.channel == "In-Store"]
    M["anon_pct"] = (insto.customer_id.isna().mean() * 100, 7, 9)
    M["promo_pct"] = (o.promotion_id.notna().mean() * 100, 20, 24)
    it = items.merge(o[["order_id", "status"]], on="order_id"); itc = it[it.status == "Completed"]
    M["return_value_pct"] = (returns.refund_amount.sum() / itc.line_total.sum() * 100, 3, 5)
    return M


def score(M):
    worst, bad = 9, []
    for k, (v, lo, hi) in M.items():
        mg = min(v - lo, hi - v) / (hi - lo)
        if mg < 0:
            bad.append(k)
        worst = min(worst, mg)
    return worst, bad


def run_seed(seed):
    S = A.run(seed=seed)
    rng = S["rng"]
    orders, items = F.finalize(S, rng)
    returns = F.make_returns(rng, S, orders, items)
    M = metrics(S, orders, items, returns)
    tg, df = T.make_targets(rng, orders)
    feas = df.a < df.z
    M["target_infeasible"] = (float((~feas).sum()), -0.5, 0.5)
    return M, score(M)


if __name__ == "__main__":
    seeds = [int(x) for x in sys.argv[1:]]
    for sd in seeds:
        t0 = time.time()
        M, (w, bad) = run_seed(sd)
        print(json.dumps(dict(seed=sd, worst=round(w, 3), bad=bad, secs=round(time.time() - t0, 1), M={k: round(float(v[0]), 3) for k, v in M.items()})), flush=True)
