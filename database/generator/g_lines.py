"""Order lines: sampling, quantities, promotions and discounts."""
import numpy as np
import registry as R
from g_reference import DAYS, ND, DAY_INDEX
import g_baskets as GB
from g_baskets import CATS, QTY_MU

CH_IN, CH_ON, CH_APP, CH_B2B = 0, 1, 2, 3
BIG_MIN = 3150.0
NC_PRICE_CAP = 650.0


def build(rng, model, O, custs, aff, kappa, cls):
    """O: dict of order arrays (day, channel, cust, kind). Returns line dict and fills O['promo'] (promotion index or -1)."""
    n = len(O["day"])
    day, ch, cust, kind = O["day"], O["channel"], O["cust"], O["kind"]
    online = (ch == CH_ON) | (ch == CH_APP)
    nl = np.where(online, 1 + rng.poisson(1.95, n), 1 + rng.poisson(1.45, n))
    nl = np.clip(nl, 1, 8)
    is_nc = np.array([(cls[c] == "NC") if c >= 0 else False for c in cust])
    nl[is_nc] = np.minimum(nl[is_nc], 3)
    big = kind == 1
    nl[big] = np.clip(rng.poisson(0.8, big.sum()), 0, 2) + 1
    biz = kind == 2
    nl[biz] = rng.integers(3, 9, biz.sum())
    # --- expand
    order = np.repeat(np.arange(n), nl)
    m = len(order)
    first = np.zeros(m, bool)
    first[np.cumsum(nl) - nl] = True
    ld = day[order]
    lon = online[order].astype(float)
    kap = np.where(cust[order] >= 0, kappa[np.maximum(cust[order], 0)], -0.1)
    arows = np.where((cust[order] >= 0)[:, None], aff[np.maximum(cust[order], 0)], 0.0)
    cap = np.where(is_nc[order], NC_PRICE_CAP, np.inf)
    # business orders get their own sampler below; sample everything else here
    normal_lines = ~biz[order]
    prod = np.zeros(m, dtype=np.int32)
    idx = np.where(normal_lines)[0]
    prod[idx] = model.sample_products(rng, ld[idx], lon[idx], arows[idx], kap[idx], price_cap=cap[idx])
    # big-ticket orders: first line is a big item
    skus = model.sku
    big_idx = np.array([skus.index(s) for s in GB.BIG_SKUS])
    wbig = np.array([3.0, 1.4, 1.6, 1.6])
    fl = np.where(first & big[order])[0]
    prod[fl] = big_idx[rng.choice(len(big_idx), size=len(fl), p=wbig / wbig.sum())]
    price = model.price[prod, ld]
    pf = np.minimum(1.0, (150.0 / price) ** 0.8)         # expensive items are rarely bought in multiples
    qty = 1 + rng.poisson(np.array([QTY_MU[CATS[model.cat[p]]] for p in range(model.P)])[prod] * pf)
    qty = np.where(online[order], qty + (rng.random(m) < 0.08 * pf), qty)
    # business orders
    bl = np.where(biz[order])[0]
    if len(bl):
        by_cat = {k: np.where(model.cat == k)[0] for k in range(8)}
        for o in np.unique(order[bl]):
            c = custs[cust[o]]
            focus = [CATS.index(l[1]) for l in R.LINES if l[2] in c["biz"]["focus"]]
            cand = np.concatenate([by_cat[k] for k in focus])
            sel = np.where(order == o)[0]
            d = day[o]
            w = np.exp(model.log_base[cand, d])
            w = np.where(np.isfinite(w), w, 0)
            if w.sum() == 0:
                w = np.ones(len(cand))
            pk = cand[rng.choice(len(cand), size=len(sel), p=w / w.sum())]
            prod[sel] = pk
            price[sel] = model.price[pk, d]
            vline = np.exp(rng.normal(np.log(1000), 0.65, len(sel)))
            qty[sel] = np.clip(np.round(vline / price[sel]), 2, 80).astype(int)
    # big orders: top up the big item so that the list value reaches the threshold
    if big.any():
        val = np.bincount(order, weights=qty * price, minlength=n)
        short = np.where(big & (val < BIG_MIN))[0]
        for o in short:
            f = np.where((order == o) & first)[0][0]
            qty[f] += int(np.ceil((BIG_MIN - val[o]) / price[f]))
    list_val = qty * price
    basket = np.bincount(order, weights=list_val, minlength=n)
    # --- promotions
    promo = np.full(n, -1, dtype=np.int32)
    pbest = np.zeros(n)
    disc = np.zeros(m)
    plinemask = np.zeros(m, bool)
    cat_line = model.cat[prod]
    pr_day = lambda d: DAY_INDEX[d]
    for j, p in enumerate(R.PROMOTIONS):
        a, b = pr_day(p["start"]), pr_day(p["end"])
        om = (kind == 0) & (day >= a) & (day <= b)
        if p["scope"] == "In-Store":
            om &= ch == CH_IN
        elif p["scope"] == "Online":
            om &= online
        if not om.any():
            continue
        em = om[order]
        if p["line"]:
            em &= cat_line == CATS.index(p["line"])
        elig = np.bincount(order[em], weights=list_val[em], minlength=n)
        ok = om & (elig > 0)
        if p["min_basket"]:
            ok &= basket >= p["min_basket"]
        score = np.where(ok, p["pct"] * elig, 0.0)
        better = score > pbest
        promo[better] = j
        pbest[better] = score[better]
    up = np.where([(R.PROMOTIONS[j]["line"] is not None) if j >= 0 else False for j in promo], GB.PROMO_UPTAKE_LINE, GB.PROMO_UPTAKE_STORE)
    take = (promo >= 0) & (rng.random(n) < up)
    promo = np.where(take, promo, -1)
    for j in np.unique(promo[promo >= 0]):
        p = R.PROMOTIONS[j]
        sel = (promo[order] == j)
        if p["line"]:
            sel &= cat_line == CATS.index(p["line"])
        disc[sel] = p["pct"]
        plinemask |= sel
    # quantity uplift on promotional lines
    mu = np.array([QTY_MU[CATS[model.cat[p]]] for p in range(model.P)])[prod]
    ql = np.where(plinemask)[0]
    qty[ql] = 1 + rng.poisson((mu[ql] * GB.PROMO_QTY_MULT + GB.PROMO_QTY_ADD) * pf[ql])
    # clearance on discontinued and declining items (not on big or business orders, not on promotional lines)
    status = np.array([p["lifecycle_status"] for p in model.prods])[prod]
    ddate = np.array([DAY_INDEX[p["discontinued_date"]] if p["discontinued_date"] else 10 ** 6 for p in model.prods])[prod]
    clr10 = (status == "Discontinued") & (ld >= ddate - 90) & ~plinemask & (kind[order] == 0)
    clr5 = (status == "Declining") & ~plinemask & (kind[order] == 0) & (rng.random(m) < 0.4)
    disc[clr5] = 5.0
    disc[clr10] = 10.0
    # business contract discount
    for o in np.unique(order[bl]) if len(bl) else []:
        sel = order == o
        disc[sel] = custs[cust[o]]["biz"]["discount"]
        qty[sel] = qty[sel]
    O["promo"] = promo
    return dict(order=order, prod=prod, qty=qty.astype(int), price=price, disc=disc, first=first, nl=nl)
