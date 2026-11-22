"""Inventory: daily stock simulation per location and SKU, purchase orders, weekly snapshots, current levels, adjustments.

Stock is simulated day by day from the generated sales (units shipped), restocked returns, supplier receipts and adjustments.
Replenishment follows a projected-stock rule with the supplier lead time, minimum order quantities, late and short deliveries.
Replenishment of stores from the distribution centre is not modelled as a separate movement.
"""
from datetime import date, timedelta
import numpy as np
import pandas as pd
import registry as R
from g_reference import DAYS, ND, DAY_INDEX
import g_baskets as GB

END = ND - 1
DC = 8
STORE_N = [98, 96, 94, 92, 90, 88, 84, 80]            # assortment size per store (RYD-OLY ... ABH-CTY)
MUST = {1: ["APPL-0002", "ELEC-0001"]}                 # JED-THL (index 1) carries these two SKUs
DEAD = ["ELEC-0013", "FASH-0014", "SPRT-0014", "HOME-0014", "FASH-0013", "HOME-0013"]
SAT0 = DAY_INDEX[date(2024, 1, 6)]


def demand_arrays(S, orders, items, returns):
    """Units shipped (Completed and Returned orders) and restocked units, by location, product and day; reserved units."""
    P = len(S["prods"])
    o = orders.set_index("order_id")
    it = items.merge(orders[["order_id", "branch_id", "order_date", "status"]], on="order_id")
    day = it.order_date.map(DAY_INDEX).to_numpy()
    loc = it.branch_id.to_numpy() - 1
    prod = it.product_id.to_numpy() - 1
    ship = it.status.isin(["Completed", "Returned"]).to_numpy()
    Dm = np.zeros((9, P, ND), dtype=np.int32)
    np.add.at(Dm, (loc[ship], prod[ship], day[ship]), it.quantity.to_numpy()[ship])
    Rm = np.zeros((9, P, ND), dtype=np.int32)
    rr = returns[returns.restocked]
    np.add.at(Rm, (rr.branch_id.to_numpy() - 1, rr.product_id.to_numpy() - 1, rr.return_date.map(DAY_INDEX).to_numpy()), rr.quantity_returned.to_numpy())
    proc = it.status.eq("Processing").to_numpy()
    Res = np.zeros((9, P), dtype=np.int32)
    np.add.at(Res, (loc[proc], prod[proc]), it.quantity.to_numpy()[proc])
    return Dm, Rm, Res


def choose_series(rng, S, Dm, exclude=()):
    """Series (location, product): all SKUs at the distribution centre, an assortment per store."""
    prods = S["prods"]
    P = len(prods)
    sku = [p["sku"] for p in prods]
    last52 = Dm[:, :, ND - 365:].sum(axis=2)
    ls, ps = [], []
    for p in range(P):
        ls.append(DC); ps.append(p)
    for st in range(8):
        score = last52[st].astype(float) + rng.random(P) * 0.5
        for s in MUST.get(st, []):
            score[sku.index(s)] = 1e9
        for p in exclude:                                        # distribution-centre-only SKUs
            score[p] = -1e9
        for s in DEAD:                                           # dead stock sits in the larger stores
            if st < 5:
                score[sku.index(s)] = 1e8
        for i, p in enumerate(prods):                            # not yet launched or already gone long ago: not carried
            if p["discontinued_date"] and p["discontinued_date"] < date(2026, 1, 1) and p["sku"] not in DEAD:
                score[i] -= 1e7
        top = np.argsort(-score)[: STORE_N[st]]
        ls += [st] * len(top); ps += list(top)
    return np.array(ls), np.array(ps)


def start_days(S, ps):
    out = []
    for p in ps:
        ld = S["prods"][p]["launch_date"]
        out.append(max(DAY_INDEX[ld], 0) if ld >= DAYS[0] else 0)
    return np.array(out)


WD = [6, 0, 1, 2, 3]                                   # supplier order weekdays (Python weekday): Sunday to Thursday
WEEKDAY = np.array([d.weekday() for d in DAYS])
EXT = 160
DBG = []
DBG_SER = None


