"""Post-processing of the order plan: spend steering (tier targets), anonymous-share fit and empty store-day fill."""
import numpy as np
from g_orders import TTM0
from g_reference import ND

LINE_KEYS = ("order", "prod", "qty", "price", "disc", "first")
STATUS_PAD = 1.015     # share of planned spend lost to cancelled / returned orders


def order_values(L, n):
    return np.bincount(L["order"], weights=L["qty"] * L["price"] * (1 - L["disc"] / 100.0), minlength=n)


def thin(O, L, keep):
    """Remove the orders where keep is False together with their lines; line order indices are re-based."""
    new = np.cumsum(keep) - 1
    lk = keep[L["order"]]
    L2 = {k: L[k][lk] for k in LINE_KEYS}
    L2["order"] = new[L2["order"]]
    L2["nl"] = L["nl"][keep]
    return {k: v[keep] for k, v in O.items()}, L2


def merge(O1, L1, O2, L2):
    """Append a second set of orders and lines and restore chronological order (stable)."""
    n1 = len(O1["day"])
    O = {k: np.concatenate([O1[k], O2[k]]) for k in O1}
    L = {k: np.concatenate([L1[k], L2[k]]) for k in LINE_KEYS}
    L["order"][len(L1["order"]):] += n1
    L["nl"] = np.concatenate([L1["nl"], L2["nl"]])
    o = np.lexsort((np.arange(len(O["day"])), O["day"]))
    rank = np.empty_like(o)
    rank[o] = np.arange(len(o))
    O = {k: v[o] for k, v in O.items()}
    L["order"] = rank[L["order"]]
    ls = np.argsort(L["order"], kind="stable")
    L = {k: (L[k][ls] if k in LINE_KEYS else L[k][o]) for k in L}
    return O, L


def steer(rng, custs, O, L):
    """For PL / GD / SE customers keep just enough of the over-planned trailing-12-month orders to reach the spend target."""
    n = len(O["day"])
    val = order_values(L, n)
    cust, day = O["cust"], O["day"]
    keep = np.ones(n, bool)
    idx = np.where((day >= TTM0) & (cust >= 0) & (O["kind"] == 0))[0]
    idx = idx[np.argsort(cust[idx], kind="stable")]
    bounds = np.flatnonzero(np.diff(cust[idx])) + 1
    short = 0
    for grp in np.split(idx, bounds):
        if len(grp) == 0:
            continue
        c = custs[cust[grp[0]]]
        if c["cls"] not in ("PL", "GD", "SE"):
            continue
        T = c["target"] * STATUS_PAD
        prot = O["prot"][grp]
        base = val[grp][prot].sum()
        cand = grp[~prot]
        rng.shuffle(cand)
        cum = base + np.cumsum(val[cand])
        if base >= T:
            k = 0
        elif len(cand) == 0 or cum[-1] < T:
            k = len(cand)
            short += 1
        else:
            j = int(np.searchsorted(cum, T))               # cum[j] >= T
            prev = cum[j - 1] if j > 0 else base
            k = j if (prev >= 0.985 * T and (T - prev) < (cum[j] - T)) else j + 1
        keep[cand[k:]] = False
    return thin(O, L, keep), short


def fit_anon(rng, O, L, share=0.08, weight=None):
    """Drop surplus anonymous in-store orders so that exactly `share` of in-store orders are anonymous. With `weight` (one value
    per order) the orders to drop are drawn with probability proportional to the weight, otherwise uniformly."""
    ins = O["channel"] == 0
    anon = np.where(ins & (O["cust"] < 0))[0]
    ident = int((ins & (O["cust"] >= 0)).sum())
    want = int(round(share / (1 - share) * ident))
    keep = np.ones(len(O["day"]), bool)
    if len(anon) > want:
        p = None if weight is None else weight[anon] / weight[anon].sum()
        keep[rng.choice(anon, size=len(anon) - want, replace=False, p=p)] = False
    return thin(O, L, keep)


def empty_store_days(O, dc=8):
    seen = np.zeros((9, ND), bool)
    seen[O["store"], O["day"]] = True
    return np.argwhere(~seen)            # (store, day) pairs without any order


def fill_arrays(pairs, O):
    """Anonymous in-store orders for store-days without orders (the distribution centre gets an online-style anonymous-free order)."""
    st, d = pairs[:, 0], pairs[:, 1]
    n = len(d)
    return dict(day=d.astype(np.int32), channel=np.zeros(n, np.int8), cust=np.full(n, -1, np.int32), kind=np.zeros(n, np.int8),
                store=st.astype(np.int16), first=np.zeros(n, bool), prot=np.zeros(n, bool))
