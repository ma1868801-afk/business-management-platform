"""Location-month balancing: keeps every (location, month) revenue close to a common growth profile so that the monthly
sales targets of guarantee G-29 (same month of the previous year x 1.10, attainment 80-120 percent) are attainable."""
from datetime import date
import numpy as np
from g_reference import DAYS, ND, DAY_INDEX
from g_orders import TTM0
from g_steer import order_values, thin, merge

YEAR = np.array([d.year for d in DAYS]) - 2024
MONTH = np.array([d.month for d in DAYS]) - 1
GROWTH = np.array([1.0, 1.10, 1.21])
STEERED = ("PL", "GD", "SE")


def cells(O, val):
    R = np.zeros((9, 12, 3))
    np.add.at(R, (O["store"], MONTH[O["day"]], YEAR[O["day"]]), val)
    return R


def growth_profile(R):
    """Own year-on-year level of each location (2024 = 1): January-October for all three years, November-December for two."""
    tot = R[:, :10, :].sum(axis=1)
    nd = R[:, 10:, :2].sum(axis=1)
    G = np.ones((9, 2, 3))
    G[:, 0, :] = tot / tot[:, [0]]
    G[:, 1, :2] = nd / nd[:, [0]]
    return G                                    # (9, month group, 3)


def desired(R):
    G = growth_profile(R)
    D = np.zeros_like(R)
    for loc in range(9):
        for m in range(12):
            yrs = [y for y in range(3) if not (y == 2 and m > 9)]
            k = np.mean([max(R[loc, m, y], 1.0) / G[loc, int(m >= 10), y] for y in yrs])
            for y in yrs:
                D[loc, m, y] = k * G[loc, int(m >= 10), y]
    return D


def removable(O, custs_cls):
    """Orders that can be dropped without disturbing tiers, first orders or the forced return order."""
    cl = np.where(O["cust"] >= 0, custs_cls[np.maximum(O["cust"], 0)], "--")
    ok = ~O["prot"] & (O["kind"] == 0)
    steered_ttm = np.isin(cl, STEERED) & (O["day"] >= TTM0)
    return ok & ~steered_ttm


def balance(rng, O, L, custs, build_fn, w_in, lo=0.94, hi=1.06, passes=2):
    cls = np.array([c["cls"] for c in custs])
    stats = []
    for _ in range(passes):
        n = len(O["day"])
        val = order_values(L, n)
        R = cells(O, val)
        D = desired(R)
        rem = removable(O, cls)
        keep = np.ones(n, bool)
        loc, mo, yr = O["store"], MONTH[O["day"]], YEAR[O["day"]]
        add_days, add_store, b2b_days, b2b_cust = [], [], [], []
        b2b_aov = max(val[O['kind'] == 2].mean(), 3000.0) if (O['kind'] == 2).any() else 7000.0
        aov = max(val[(O["channel"] == 0) & (O["cust"] < 0)].mean(), 300.0)
        for l in range(9):
            for m in range(12):
                for y in range(3):
                    if D[l, m, y] == 0 or l == 8:
                        continue
                    ratio = R[l, m, y] / D[l, m, y]
                    if ratio > hi:
                        cand = np.where((loc == l) & (mo == m) & (yr == y) & rem)[0]
                        rng.shuffle(cand)
                        excess = R[l, m, y] - 1.02 * D[l, m, y]
                        cum = np.cumsum(val[cand])
                        j = int(np.searchsorted(cum, excess))
                        keep[cand[: min(j + 1, len(cand))]] = False
                    elif ratio < lo and l < 8:
                        need = 0.98 * D[l, m, y] - R[l, m, y]
                        k = int(round(need / aov))
                        if k <= 0:
                            continue
                        days = np.where((MONTH == m) & (YEAR == y))[0]
                        w = w_in[days] / w_in[days].sum()
                        add_days += list(rng.choice(days, size=k, p=w))
                        add_store += [l] * k
                    elif ratio < lo and l == 8:                      # distribution centre: add business orders
                        need = 0.98 * D[l, m, y] - R[l, m, y]
                        k = int(round(need / b2b_aov))
                        if k <= 0:
                            continue
                        days = np.array([d for d in np.where((MONTH == m) & (YEAR == y))[0] if (DAYS[d].weekday() + 1) % 7 not in (5, 6)])
                        for d in rng.choice(days, size=k):
                            live = [c["idx"] for c in custs if c["customer_type"] == "Business" and DAY_INDEX.get(c["reg"], -1) <= d]
                            if live:
                                b2b_days.append(int(d)); b2b_cust.append(int(rng.choice(live)))
        O, L = thin(O, L, keep)
        if add_days:
            O2 = dict(day=np.array(add_days, dtype=np.int32), channel=np.zeros(len(add_days), np.int8),
                      cust=np.full(len(add_days), -1, np.int32), kind=np.zeros(len(add_days), np.int8),
                      store=np.array(add_store, dtype=np.int16), first=np.zeros(len(add_days), bool), prot=np.zeros(len(add_days), bool))
            L2 = build_fn(O2)
            O, L = merge(O, L, O2, L2)
        if b2b_days:
            nb = len(b2b_days)
            O3 = dict(day=np.array(b2b_days, dtype=np.int32), channel=np.full(nb, 3, np.int8), cust=np.array(b2b_cust, dtype=np.int32),
                      kind=np.full(nb, 2, np.int8), store=np.full(nb, 8, np.int16), first=np.zeros(nb, bool), prot=np.zeros(nb, bool))
            L3 = build_fn(O3)
            O, L = merge(O, L, O3, L3)
        stats.append((int((~keep).sum()), len(add_days), len(b2b_days)))
    return O, L, stats


