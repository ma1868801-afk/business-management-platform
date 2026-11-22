"""Channel, store and B2B assignment for the order plan."""
from datetime import date
import numpy as np
import registry as R
from g_reference import DAYS, ND, DAY_INDEX
from g_orders import _sample_days, PERIODS

STORES = ["RYD-OLY", "JED-THL", "RYD-MLQ", "DMM-FSL", "KHB-COR", "MED-QBA", "JED-OBH", "ABH-CTY"]
# target relative store demand (registry base weights; KHB-COR set to 96 percent of DMM-FSL for G-12)
STORE_W = np.array([100, 82, 58, 50, 48, 36, 24, 18], dtype=float)
STORE_REGION = {"RYD-OLY": "Central", "JED-THL": "Western", "RYD-MLQ": "Central", "DMM-FSL": "Eastern",
                "KHB-COR": "Eastern", "MED-QBA": "Western", "JED-OBH": "Western", "ABH-CTY": "Southern"}
# online propensity multiplier, piecewise linear in time (annual means 0.34 / 0.44 / 0.58 give online+app shares of about 15 / 19 / 22.7 percent)
ONLINE_KNOTS = [(date(2024, 1, 1), 0.298), (date(2025, 1, 1), 0.368), (date(2026, 1, 1), 0.520), (date(2026, 10, 31), 0.655)]
B2B_ORDERS = {2024: 330, 2025: 300, 2026: 280}           # orders per calendar year (2026 up to October)
HOME_BONUS, REGION_BONUS = 2.6, 0.7
QBA_BONUS, SUMMER_BONUS = 0.45, 0.55
CH_IN, CH_ON, CH_APP, CH_B2B = 0, 1, 2, 3


def channels(rng, custs, ci, di, season, acq):
    """Channel of each identified order. Online/App more likely for online-affine customers and in White Friday."""
    aff = np.array([c["online_aff"] for c in custs])[ci]
    yr = np.array([DAYS[d].year for d in di])
    scale = np.interp(di, [DAY_INDEX[d] for d, _ in ONLINE_KNOTS], [v for _, v in ONLINE_KNOTS])
    wf = np.array([1.35 if s == "White Friday" else 1.0 for s in season[di]])
    p_on = np.clip(aff * scale * wf, 0, 0.95)
    online = rng.random(len(ci)) < p_on
    acqs = np.array([c["acquisition_channel"] for c in custs])[ci]
    p_app = np.where(acqs == "Mobile App", 0.85, np.where(acqs == "Website", 0.20, 0.45)) + 0.05 * (yr - 2024)
    app = rng.random(len(ci)) < p_app
    ch = np.full(len(ci), CH_IN, dtype=np.int8)
    ch[online & ~app] = CH_ON
    ch[online & app] = CH_APP
    return ch


def b2b_plan(rng, custs, cum_w):
    """Orders of the twelve contract accounts: business days (Sunday to Thursday) after the contract start."""
    ci, di = [], []
    bus = [c for c in custs if c["customer_type"] == "Business"]
    w_acct = np.array([c["credit_limit"] ** 0.75 for c in bus])
    for year, total in B2B_ORDERS.items():
        a = DAY_INDEX[date(year, 1, 1)]
        b = DAY_INDEX[date(year, 12, 31)] if year < 2026 else ND - 1
        days = np.arange(a, b + 1)
        for j, c in enumerate(bus):
            start = max(DAY_INDEX[c["reg"]] if c["reg"] >= DAYS[0] else 0, a)
            act = max(0, b - start + 1) / (b - a + 1)
            share = w_acct[j] * act / sum(w_acct[k] * max(0, b - max(DAY_INDEX.get(bus[k]["reg"], 0) if bus[k]["reg"] >= DAYS[0] else 0, a) + 1) / (b - a + 1) for k in range(len(bus)))
            n = int(rng.poisson(total * share))
            ok = np.array([d for d in days if d >= start and (DAYS[d].weekday() + 1) % 7 not in (5, 6)])
            if len(ok) == 0 or n == 0:
                continue
            pick = rng.choice(ok, size=n, replace=True, p=cum_w[ok] / cum_w[ok].sum())
            ci += [c["idx"]] * n
            di += list(pick)
    return np.array(ci), np.array(di)


