"""Fast pandas version of the main guarantees, used while calibrating the generator (the SQL script is the real check)."""
import numpy as np, pandas as pd
from scipy import stats


def run(S, orders, items, returns, targets, verbose=True):
    pr = {}
    o = orders.copy()
    o["year"] = pd.to_datetime(o.order_date).dt.year
    comp = o[o.status == "Completed"]
    it = items.merge(o[["order_id", "status", "year", "channel", "branch_id"]], on="order_id")
    itc = it[it.status == "Completed"]
    prod = pd.DataFrame(S["prods"])
    print("orders", len(o), "lines", len(items), "net revenue (Completed) M", round(comp.subtotal_amount.sum() / 1e6, 2),
          "AOV", round(comp.subtotal_amount.mean()))
    print("status:", (o.status.value_counts(normalize=True) * 100).round(2).to_dict())
    for y in (2024, 2025, 2026):
        c = comp[comp.year == y]
        t = c.subtotal_amount.sum()
        sh = c.groupby("channel").subtotal_amount.sum() / t
        print(y, "rev", round(t / 1e6, 2), "online+app", round(float(sh.get("Online", 0) + sh.get("Mobile App", 0)), 3), "b2b", round(float(sh.get("B2B", 0)), 3))
    r24, r25 = comp[comp.year == 2024].subtotal_amount.sum(), comp[comp.year == 2025].subtotal_amount.sum()
    d = pd.to_datetime(comp.order_date)
    y25 = comp[(comp.year == 2025) & (d.dt.month <= 10)].subtotal_amount.sum()
    y26 = comp[(comp.year == 2026)].subtotal_amount.sum()
    print("growth 2025/2024", round(r25 / r24 - 1, 3), " Jan-Oct 2026 vs 2025", round(y26 / y25 - 1, 3))
    st = comp[(comp.year == 2025) & (comp.branch_id <= 8)].groupby("branch_id").subtotal_amount.sum()
    print("2025 store revenue ranking", list(st.sort_values(ascending=False).index), "KHB/DMM", round(st[5] / st[4], 3), "OBH/ABH", round(st[7] / st[8], 3))
    cu = pd.DataFrame(S["custs"])
    ind = cu[cu.customer_type == "Individual"]
    print("tiers", (ind.loyalty_tier.value_counts(normalize=True) * 100).round(1).to_dict())
    c25 = comp[(comp.year == 2025) & comp.customer_id.notna()]
    c25 = c25.merge(cu[["customer_id", "customer_type"]], on="customer_id")
    per = c25[c25.customer_type == "Individual"].groupby("customer_id").size()
    print("repeat rate 2025 (>=2 orders among purchasers)", round(float((per >= 2).mean()) * 100, 1), "purchasers", len(per))
    # cohort retention for 2025 registrations
    reg = ind[(pd.to_datetime(ind.reg).dt.year == 2025)][["customer_id", "reg"]].copy()
    reg["m0"] = pd.to_datetime(reg.reg).dt.to_period("M")
    oc = comp[comp.customer_id.notna()][["customer_id", "order_date"]].copy()
    oc["om"] = pd.to_datetime(oc.order_date).dt.to_period("M")
    j = reg.merge(oc, on="customer_id")
    j["k"] = (j.om - j.m0).apply(lambda x: x.n)
    ret = j[(j.k >= 1) & (j.k <= 3)].groupby("customer_id").size()
    reg["ret"] = reg.customer_id.isin(ret.index)
    rr = reg.groupby("m0").ret.mean() * 100
    print("cohort re-order within 3 months: pooled", round(float(reg.ret.mean()) * 100, 1), "monthly min/max", round(float(rr.min()), 1), round(float(rr.max()), 1))
    # AOV by tier 2025
    j2 = c25.merge(cu[["customer_id", "loyalty_tier"]], on="customer_id")
    print("AOV by tier 2025", j2.groupby("loyalty_tier").subtotal_amount.mean().round(0).to_dict())
    for a, b in (("Gold", "Silver"),):
        print("Gold vs Silver Welch p", stats.ttest_ind(j2[j2.loyalty_tier == a].subtotal_amount, j2[j2.loyalty_tier == b].subtotal_amount, equal_var=False).pvalue)
    dm, kh = comp[(comp.year == 2025) & (comp.branch_id == 4)].subtotal_amount, comp[(comp.year == 2025) & (comp.branch_id == 5)].subtotal_amount
    print("DMM vs KHB AOV diff %", round((kh.mean() / dm.mean() - 1) * 100, 2), "p", round(stats.ttest_ind(dm, kh, equal_var=False).pvalue, 3))
    on = comp[(comp.year == 2025)]
    dig = on[on.channel.isin(["Online", "Mobile App"])].subtotal_amount
    ins = on[on.channel == "In-Store"].subtotal_amount
    print("digital AOV vs in-store +%", round((dig.mean() / ins.mean() - 1) * 100, 1))
    ins_all = o[o.channel == "In-Store"]
    print("anonymous share of in-store", round(float(ins_all.customer_id.isna().mean()) * 100, 2))
    cats = prod.set_index("product_id").category_id
    itc = itc.assign(cat=itc.product_id.map(cats))
    byc = itc.groupby("cat").agg(rev=("line_total", "sum"), cost=("line_cost", "sum"), units=("quantity", "sum"))
    byc["margin"] = (1 - byc.cost / byc.rev) * 100
    byc["rev_share"] = byc.rev / byc.rev.sum() * 100
    print(byc.round(1)[["rev_share", "units", "margin"]].T.to_string())
    print("promo share of orders", round(float(o.promotion_id.notna().mean()) * 100, 1))
    print("returns", len(returns), "by value %", round(float(returns.refund_amount.sum() / itc.line_total.sum()) * 100, 2))
    if targets is not None:
        t = targets.merge(comp.assign(ym=pd.to_datetime(comp.order_date).dt.to_period("M").dt.to_timestamp().dt.date)
                          .groupby(["branch_id", "ym"]).subtotal_amount.sum().reset_index(), left_on=["branch_id", "target_month"], right_on=["branch_id", "ym"])
        t["att"] = t.subtotal_amount / t.target_revenue
        print("attainment range", round(t.att.min(), 3), round(t.att.max(), 3), "n<0.9", int((t.att < 0.9).sum()), "n>1.1", int((t.att > 1.1).sum()))