def spread_report(O, L):
    val = order_values(L, len(O["day"]))
    R = cells(O, val)
    G = growth_profile(R)
    q = np.full((9, 12), np.nan)
    for l in range(9):
        for m in range(12):
            yrs = [y for y in range(3) if not (y == 2 and m > 9)]
            v = np.array([R[l, m, y] / G[l, int(m >= 10), y] for y in yrs])
            q[l, m] = v.max() / v.min()
    return q


def calibrate_growth(rng, O, L, custs, g25=1.108, g26=1.09, tol=0.003):
    """Pins the year-on-year growth of G-10. The trailing-12-month revenue (November 2025 to October 2026) is anchored by the
    spend targets of the loyalty tiers; the earlier periods are over-planned and thinned here to the revenue implied by the
    target growth (2025 over 2024: 12 percent; January to October 2026 over the same months of 2025: 9 percent)."""
    n = len(O["day"])
    val = order_values(L, n)
    yr, mo = YEAR[O["day"]], MONTH[O["day"]]
    cls = np.array([c["cls"] for c in custs])
    rem = removable(O, cls)
    r26 = val[yr == 2].sum()
    nd25 = val[(yr == 1) & (mo >= 10)].sum()
    t25y = r26 / g26
    t24 = (t25y + nd25) / g25
    keep = np.ones(n, bool)
    out = {}
    for tag, seg, target in (("2025 Jan-Oct", (yr == 1) & (mo <= 9), t25y), ("2024", yr == 0, t24)):
        cur = val[seg].sum()
        out[tag] = (round(cur / 1e6, 3), round(target / 1e6, 3))
        if cur <= target * (1 + tol):
            continue
        cand = np.where(seg & rem)[0]
        rng.shuffle(cand)
        cum = np.cumsum(val[cand])
        excess = cur - target
        j = int(np.searchsorted(cum, excess))
        keep[cand[: min(j + 1, len(cand))]] = False
    O, L = thin(O, L, keep)
    return O, L, out


def cell_weight(O, L, power=6):
    """Per-order weight that is large where a (location, month) cell is above its desired level."""
    n = len(O["day"])
    R = cells(O, order_values(L, n))
    D = desired(R)
    ratio = np.where(D > 0, R / np.maximum(D, 1.0), 1.0)
    return np.clip(ratio[O["store"], MONTH[O["day"]], YEAR[O["day"]]], 0.3, 3.0) ** power


def _dc_shape(onl, nm):
    S = np.zeros(12)
    for m in range(12):
        S[m] = np.mean([onl[m, y] / onl[:10, y].sum() for y in range(3) if m < nm[y]])
    return S / S.sum()