def stores(rng, custs, ci, di, season):
    """Store of each identified in-store order. Returns an int array of store indexes (0..7)."""
    home = np.array([STORES.index(c["store"]) for c in custs])[ci]
    reg = np.array([["Central", "Western", "Eastern", "Southern"].index(c["region"]) for c in custs])[ci]
    store_reg = np.array([["Central", "Western", "Eastern", "Southern"].index(STORE_REGION[s]) for s in STORES])
    month = np.array([DAYS[d].month for d in di])
    seas = season[di]
    base = np.zeros((len(ci), 8))
    base[np.arange(len(ci)), home] += HOME_BONUS
    base += REGION_BONUS * (store_reg[None, :] == reg[:, None])
    ramhajj = np.isin(seas, ["Ramadan", "Eid al-Fitr", "Hajj and Eid al-Adha"])
    base[:, STORES.index("MED-QBA")] += QBA_BONUS * ramhajj
    summer = np.isin(month, [6, 7, 8])
    base[:, STORES.index("ABH-CTY")] += SUMMER_BONUS * summer
    base[:, STORES.index("JED-OBH")] += SUMMER_BONUS * summer
    logm = np.zeros(8)
    target = STORE_W / STORE_W.sum()
    for _ in range(12):                                     # iterative proportional fitting of store shares
        z = base + logm[None, :]
        p = np.exp(z - z.max(axis=1, keepdims=True))
        p /= p.sum(axis=1, keepdims=True)
        share = p.sum(axis=0) / len(ci)
        logm += 0.9 * np.log(target / share)
    z = base + logm[None, :]
    p = np.exp(z - z.max(axis=1, keepdims=True))
    p /= p.sum(axis=1, keepdims=True)
    cpf = p.cumsum(axis=1)
    u = rng.random(len(ci))[:, None]
    return (u > cpf).sum(axis=1).clip(0, 7), logm


def anon_orders(rng, di_in, st_in, season, w_in, share=0.08):
    """Anonymous in-store orders: 8 percent of all in-store orders, same month and store distribution as identified ones."""
    n = int(round(len(di_in) * share / (1 - share)))
    cum = np.cumsum(w_in)
    ym = np.array([DAYS[d].year * 100 + DAYS[d].month for d in range(ND)])
    pool = {}
    for d, s in zip(di_in, st_in):
        pool.setdefault(ym[d], []).append(s)
    # days: draw by in-store weights but proportional to identified orders per month
    months, counts = np.unique(ym[di_in], return_counts=True)
    out_d, out_s = [], []
    for m, c in zip(months, counts):
        k = int(round(c * share / (1 - share)))
        idx = np.where(ym == m)[0]
        out_d += list(_sample_days(rng, cum, idx[0], idx[-1], k))
        out_s += list(rng.choice(pool[m], size=k))
    return np.array(out_d), np.array(out_s)


if __name__ == "__main__":
    import g_customers as GC
    import g_orders as GO
    from g_reference import calendar_rows
    rng = np.random.default_rng(11)
    custs = GC.build(rng)
    w_in, w_on, cal = GO.day_weights()
    season = np.array([c["season"] for c in cal])
    ci, di, ki, fi = GO.plan(rng, custs, w_in, w_on)
    ch = channels(rng, custs, ci, di, season, None)
    yr = np.array([DAYS[d].year for d in di])
    for y in (2024, 2025, 2026):
        m = yr == y
        print(y, "online+app order share", round(float((ch[m] > 0).mean()), 3))
    ins = ch == CH_IN
    st, logm = stores(rng, custs, ci[ins], di[ins], season)
    print({s: int((st == i).sum()) for i, s in enumerate(STORES)})
    ad, ast = anon_orders(rng, di[ins], st, season, w_in)
    print("anon", len(ad), round(len(ad) / (len(ad) + ins.sum()), 3))
    bc, bd = b2b_plan(rng, custs, np.cumsum(w_in))
    print("b2b", len(bc))