def adjustment_plan(rng, S, ser_l, ser_p, Dm, n=3250):
    """Planned non-sales stock movements: (series index, day, reason, signed quantity)."""
    prods = S["prods"]
    vel = Dm[ser_l, ser_p, :].sum(axis=1) + 1.0
    price = np.array([prods[p]["unit_price"] for p in ser_p])
    w = vel ** 0.5 / (price ** 0.15)
    w = w / w.sum()
    shelf = np.array([prods[p]["shelf_life_days"] is not None for p in ser_p])
    cat = np.array([prods[p]["sku"][:4] for p in ser_p])
    rows = []
    reasons = ["Damage", "Expiry", "Shrinkage", "Count Correction", "Display Sample"]
    prob = np.array([0.30, 0.17, 0.23, 0.22, 0.08])
    for _ in range(n):
        s = int(rng.choice(len(ser_l), p=w))
        r = reasons[int(rng.choice(5, p=prob))]
        if r == "Expiry" and not shelf[s]:
            r = "Damage"
        if r == "Display Sample" and (ser_l[s] == DC or cat[s] not in ("ELEC", "APPL", "BEAU", "SPRT", "KIDS")):
            r = "Shrinkage"
        d = int(rng.integers(20, ND - 1))
        mx = 3 + int(2 * vel[s] ** 0.3)
        q = {"Damage": -int(rng.integers(1, mx + 2)), "Expiry": -int(rng.integers(2, mx * 3 + 3)), "Shrinkage": -int(rng.integers(1, mx + 1)),
             "Count Correction": int(rng.choice([-1, 1], p=[0.6, 0.4])) * int(rng.integers(1, mx + 1)), "Display Sample": -1}[r]
        rows.append((s, d, r, q))
    return rows


def build_script(Dp, moq, lead, windows, p_open=0):
    """Scripted stock cycles for a distribution-centre-only SKU: every receipt equals the demand until the next planned
    depletion, and each planned window starts exactly when the stock reaches zero. Returns the series script."""
    cum = np.cumsum(Dp.astype(np.int64))
    csum = lambda a, b: int(cum[b] - (cum[a - 1] if a > 0 else 0))
    cycles = []                       # (receipt_day, qty, expected_day)
    r, exp_next, writeoffs = 0, 0, []
    for (s0, e0) in windows:
        while r <= s0 - 1:
            tgt = (cum[r - 1] if r > 0 else 0) + moq
            x = int(np.searchsorted(cum, tgt, side="left"))
            if x >= s0 - 1 or csum(x + 1, s0 - 1) < moq:
                x = s0 - 1
            q = csum(r, x)
            qq = max(q, moq) if q > 0 else 0
            if qq > 0:
                cycles.append((r, qq, exp_next))
            if x == s0 - 1 and qq > q:
                writeoffs.append(x)
            r, exp_next = x + 1, x + 1
        r, exp_next = e0 + 1, s0                  # the receipt after the window arrives late
    q_post = max(moq, csum(r, min(r + 60, len(Dp) - 1))) if r < len(Dp) else 0
    if q_post > 0:
        cycles.append((r, q_post, exp_next))
    return dict(cycles=cycles, resume=r, writeoffs=writeoffs, windows=windows)


N_STUCK_ST, N_STUCK_DC = 20, 110
def dyn_ss(C, idx, t, L, z=1.65):
    """Safety stock from the service level and the lead time: z x (standard deviation of weekly demand over the last 26 weeks) x sqrt(L / 7)."""
    ends = np.maximum((t + 1) - 7 * np.arange(0, 27), 0)
    cs = C[idx][:, ends]
    wk = cs[:, :-1] - cs[:, 1:]
    return np.maximum(np.ceil(z * wk.std(axis=1) * np.sqrt(L / 7.0)), 1)


SS_PAD = 2                                             # the replenishment rule keeps this many units above the published safety stock
PACK = 3                                               # store replenishment from the distribution centre moves at least this many units
ADJ_CAP = 0.25                                         # a planned loss never exceeds this share of the stock on hand
HFRAC = 0.85                                           # extra ordering horizon as a share of the lead time (minimum 7 days)


