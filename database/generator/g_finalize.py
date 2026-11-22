"""Finalise orders: status, time, payment, costs, totals, loyalty tier, shipping, points."""
from datetime import datetime, timedelta, date
import numpy as np
import pandas as pd
import registry as R
from g_reference import DAYS, ND, DAY_INDEX
from g_baskets import CATS


def round_half_up(x, decimals=2):
    """Round-half-away-from-zero (matches SQL's ROUND, unlike numpy's/Python's round-half-to-even) for the
    few line totals that land exactly on a .xx5 boundary. The tiny epsilon absorbs float64 representation
    error in the multiplication itself (e.g. 0.15 has no exact binary form, so 673.30 * 0.15 often lands a
    sliver below the true 100.995 and would otherwise floor to 100.99 instead of rounding up to 101.00)."""
    factor = 10 ** decimals
    return np.floor(np.asarray(x, dtype=np.float64) * factor + 0.5 + 1e-7) / factor

CH_NAMES = {0: "In-Store", 1: "Online", 2: "Mobile App", 3: "B2B"}
STORE_CODES = ["RYD-OLY", "JED-THL", "RYD-MLQ", "DMM-FSL", "KHB-COR", "MED-QBA", "JED-OBH", "ABH-CTY", "RYD-DC"]
PAY = {
    0: (["Mada", "Credit Card", "Apple Pay", "STC Pay", "Cash"], [0.48, 0.20, 0.14, 0.06, 0.12]),
    1: (["Mada", "Credit Card", "Apple Pay", "STC Pay", "Cash on Delivery", "Buy Now Pay Later"], [0.30, 0.24, 0.16, 0.08, 0.14, 0.08]),
    2: (["Mada", "Credit Card", "Apple Pay", "STC Pay", "Buy Now Pay Later"], [0.30, 0.22, 0.24, 0.12, 0.12]),
    3: (["Bank Transfer"], [1.0]),
}
H_STORE = {10: 0.5, 11: 0.7, 12: 0.8, 13: 0.7, 14: 0.5, 15: 0.6, 16: 0.9, 17: 1.3, 18: 1.5, 19: 1.8, 20: 2.0, 21: 1.8, 22: 1.2}
H_STORE_RAM = {10: 0.3, 11: 0.3, 12: 0.3, 13: 0.2, 14: 0.2, 15: 0.3, 16: 0.5, 17: 0.7, 18: 0.5, 19: 0.6, 20: 1.4, 21: 2.2, 22: 2.4}
H_ONLINE = [0.8, 0.4, 0.2, 0.1, 0.1, 0.1, 0.2, 0.4, 0.6, 0.8, 0.9, 1.1, 1.5, 1.5, 1.2, 0.9, 0.9, 1.0, 1.2, 1.5, 2.4, 2.8, 3.0, 2.4]
# status rates: exact quotas per (channel group, year)
CANCEL_ONLINE, CANCEL_STORE, CANCEL_B2B = 0.0275, 0.0040, 0.015
RETURNED = 0.0065
PROCESSING_P = 0.55


def _quota(rng, mask, rate):
    """Boolean array with exactly round(rate * mask.sum()) True values among the masked positions."""
    idx = np.where(mask)[0]
    k = int(round(rate * len(idx)))
    out = np.zeros(len(mask), bool)
    if k > 0:
        out[rng.choice(idx, size=k, replace=False)] = True
    return out


def statuses(rng, O):
    n = len(O["day"])
    yr = np.array([DAYS[d].year for d in O["day"]])
    ch = O["channel"]
    online = (ch == 1) | (ch == 2)
    st = np.full(n, "Completed", dtype=object)
    last3 = O["day"] >= ND - 3
    proc = last3 & (rng.random(n) < PROCESSING_P)
    st[proc] = "Processing"
    free = ~proc
    for y in (2024, 2025, 2026):
        for grp, rate in ((online, CANCEL_ONLINE), (ch == 0, CANCEL_STORE), (ch == 3, CANCEL_B2B)):
            m = free & grp & (yr == y)
            st[_quota(rng, m, rate)] = "Cancelled"
    free = st == "Completed"
    for y in (2024, 2025, 2026):
        st[_quota(rng, free & (yr == y), RETURNED)] = "Returned"
    return st.astype(str)