def retime_b2b(rng, O, L, custs, build_fn):
    """Places the business orders of every year so that the revenue of the distribution centre (online, app and business) grows by the
    same factor in every month. The yearly count of business orders is unchanged; only their dates (and baskets) move. Online sales
    grow much faster than the 10 percent of the sales targets, and this is the only way to keep the monthly attainment of RYD-DC
    inside the band of guarantee G-29."""
    n = len(O["day"])
    val = order_values(L, n)
    yr, mo = YEAR[O["day"]], MONTH[O["day"]]
    on_dc = (O["store"] == 8) & ((O["channel"] == 1) | (O["channel"] == 2))
    b2b = O["kind"] == 2
    onl = np.zeros((12, 3))
    np.add.at(onl, (mo[on_dc], yr[on_dc]), val[on_dc])
    n_y = [int((b2b & (yr == y)).sum()) for y in range(3)]
    B = [float(val[b2b & (yr == y)].sum()) for y in range(3)]
    nm = [12, 12, 10]
    S = _dc_shape(onl, nm)
    X = onl[:, 0].sum() + B[0]
    x = S * X
    for _ in range(40):
        k25 = (onl[:, 1].sum() + B[1]) / X
        k26 = (onl[:10, 2].sum() + B[2]) / x[:10].sum()
        lb = np.maximum(onl[:, 0], onl[:, 1] / k25)
        lb[:10] = np.maximum(lb[:10], onl[:10, 2] / k26)
        lo_t, hi_t = 0.0, 4.0
        for _ in range(60):
            t = (lo_t + hi_t) / 2
            if np.maximum(lb, t * S * X).sum() > X:
                hi_t = t
            else:
                lo_t = t
        x = np.maximum(lb, lo_t * S * X)
        if x.sum() > X * 1.0001:                                  # not enough business revenue to level every month: scale down
            x = x * X / x.sum()
    k25 = (onl[:, 1].sum() + B[1]) / x.sum()
    k26 = (onl[:10, 2].sum() + B[2]) / x[:10].sum()
    need = {0: x - onl[:, 0], 1: k25 * x - onl[:, 1], 2: k26 * x[:10] - onl[:10, 2]}
    bus = [c for c in custs if c["customer_type"] == "Business"]
    wacct = np.array([c["credit_limit"] ** 0.75 for c in bus])
    cand_day, cand_cust, cand_cell = [], [], []
    for y in range(3):
        nd = np.maximum(need[y], 0.0)
        mean_val = B[y] / max(n_y[y], 1)
        for m in range(len(nd)):
            k = int(np.ceil(nd[m] / mean_val * 1.8)) + 3 if nd[m] > 0 else 0
            days = np.array([d for d in np.where((MONTH == m) & (YEAR == y))[0] if (DAYS[d].weekday() + 1) % 7 not in (5, 6)])
            for d in rng.choice(days, size=k):
                live = [j for j, c in enumerate(bus) if DAY_INDEX.get(c["reg"], -1) <= d]
                if not live:
                    live = list(range(len(bus)))
                p = wacct[live] / wacct[live].sum()
                cand_day.append(int(d)); cand_cust.append(bus[int(rng.choice(live, p=p))]["idx"]); cand_cell.append((y, m))
    nc = len(cand_day)
    O3 = dict(day=np.array(cand_day, dtype=np.int32), channel=np.full(nc, 3, np.int8), cust=np.array(cand_cust, dtype=np.int32),
              kind=np.full(nc, 2, np.int8), store=np.full(nc, 8, np.int16), first=np.zeros(nc, bool), prot=np.zeros(nc, bool))
    L3 = build_fn(O3)
    v3 = order_values(L3, nc)
    cell_of = {}
    for i, c in enumerate(cand_cell):
        cell_of.setdefault(c, []).append(i)
    pick = np.zeros(nc, bool)
    for (y, m), idx in cell_of.items():
        want = max(need[y][m], 0.0)
        idx = list(rng.permutation(idx))
        total = 0.0
        chosen = []
        for i in idx:                                          # take orders until the cell amount is reached, then close the gap
            if total + v3[i] <= want:
                chosen.append(i); total += v3[i]
        rest = [i for i in idx if i not in set(chosen)]
        if rest:
            j = min(rest, key=lambda i: abs(total + v3[i] - want))
            if abs(total + v3[j] - want) < abs(total - want):
                chosen.append(j)
        pick[chosen] = True
    O, L = thin(O, L, ~b2b)
    O3, L3 = thin(O3, L3, pick)
    O, L = merge(O, L, O3, L3)
    return O, L