def simulate(rng, S, ser_l, ser_p, Dm, Rm, counters, script, plan_adj, internal=None, Dx=None, cover_scale=1.0, stuck=None):
    prods, sups = S["prods"], S["sups"]
    ns = len(ser_l)
    sup = np.array([prods[p]["supplier_id"] for p in ser_p]) - 1
    lead = np.array([s["lead_time_days"] for s in sups])[sup]
    moq = np.array([s["min_order_qty"] for s in sups])[sup]
    internal = np.zeros(ns, bool) if internal is None else internal
    lead = np.where(internal, 3, lead)
    moq = np.where(internal, PACK, moq)
    D = Dm[ser_l, ser_p, :].astype(np.int64)
    if Dx is not None:
        D = D + Dx
    Rr = Rm[ser_l, ser_p, :].astype(np.int64)
    rate28 = D[:, -28:].mean(axis=1)
    Dext = np.concatenate([D, np.repeat(rate28[:, None], EXT, axis=1)], axis=1).astype(float)
    C = np.concatenate([np.zeros((ns, 1)), np.cumsum(Dext, axis=1)], axis=1)
    st = start_days(S, ser_p)
    disc = np.array([DAY_INDEX[prods[p]["discontinued_date"]] if prods[p]["discontinued_date"] else 10 ** 6 for p in ser_p])
    sku = np.array([prods[p]["sku"] for p in ser_p])
    dead = np.isin(sku, DEAD)
    no_order = np.where(dead, DAY_INDEX[date(2026, 5, 20)], np.where(disc < 10 ** 6, disc - 21, 10 ** 6))
    cover = np.where(internal, 14, np.clip(np.round((14 + 0.9 * lead) * cover_scale), 14, 60)).astype(int)
    ss_days = np.where(internal, 4.0, 9.0)
    hxv = np.where(internal, 7, np.maximum(7, np.round(HFRAC * lead))).astype(int)
    stuck = np.zeros(ns, bool) if stuck is None else stuck
    was_stuck = np.zeros(ns, bool)
    dow = np.array([WD[(x + int(l)) % 5] for x, l in zip(sup, ser_l)])
    dow = np.where(internal, 0, dow)
    transfer = np.zeros((ns, ND), dtype=np.int32)
    n_po, n_late, tgt = counters
    Sx = np.zeros(ns, dtype=np.int64)
    pend_day = np.full(ns, -1)
    pend_qty = np.zeros(ns, dtype=np.int64)
    started = np.zeros(ns, bool)
    last_rec = np.full(ns, -1)
    nweeks = (END - SAT0) // 7 + 1
    snap = np.full((ns, nweeks), -1, dtype=np.int32)
    so = np.zeros((ns, nweeks), dtype=np.int16)
    events, adj_rows, init_events = [], [], []
    adj_by_day = {}
    for s_, d, r, q in plan_adj:
        adj_by_day.setdefault(d, []).append((s_, r, q))
    live_end = np.where(dead, DAY_INDEX[date(2026, 7, 20)], disc)
    # scripted series
    script_recv, open_q = {}, {}
    script_until = np.full(ns, -1)
    for i, sc in script.items():
        sp = int(sup[i])
        cyc = sc["cycles"]
        open_q[i] = cyc[0][1] if cyc and cyc[0][0] == 0 else 0
        for (r, q, ex) in cyc:
            if r == 0:
                continue
            script_recv.setdefault(r, []).append((i, q))
            od = ex - int(lead[i])
            if od >= 0:
                events.append((i, od, q, q, ex, r, False, False))
                n_po[sp] += 1
                n_late[sp] += 1 if r > ex else 0
        for x in sc["writeoffs"]:
            adj_by_day.setdefault(x, []).append((i, "WRITEOFF", -10 ** 6))
        script_until[i] = sc["resume"]
    for t in range(ND):
        wk = 0 if t <= SAT0 else -(-(t - SAT0) // 7)
        new = (~started) & (st <= t)
        if new.any():
            idx = np.where(new)[0]
            horizon = lead[idx] + cover[idx]
            hh = lead[idx] + hxv[idx] + cover[idx] // 2
            need = np.ceil(C[idx, np.minimum(t + 1 + hh, ND + EXT)] - C[idx, t + 1] + ss_days[idx] * np.maximum(rate28[idx], 0.05))
            q0 = np.maximum(need, 0).astype(np.int64)
            q0 = np.where(q0 > 0, np.maximum(q0, moq[idx]), 0)
            for j, i in enumerate(idx):
                if i in open_q:
                    q0[j] = open_q[i]
            Sx[idx] += q0
            started[idx] = True
            for j, i in enumerate(idx):
                if t > 0 and q0[j] > 0 and t >= lead[i]:
                    init_events.append((int(i), t - int(lead[i]), int(q0[j]), t))
                last_rec[i] = t
        arr = pend_day == t
        rec = np.where(arr, pend_qty, 0)
        if arr.any():
            last_rec[arr] = t
            pend_day[arr] = -1
        for (i, q) in script_recv.get(t, ()):
            rec[i] += q
            last_rec[i] = t
        avail = Sx + rec + Rr[:, t]
        live = started & (t < live_end)
        so_mask = (avail == 0) & (D[:, t] == 0) & live
        if so_mask.any():
            so[so_mask, wk] += 1
        after = avail - D[:, t]
        neg = after < 0
        if neg.any():
            for i in np.where(neg)[0]:
                adj_rows.append((int(i), t, "SHORT", int(-after[i])))
            after = np.where(neg, 0, after)
        for s_, r, q in adj_by_day.get(t, ()):
            if not started[s_]:
                continue
            if q < 0:
                q = -min(-q, int(after[s_] * ADJ_CAP)) if q > -10 ** 5 else -int(after[s_])
            if q != 0:
                after[s_] += q
                adj_rows.append((s_, t, r, q))
        Sx = after
        if DBG_SER is not None and DBG_SER[0] == ns:
            DBG.append((t, int(Sx[DBG_SER[1]]), int(pend_day[DBG_SER[1]]), int(rec[DBG_SER[1]])))
        if t <= END:
            cand = np.where(started & (dow == WEEKDAY[t]) & (pend_day < 0) & (t > st) & (t <= no_order) & (t > script_until))[0]
            if len(cand):
                hz = lead[cand] + hxv[cand]
                f_lead = C[cand, t + 1 + hz] - C[cand, t + 1]
                ss = np.ceil(ss_days[cand] * (C[cand, t + 29] - C[cand, t + 1]) / 28.0)
                ss = dyn_ss(C, cand, t, lead[cand]) + SS_PAD
                proj = Sx[cand] - f_lead
                f_cover = C[cand, t + 1 + hz + cover[cand]] - C[cand, t + 1 + hz]
                go = (proj <= ss) & ((f_lead + f_cover) > 0)
                cand, ss = cand[go], ss[go]
                if len(cand):
                    q = np.ceil(ss + (C[cand, t + 1 + lead[cand] + hxv[cand] + cover[cand]] - C[cand, t + 1]) - Sx[cand]).astype(np.int64)
                    q = np.maximum(np.maximum(q, moq[cand]), 1)
                    groups = {}
                    for j, i in enumerate(cand):
                        if internal[i]:
                            pend_day[i] = t + 3
                            pend_qty[i] = int(q[j])
                            transfer[i, t] = int(q[j])
                            continue
                        groups.setdefault((int(sup[i]), int(ser_l[i])), []).append(j)
                    for (sp, lc), js in groups.items():
                        ids = cand[js]
                        a = t + int(lead[ids[0]])
                        dmax = 10 ** 6
                        for i in ids:
                            row = C[i, t + 1:]
                            k = int(np.searchsorted(row, row[0] + Sx[i], side="right"))
                            amax = t + k if k < len(row) else 10 ** 6
                            dmax = min(dmax, max(amax - a, 0))
                        cancelled = rng.random() < 0.012
                        delay = 0
                        want_late = (n_late[sp] + 1) <= tgt[sp] * (n_po[sp] + 1) + 0.5
                        if dmax >= 1 and want_late:
                            u = rng.random()
                            delay = 1 + int(rng.integers(0, 7)) if u < 0.6 else (8 + int(rng.integers(0, 7)) if u < 0.9 else 15 + int(rng.integers(0, 11)))
                            delay = min(delay, dmax)
                        else:
                            delay = 0 if rng.random() < 0.7 else -int(rng.integers(1, 3))
                        if not cancelled:
                            n_po[sp] += 1
                            n_late[sp] += 1 if delay > 0 else 0
                        partial = (not cancelled) and rng.random() < 0.04
                        pi = int(rng.integers(0, len(ids)))
                        for n, (i, j) in enumerate(zip(ids, js)):
                            qo = int(q[j])
                            qr = 0 if cancelled else qo
                            if partial and n == pi and qo >= 2:
                                qr = max(1, int(qo * rng.uniform(0.4, 0.85)))
                            actual = a + delay
                            if stuck[i] and not was_stuck[i] and not cancelled and END - max(30, int(1.2 * lead[i])) <= a <= END:
                                actual = END + 1 + int(rng.integers(0, 4))      # the shipment is held up and does not arrive before the reference date
                                was_stuck[i] = True
                            events.append((int(i), t, qo, qr, a, actual, cancelled, partial and n == pi))
                            if not cancelled:
                                pend_day[i] = actual if actual <= END else 10 ** 7
                                pend_qty[i] = qr
        if t >= SAT0 and (t - SAT0) % 7 == 0:
            snap[:, (t - SAT0) // 7] = np.where(started, Sx, -1)
    return dict(D=D.astype(np.int32), was_stuck=was_stuck, internal=internal, hx=hxv, ser_l=ser_l, ser_p=ser_p, sup=sup, lead=lead, moq=moq, cover=cover, st=st, snap=snap, so=so, events=events, init_events=init_events,
                adj=adj_rows, transfer=transfer, S_end=Sx, last_rec=last_rec, rate28=rate28, pend_day=pend_day, started=started, nweeks=nweeks, ss_days=ss_days)


# --------------------------------------------------------------------------------------------- orchestration
def pick_stuck(rng, S, Dm, ls, ps, internal, k, skip=()):
    """Series whose last shipment is held up: they run out of stock before the reference date."""
    prods, sups = S["prods"], S["sups"]
    ok = []
    for i, (l, p) in enumerate(zip(ls, ps)):
        pr = prods[p]
        lead = sups[pr["supplier_id"] - 1]["lead_time_days"]
        rate = Dm[l, p, -90:].mean()
        if (internal[i] or lead < 4 or rate < 0.12 or pr["sku"] in DEAD or pr["discontinued_date"] or pr["lifecycle_status"] != "Active"
                or p in skip or pr["launch_date"] > date(2024, 6, 1)):
            continue
        ok.append(i)
    flag = np.zeros(len(ls), bool)
    if ok:
        flag[rng.choice(ok, size=min(k, len(ok)), replace=False)] = True
    return flag


def run(S, orders, items, returns, rng, verbose=True):
    prods, sups = S["prods"], S["sups"]
    windows = S["windows"]
    fr_prods = sorted(windows)
    # restocked returns of the scripted SKUs at the distribution centre would break the planned depletions
    returns = returns.copy()
    returns.loc[(returns.branch_id == DC + 1) & returns.product_id.isin([p + 1 for p in fr_prods]), "restocked"] = False
    Dm, Rm, Res = demand_arrays(S, orders, items, returns)
    ls, ps = choose_series(rng, S, Dm, exclude=fr_prods)
    w = Dm[:, :, -365:].sum(axis=2)[ls, ps] / 52.0
    moq = np.array([sups[prods[q]["supplier_id"] - 1]["min_order_qty"] for q in ps])
    internal_all = (ls != DC) & (moq > 10 * w)
    st_idx, dc_idx = np.where(ls != DC)[0], np.where(ls == DC)[0]
    adj_plan = adjustment_plan(rng, S, ls, ps, Dm)
    st_map = {int(g): k for k, g in enumerate(st_idx)}
    dc_map = {int(g): k for k, g in enumerate(dc_idx)}
    target_late = 1 - np.array([s["on_time_delivery_pct"] for s in sups]) / 100.0
    counters = (np.zeros(16), np.zeros(16), target_late)
    pmap = {p: i for i, p in enumerate(ps[dc_idx])}
    # scripted SKUs first so that their late deliveries count towards the supplier rates
    script = {}
    for p in fr_prods:
        i = pmap[p]
        m = sups[prods[p]["supplier_id"] - 1]
        script[i] = build_script(Dm[DC, p, :], m["min_order_qty"], m["lead_time_days"], windows[p])
    plan_st = [(st_map[s], d, r, q) for s, d, r, q in adj_plan if s in st_map]
    stuck_st = pick_stuck(rng, S, Dm, ls[st_idx], ps[st_idx], internal_all[st_idx], N_STUCK_ST)
    sim_st = simulate(rng, S, ls[st_idx], ps[st_idx], Dm, Rm, counters, {}, plan_st, internal=internal_all[st_idx], stuck=stuck_st)
    Dx = np.zeros((len(dc_idx), ND), dtype=np.int64)
    for k, g in enumerate(st_idx):
        if internal_all[g]:
            Dx[pmap[ps[g]]] += sim_st["transfer"][k]
    plan_dc = [(dc_map[s], d, r, q) for s, d, r, q in adj_plan if s in dc_map and dc_map[s] not in script]
    stuck_dc = pick_stuck(rng, S, Dm, ls[dc_idx], ps[dc_idx], np.zeros(len(dc_idx), bool), N_STUCK_DC, skip=fr_prods)
    sim_dc = simulate(rng, S, ls[dc_idx], ps[dc_idx], Dm, Rm, counters, script, plan_dc, Dx=Dx, stuck=stuck_dc)
    return dict(Dm=Dm, Rm=Rm, Res=Res, ls=ls, ps=ps, st_idx=st_idx, dc_idx=dc_idx, sim_st=sim_st, sim_dc=sim_dc, script=script, internal=internal_all,
                adj_plan=adj_plan, counters=counters, fr_prods=fr_prods, returns=returns)


# --------------------------------------------------------------------------------------------- stockout scenarios
EST_PO = [128, 25, 161, 52, 110, 74, 151, 149, 93, 106, 122, 70, 69, 68, 228, 75]      # purchase orders per supplier (measured)


def plan_windows(rng, S, n_sku=30, n_win=3, want=20):
    """Pick distribution-centre-only SKUs and plan stockout windows in 2025; demand inside a window is replaced by a substitute
    product of the same category (a lost sale of the SKU). Modifies the line arrays in place."""
    O, L, model, prods, sups = S["O"], S["L"], S["model"], S["prods"], S["sups"]
    dc = O["store"][L["order"]] == DC
    day = O["day"][L["order"]]
    y0, y1 = DAY_INDEX[date(2025, 1, 1)], DAY_INDEX[date(2025, 12, 31)]
    P = len(prods)
    cand = []
    for p, pr in enumerate(prods):
        if pr["lifecycle_status"] != "Active" or pr["launch_date"] > date(2024, 3, 1) or pr["sku"] in DEAD or pr["is_seasonal"]:
            continue
        if pr["sku"] in sum(MUST.values(), []):
            continue
        m = (L["prod"] == p) & dc
        d25 = m & (day >= y0) & (day <= y1)
        units25 = int(L["qty"][d25].sum())
        days25 = len(np.unique(day[d25]))
        moq = sups[pr["supplier_id"] - 1]["min_order_qty"]
        st_units = int(L["qty"][(L["prod"] == p) & ~dc].sum())
        if days25 >= 25 and units25 >= 3.6 * moq:
            cand.append((st_units / max(units25, 1), p))
    cand.sort()
    per_cat, chosen = {}, []
    for _, p in cand:
        k = int(model.cat[p])
        if per_cat.get(k, 0) >= 6:
            continue
        per_cat[k] = per_cat.get(k, 0) + 1
        chosen.append(p)
        if len(chosen) >= n_sku:
            break
    windows = {}
    budget = [int(0.8 * (1 - sups[i]["on_time_delivery_pct"] / 100.0) * EST_PO[i]) for i in range(len(sups))]   # late deliveries a supplier can absorb
    sub_pool = {k: [q for q in range(P) if model.cat[q] == k and q not in chosen] for k in range(8)}
    for p in chosen:
        if len(windows) >= want:
            break
        sp = prods[p]["supplier_id"] - 1
        if budget[sp] < 2:
            continue
        moq = sups[sp]["min_order_qty"]
        m = (L["prod"] == p) & dc
        dem = np.bincount(day[m], weights=L["qty"][m], minlength=ND)
        cum = np.cumsum(dem)
        pos = y0 + 20
        wl = []
        for _ in range(min(n_win, budget[sp])):
            base = cum[pos - 1]
            j = int(np.searchsorted(cum, base + 1.3 * moq, side="left"))
            s0 = j + 1
            g = int(rng.integers(9, 17))
            if s0 + g - 1 > y1 - 10:
                break
            wl.append((s0, s0 + g - 1))
            pos = s0 + g
        if len(wl) >= 2:
            windows[p] = wl
            budget[sp] -= len(wl)
    # substitute demand inside the windows
    changed = 0
    for p, wl in windows.items():
        k = int(model.cat[p])
        for (a, b) in wl:
            idx = np.where((L["prod"] == p) & dc & (day >= a) & (day <= b))[0]
            for i in idx:
                d = day[i]
                pool = np.array(sub_pool[k])
                w = np.exp(model.log_base[pool, d])
                w = np.where(np.isfinite(w), w, 0.0)
                if w.sum() <= 0:
                    continue
                q = int(rng.choice(pool, p=w / w.sum()))
                L["prod"][i] = q
                L["price"][i] = model.price[q, d]
                changed += 1
    S["windows"] = windows
    S["window_changed"] = changed
    return windows