def hours(rng, O):
    n = len(O["day"])
    h = np.zeros(n, dtype=np.int16)
    ram = np.array([c for c in (True,)] * 0)
    from g_reference import calendar_rows
    isram = np.array([c["is_ramadan"] for c in calendar_rows()])
    hs = np.arange(10, 23)
    p1 = np.array([H_STORE[x] for x in hs]); p1 /= p1.sum()
    p2 = np.array([H_STORE_RAM[x] for x in hs]); p2 /= p2.sum()
    po = np.array(H_ONLINE); po /= po.sum()
    ch, store, day = O["channel"], O["store"], O["day"]
    for i in np.where(ch == 0)[0]:
        pass
    ins = np.where(ch == 0)[0]
    r = isram[day[ins]]
    h[ins] = np.where(r, rng.choice(hs, size=len(ins), p=p2), rng.choice(hs, size=len(ins), p=p1))
    express = np.isin(store[ins], [6, 7])                         # JED-OBH and ABH-CTY open at 11:00
    first = express & (h[ins] == 10)
    h[ins[first]] = 11
    on = np.where((ch == 1) | (ch == 2))[0]
    h[on] = rng.choice(24, size=len(on), p=po)
    b = np.where(ch == 3)[0]
    h[b] = rng.choice(np.arange(8, 17), size=len(b))
    return h


def pay(rng, O):
    n = len(O["day"])
    out = np.empty(n, dtype=object)
    for c, (names, p) in PAY.items():
        idx = np.where(O["channel"] == c)[0]
        out[idx] = rng.choice(names, size=len(idx), p=p)
    return out


# ------------------------------------------------------------------------------------------ part 2
TTM0 = DAY_INDEX[date(2025, 11, 1)]
RET_RATE = dict(ELEC=0.028, APPL=0.025, FASH=0.085, GROC=0.0060, BEAU=0.042, SPRT=0.045, KIDS=0.038, HOME=0.038)
REASONS_STORE = (["Defective", "Wrong Item", "Changed Mind", "Not as Described"], [0.24, 0.12, 0.42, 0.22])
REASONS_ONLINE = (["Defective", "Wrong Item", "Changed Mind", "Late Delivery", "Not as Described", "Damaged in Transit"],
                  [0.14, 0.08, 0.30, 0.14, 0.12, 0.22])


def balance_eastern(rng, O, net, status):
    """Make the order-value distributions of DMM-FSL (3) and KHB-COR (4) equal inside each year (guarantee G-24)."""
    yr = np.array([DAYS[d].year for d in O["day"]])
    share_khb = 48.0 / 98.0
    for y in (2024, 2025, 2026):
        m = np.where((yr == y) & (O["channel"] == 0) & np.isin(O["store"], [3, 4]) & (status == "Completed"))[0]
        m = m[np.argsort(net[m], kind="stable")]
        for part in np.array_split(m, 12):
            want = int(round(share_khb * len(part)))
            have = int((O["store"][part] == 4).sum())
            if have > want:
                pick = rng.choice(part[O["store"][part] == 4], size=have - want, replace=False)
                O["store"][pick] = 3
            elif have < want:
                pick = rng.choice(part[O["store"][part] == 3], size=want - have, replace=False)
                O["store"][pick] = 4


