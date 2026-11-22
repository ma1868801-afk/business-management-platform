"""Inventory tables built from the stock simulation: inventory_levels, inventory_snapshots, purchase_orders,
purchase_order_items and stock_adjustments."""
from datetime import date, timedelta
import numpy as np
import pandas as pd
from g_reference import DAYS, ND, DAY_INDEX
import g_inventory as GI

END = ND - 1
OPEN_DAYS = 6                    # purchase orders placed in the last week and not yet shipped are Open
Z_SERVICE = 1.65                 # 95 percent service level


def _series(R):
    """All simulated series in one list ordered by location and product: (sim, index in sim)."""
    out = []
    for key in ("sim_st", "sim_dc"):
        sim = R[key]
        out += [(sim, i) for i in range(len(sim["ser_l"]))]
    out.sort(key=lambda r: (int(r[0]["ser_l"][r[1]]), int(r[0]["ser_p"][r[1]])))
    return out


def levels(S, R, rng, adj_df):
    prods = S["prods"]
    rows = []
    last_count = adj_df[adj_df.reason == "Count Correction"].groupby(["branch_id", "product_id"]).adjustment_date.max().to_dict()
    for k, (sim, i) in enumerate(_series(R)):
        loc, p = int(sim["ser_l"][i]), int(sim["ser_p"][i])
        D = sim["D"][i].astype(float)
        L, moq, cover = int(sim["lead"][i]), int(sim["moq"][i]), int(sim["cover"][i])
        rate = D[-90:].mean()
        wk = D[-182:].reshape(26, 7).sum(axis=1)
        sig = float(wk.std())
        ss = max(1, int(np.ceil(Z_SERVICE * sig * np.sqrt(L / 7.0))))
        rop = int(np.ceil(rate * L)) + ss
        rq = max(moq, int(np.ceil(rate * (cover + int(sim["hx"][i]) - L))) + GI.SS_PAD, 1)
        oh = int(sim["S_end"][i])
        rsv = int(min(R["Res"][loc, p], oh))
        lr = int(sim["last_rec"][i])
        lc = DAYS[END - int(rng.integers(0, 120))]
        cc = last_count.get((loc + 1, p + 1))
        if cc is not None and cc > lc:
            lc = cc
        if rng.random() < 0.02:
            lc = None
        rows.append(dict(inventory_id=k + 1, branch_id=loc + 1, product_id=p + 1, quantity_on_hand=oh, quantity_reserved=rsv,
                         reorder_point=rop, safety_stock=ss, max_stock_level=rop + rq, reorder_quantity=rq,
                         last_restock_date=DAYS[lr] if lr >= 0 else None, last_count_date=lc, snapshot_date=DAYS[END]))
    df = pd.DataFrame(rows)
    return df


def snapshots(R):
    frames = []
    for sim in (R["sim_st"], R["sim_dc"]):
        snap, so = sim["snap"], sim["so"]
        ii, ww = np.where(snap >= 0)
        frames.append(pd.DataFrame(dict(branch_id=sim["ser_l"][ii] + 1, product_id=sim["ser_p"][ii] + 1, _w=ww,
                                        quantity_on_hand=snap[ii, ww].astype(np.int64), stockout_days=so[ii, ww].astype(np.int16))))
    df = pd.concat(frames, ignore_index=True)
    sat = np.array([DAYS[GI.SAT0 + 7 * w] for w in range(R["sim_dc"]["nweeks"])], dtype=object)
    df["snapshot_date"] = sat[df["_w"].to_numpy()]
    df = df.sort_values(["branch_id", "product_id", "_w"]).reset_index(drop=True)
    df.insert(0, "snapshot_id", np.arange(1, len(df) + 1, dtype=np.int64))
    return df[["snapshot_id", "snapshot_date", "branch_id", "product_id", "quantity_on_hand", "stockout_days"]]


def purchase_orders(S, R, rng):
    prods, sups = S["prods"], S["sups"]
    ev = []
    for sim in (R["sim_st"], R["sim_dc"]):
        sup = sim["sup"]
        for (i, od, qo, qr, ex, actual, cancelled, partial) in sim["events"]:
            ev.append((int(sim["ser_l"][i]), int(sup[i]), int(sim["ser_p"][i]), od, qo, qr, ex, actual, cancelled, partial))
        for (i, od, q, t) in sim["init_events"]:
            if sim["internal"][i]:
                continue
            ev.append((int(sim["ser_l"][i]), int(sup[i]), int(sim["ser_p"][i]), od, q, q, t, t, False, False))
    e = pd.DataFrame(ev, columns=["loc", "sup", "prod", "od", "qo", "qr", "ex", "act", "canc", "part"])
    e["transit"] = (e.act > END) & ~e.canc
    e["kind"] = np.where(e.canc, "C", np.where(e.transit, "T", "R"))
    e["act_key"] = np.where(e.kind == "R", e.act, -1)
    e["lead"] = e.sup.map(lambda s: sups[s]["lead_time_days"])
    assert (e.ex == e.od + e.lead).all(), "expected delivery must equal order date plus lead time"
    g = e.groupby(["od", "sup", "loc", "kind", "act_key"], sort=True).ngroup()
    e["g"] = g
    first = e.groupby("g").agg(od=("od", "first"), sup=("sup", "first"), loc=("loc", "first"), kind=("kind", "first"),
                               act=("act", "first"), ex=("ex", "first"), part=("part", "max")).sort_values(["od", "sup", "loc", "act"]).reset_index()
    first["po_id"] = np.arange(1, len(first) + 1)
    first["year"] = first.od.map(lambda d: DAYS[d].year)
    first["seq"] = first.groupby("year").cumcount() + 1
    first["po_number"] = ["PO-%d-%05d" % (y, n) for y, n in zip(first.year, first.seq)]
    first["status"] = np.select([first.kind == "C", first.kind == "T", first.part], ["Cancelled", "In Transit", "Partially Received"], "Received")
    first.loc[(first.kind == "T") & (first.od >= END - OPEN_DAYS + 1), "status"] = "Open"
    e = e.merge(first[["g", "po_id", "status"]], on="g")
    # line costs: product cost with a small supplier price variation
    uc = np.array([prods[p]["unit_cost"] for p in e["prod"]])
    cents = np.round(uc * (1 + rng.uniform(-0.015, 0.015, len(e))) * 100).astype(np.int64)
    e["uc_c"] = np.maximum(cents, 1)
    e["line_c"] = e.qo.astype(np.int64) * e.uc_c
    tot = e.groupby("po_id").line_c.sum()
    first["total_amount"] = first.po_id.map(tot) / 100.0
    e["qr"] = np.where(e.kind == "R", e.qr, 0)
    e = e.sort_values(["po_id", "prod"]).reset_index(drop=True)
    items = pd.DataFrame(dict(po_item_id=np.arange(1, len(e) + 1), po_id=e.po_id, product_id=e["prod"] + 1, quantity_ordered=e.qo.astype(int),
                              quantity_received=e.qr.astype(int), unit_cost=e.uc_c / 100.0))
    po = pd.DataFrame(dict(po_id=first.po_id, po_number=first.po_number, supplier_id=first.sup + 1, destination_branch_id=first["loc"] + 1,
                           order_date=[DAYS[d] for d in first.od], expected_delivery_date=[DAYS[0] + timedelta(days=int(d)) for d in first.ex],
                           actual_delivery_date=[DAYS[a] if k == "R" else None for a, k in zip(first.act, first.kind)],
                           status=first.status, total_amount=first.total_amount, currency="SAR"))
    return po, items


def adjustments(S, R, rng):
    prods = S["prods"]
    rows = []
    for sim in (R["sim_st"], R["sim_dc"]):
        for (i, d, reason, q) in sim["adj"]:
            p = int(sim["ser_p"][i])
            if reason == "SHORT":
                reason = "Count Correction"
            elif reason == "WRITEOFF":
                reason = "Expiry" if prods[p]["shelf_life_days"] else "Damage"
            rows.append((int(sim["ser_l"][i]) + 1, p + 1, d, int(q), reason))
    df = pd.DataFrame(rows, columns=["branch_id", "product_id", "d", "quantity_change", "reason"])
    df = df[df.quantity_change != 0].sort_values(["d", "branch_id", "product_id"]).reset_index(drop=True)
    uc = np.array([prods[p - 1]["unit_cost"] for p in df.product_id])
    df.insert(0, "adjustment_id", np.arange(1, len(df) + 1))
    df["adjustment_date"] = [DAYS[d] for d in df.d]
    df["cost_impact"] = np.round(df.quantity_change.to_numpy() * uc, 2)
    return df[["adjustment_id", "branch_id", "product_id", "adjustment_date", "quantity_change", "reason", "cost_impact"]]


def status_of(lv):
    avail = lv.quantity_on_hand - lv.quantity_reserved
    return np.select([avail <= 0, avail <= lv.safety_stock, avail <= lv.reorder_point, avail > lv.max_stock_level],
                     ["Out of Stock", "Critical", "Reorder Now", "Overstock"], "Healthy")


def build(S, R, rng):
    adj = adjustments(S, R, rng)
    lv = levels(S, R, rng, adj)
    snap = snapshots(R)
    po, poi = purchase_orders(S, R, rng)
    return dict(levels=lv, snapshots=snap, purchase_orders=po, purchase_order_items=poi, stock_adjustments=adj)