def finalize(S, rng):
    O, L, custs, model = S["O"], S["L"], S["custs"], S["model"]
    prods, price_tab = S["prods"], S["price"]
    n = len(O["day"])
    status = statuses(rng, O)
    # line values with list prices
    qty, price, disc, order, prod = L["qty"], L["price"], L["disc"], L["order"], L["prod"]
    line_total = round_half_up(qty * price * (1 - disc / 100.0), 2)
    net = np.bincount(order, weights=line_total, minlength=n)
    balance_eastern(rng, O, net, status)
    # cost factors: calibrated so that the realised margin of each product line is close to its target margin
    cat = model.cat[prod]
    list_val = qty * price
    kfac = np.zeros(model.P)
    for k, line in enumerate(R.LINES):
        mk = cat == k
        dbar = 1 - line_total[mk].sum() / list_val[mk].sum()
        idx = np.where(model.cat == k)[0]
        m_sku = line[4] + np.clip(rng.normal(0, 1.4, len(idx)), -2.6, 2.6)
        kfac[idx] = (1 - m_sku / 100.0) * (1 - dbar) - 0.0
    unit_cost = round_half_up(price * kfac[prod], 2)
    unit_cost = np.minimum(unit_cost, round_half_up(price - 0.01, 2))
    line_cost = round_half_up(qty * unit_cost, 2)
    for i, p in enumerate(prods):
        p["unit_cost"] = round(float(p["unit_price"] * kfac[i]), 2)
    # order level
    subtotal = round_half_up(np.bincount(order, weights=line_total, minlength=n), 2)
    gross = np.bincount(order, weights=qty * price, minlength=n)
    discount_amount = round_half_up(gross - subtotal, 2)
    vat = round_half_up(0.15 * subtotal, 2)
    items = np.bincount(order, minlength=n)
    # loyalty tier of individuals from the trailing 12 months
    n_c = len(custs)
    comp = status == "Completed"
    ttm = comp & (O["day"] >= TTM0) & (O["cust"] >= 0)
    spend_ttm = np.bincount(O["cust"][ttm], weights=subtotal[ttm], minlength=n_c)
    life = np.bincount(O["cust"][comp & (O["cust"] >= 0)], weights=subtotal[comp & (O["cust"] >= 0)], minlength=n_c)
    is_ind = np.array([c["customer_type"] == "Individual" for c in custs])
    tier = np.where(spend_ttm >= 25000, "Platinum", np.where(spend_ttm >= 10000, "Gold", np.where(spend_ttm >= 3000, "Silver", "None")))
    tier = np.where(is_ind, tier, "None")
    points = np.floor(life / 10).astype(int)
    red = (rng.random(n_c) < 0.4) & (points >= 100)
    points = np.where(red, points - 100 * np.floor(rng.random(n_c) * 0.5 * points / 100).astype(int), points)
    for i, c in enumerate(custs):
        c["loyalty_tier"], c["loyalty_points"] = str(tier[i]), int(points[i])
        c["spend_ttm"] = float(spend_ttm[i])
    # shipping fee uses the customer's current tier
    online = (O["channel"] == 1) | (O["channel"] == 2)
    cust_tier = np.where(O["cust"] >= 0, tier[np.maximum(O["cust"], 0)], "None")
    ship = np.where(online & (subtotal < 250) & np.isin(cust_tier, ["None", "Silver"]), 25.0, 0.0)
    total = round_half_up(subtotal + vat + ship, 2)
    # account closures: some customers without recent orders
    quiet = np.where(is_ind & (spend_ttm == 0))[0]
    for i in rng.choice(quiet, size=int(0.03 * len(quiet)), replace=False):
        custs[i]["is_active"] = False
    # time stamps, payments, numbers
    h = hours(rng, O)
    minute = rng.integers(0, 60, n)
    second = rng.integers(0, 60, n)
    ts = [datetime(DAYS[d].year, DAYS[d].month, DAYS[d].day, int(hh), int(mm), int(ss)) for d, hh, mm, ss in zip(O["day"], h, minute, second)]
    yr = np.array([DAYS[d].year for d in O["day"]])
    seq = np.zeros(n, dtype=int)
    for y in (2024, 2025, 2026):
        m = yr == y
        seq[m] = np.arange(1, m.sum() + 1)
    city = np.array([custs[c]["city"] if c >= 0 else None for c in O["cust"]], dtype=object)
    city = np.where(O["channel"] == 0, None, city)
    promo_id = np.array([R.PROMOTIONS[j]["id"] if j >= 0 else None for j in O["promo"]], dtype=object)
    season = S["season"][O["day"]]
    orders = pd.DataFrame(dict(
        order_id=np.arange(1, n + 1), order_number=[f"SO-{y}-{s:07d}" for y, s in zip(yr, seq)],
        customer_id=pd.array(np.where(O["cust"] >= 0, O["cust"] + 1, -1), dtype="Int64"),
        branch_id=O["store"] + 1, channel=[CH_NAMES[c] for c in O["channel"]], order_timestamp=ts,
        order_date=[DAYS[d] for d in O["day"]], order_hour=h, season=season, status=status, payment_method=pay(rng, O),
        promotion_id=pd.array(promo_id, dtype="Int64"), items_count=items, subtotal_amount=subtotal,
        discount_amount=discount_amount, vat_amount=vat, shipping_fee=ship, total_amount=total, delivery_city=city, currency="SAR"))
    orders.loc[orders.customer_id == -1, "customer_id"] = pd.NA
    items_df = pd.DataFrame(dict(
        order_item_id=np.arange(1, len(order) + 1), order_id=order + 1, product_id=prod + 1, quantity=qty, unit_price=price,
        unit_cost=unit_cost, discount_pct=disc, line_total=line_total, line_cost=line_cost))
    S["fin"] = dict(status=status, subtotal=subtotal, tier=tier, kfac=kfac, hour=h)
    return orders, items_df


def make_returns(rng, S, orders, items):
    """Returns for Completed order lines (partial) and for all lines of fully Returned orders."""
    model = S["model"]
    o = orders.set_index("order_id")
    st = o.loc[items.order_id, "status"].to_numpy()
    cat = model.cat[items.product_id.to_numpy() - 1]
    comp = st == "Completed"
    p = np.array([RET_RATE[CATS[k]] for k in cat])
    sel = (comp & (rng.random(len(items)) < p)) | (st == "Returned")
    r = items[sel].copy()
    full = (st[sel] == "Returned")
    odate = pd.to_datetime(o.loc[r.order_id, "order_date"]).to_numpy()
    ch = o.loc[r.order_id, "channel"].to_numpy()
    reasons = np.empty(len(r), dtype=object)
    for is_store in (True, False):
        m = (ch == "In-Store") if is_store else (ch != "In-Store")
        names, pr = REASONS_STORE if is_store else REASONS_ONLINE
        reasons[m] = rng.choice(names, size=m.sum(), p=pr)
    qr = np.where(full, r.quantity.to_numpy(), 1 + (rng.random(len(r)) < 0.25) * (r.quantity.to_numpy() - 1) * rng.random(len(r)))
    qr = np.clip(np.floor(qr).astype(int), 1, r.quantity.to_numpy())
    window = np.where(reasons == "Defective", 30, 14)
    lag = 1 + np.floor(rng.random(len(r)) * window).astype(int)
    odate_s = pd.Series(pd.to_datetime(odate))
    rdate = odate_s + pd.to_timedelta(lag, unit="D")
    rdate = rdate.where(rdate <= pd.Timestamp(R.REF_DATE), pd.Timestamp(R.REF_DATE))
    rdate = rdate.where(rdate >= odate_s, odate_s)
    branch = np.where(ch == "In-Store", o.loc[r.order_id, "branch_id"].to_numpy(), 9)
    refund = round_half_up(r.line_total.to_numpy() * qr / r.quantity.to_numpy(), 2)
    restock = ~np.isin(reasons, ["Defective", "Damaged in Transit"]) & (rng.random(len(r)) < 0.93)
    ret = pd.DataFrame(dict(return_id=np.arange(1, len(r) + 1), order_item_id=r.order_item_id.to_numpy(), order_id=r.order_id.to_numpy(),
                            product_id=r.product_id.to_numpy(), branch_id=branch, return_date=rdate.dt.date, quantity_returned=qr,
                            refund_amount=refund, return_reason=reasons, restocked=restock))
    return ret.sort_values(["return_date", "order_item_id"]).assign(return_id=lambda d: np.arange(1, len(d) + 1)).reset_index(drop=True)
