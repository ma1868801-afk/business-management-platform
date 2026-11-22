"""Order plan: which customer orders on which day (before channel, branch and basket)."""
from datetime import date, timedelta
import numpy as np
import registry as R
from g_reference import DAYS, ND, DAY_INDEX, calendar_rows

END = ND - 1
D = lambda y, m, d: DAY_INDEX[date(y, m, d)]
PERIODS = {"P24": (D(2024, 1, 1), D(2024, 12, 31)), "P25a": (D(2025, 1, 1), D(2025, 10, 31)),
           "P25b": (D(2025, 11, 1), D(2025, 12, 31)), "P26": (D(2026, 1, 1), D(2026, 10, 31))}
TTM0 = D(2025, 11, 1)
# average basket value assumed when turning a spend target into an order count (calibrated against the baskets)
AOVC = {"PL": 780.0, "GD": 740.0, "SE": 680.0}
# TTM spend targets (the steering step trims the over-planned orders so that the realised spend lands close to the target)
SPEND = {"PL": (25700, 26800), "GD": (10400, 11300), "SE": (3150, 3700)}
OVER_PRE = 1.12      # the earlier periods are over-planned too; assemble thins them to the revenue implied by the growth targets
OVER = 1.45          # over-planning factor for the trailing-12-month window; steering removes the surplus orders
RATE_CAP = 48.0      # orders per year
# activity of the same customer relative to the last 12 months: customers registered before 2025 slow down over time
# activity multiplier of customers registered before 2025 (piecewise linear in time; mean over the last 12 months is about 1)
G_KNOTS = [(date(2024, 1, 1), 1.80), (date(2024, 12, 31), 1.75), (date(2025, 10, 31), 1.70), (date(2026, 2, 28), 1.02), (date(2026, 10, 31), 0.78)]

DOW_W = np.array([0.93, 0.93, 0.93, 0.96, 1.00, 1.38, 1.32])      # Sunday..Saturday, in-store
DOW_ON = np.array([1.0, 0.98, 0.98, 1.0, 1.05, 1.12, 1.10])        # online and app
SEASON_W = {"White Friday": 2.5, "Eid al-Fitr": 1.35, "Hajj and Eid al-Adha": 1.2, "Ramadan": 1.12, "National Day": 1.2,
            "Founding Day": 1.1, "Back to School": 1.08, "Summer": 0.92, "Winter": 1.0, "Regular": 1.0}
PAYDAY_W = 1.38


def day_weights():
    cal = calendar_rows()
    w_in = np.zeros(ND)
    w_on = np.zeros(ND)
    for i, c in enumerate(cal):
        s = SEASON_W[c["season"]] * (PAYDAY_W if c["is_payday"] else 1.0)
        w_in[i] = DOW_W[c["day_of_week"]] * s
        w_on[i] = DOW_ON[c["day_of_week"]] * s
    return w_in, w_on, cal


def month_end_idx(i):
    d = DAYS[i]
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return min(DAY_INDEX.get(nxt - timedelta(days=1), END), END)


def month_add_start(i, k):
    """Day index of the first day of the month k months after the month of day i (clipped to END+1)."""
    d = DAYS[i]
    m0 = d.year * 12 + d.month - 1 + k
    y, m = divmod(m0, 12)
    t = date(y, m + 1, 1)
    return DAY_INDEX.get(t, END + 1) if t <= DAYS[-1] else END + 1


def _sample_days(rng, cum, a, b, n):
    """n days in [a, b] with probability proportional to the weights (cum is the cumulative weight array)."""
    if n <= 0 or b < a:
        return np.empty(0, dtype=int)
    lo = cum[a - 1] if a > 0 else 0.0
    u = rng.uniform(lo, cum[b], size=n)
    return np.minimum(np.searchsorted(cum, u, side="right"), b)


def _count(rng, mu):
    """Low-variance count: floor(mu) plus a Bernoulli on the fraction."""
    if mu <= 0:
        return 0
    f = int(np.floor(mu))
    return f + int(rng.random() < mu - f)


def plan(rng, custs, w_in, w_on):
    """Return arrays (cust_idx, day_idx, kind, first) for individual customers. kind: 0 normal, 1 big-ticket."""
    base = 0.5 * (w_in + w_on)
    cum = np.cumsum(base)
    g_old = np.interp(np.arange(ND), [DAY_INDEX[d] for d, _ in G_KNOTS], [v for _, v in G_KNOTS])
    cum_old = np.cumsum(base * g_old)
    gcum = np.concatenate([[0.0], np.cumsum(g_old)])       # gcum[i + 1] - gcum[a] = sum of g over days a..i
    ci, di, ki, fi = [], [], [], []
    for c in custs:
        if c["customer_type"] != "Individual":
            continue
        cl, reg = c["cls"], c["reg"]
        r0 = DAY_INDEX[reg] if reg >= DAYS[0] else -1           # -1: registered before the data starts
        in_data = r0 >= 0
        own = []                                               # (day, kind, first)
        first_day = None
        if in_data:
            span = month_end_idx(r0) - r0
            first_day = r0 + int(rng.integers(0, min(span, 3) + 1))
        later_from = month_add_start(r0, 4) if in_data else 0   # for casual customers: nothing in months M+1..M+3
        eff = max(r0 + 1, 0) if in_data else 0
        if cl in ("PL", "GD", "SE"):
            lo, hi = SPEND[cl]
            target = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
            tau = max((END - max(eff, TTM0) + 1) / 365.0, 0.25)
            n_ttm = target / AOVC[cl]
            rate = min(n_ttm / tau, RATE_CAP)
            c["rate"], c["target"] = rate, target
            if in_data:
                own.append((first_day, 0, 1))
            old = reg.year < 2025
            cw = cum_old if old else cum
            for p, (a, b) in PERIODS.items():
                a2, b2 = max(a, eff), b
                if b2 < a2:
                    continue
                span = (gcum[b2 + 1] - gcum[a2]) if old else (b2 - a2 + 1)
                mu = rate * (OVER if p in ("P25b", "P26") else OVER_PRE) * span / 365.0
                for d in _sample_days(rng, cw, a2, b2, _count(rng, mu)):
                    own.append((int(d), 0, 0))
            if in_data and reg.year >= 2025:                    # engaged customers order again within three months
                a, b = r0 + 1, min(month_add_start(r0, 4) - 1, END)
                a = max(a, month_add_start(r0, 1))
                if b >= a and not any(a <= d <= b for d, _, _ in own):
                    own.append((int(_sample_days(rng, cum, a, b, 1)[0]), 0, 2))
                elif b >= a:                                      # an ordinary order already falls in the window: protect one
                    k = next(j for j, (d, _, _) in enumerate(own) if a <= d <= b)
                    own[k] = (own[k][0], 0, 2)
        elif cl == "SB":
            if in_data:
                own.append((first_day, 0, 1))
            else:                                                # old customers: occasional ordinary purchases
                for p in ("P24", "P25a"):
                    a, b = PERIODS[p]
                    if rng.random() < (0.60 if p == "P24" else 1.0):
                        own.append((int(_sample_days(rng, cum, a, b, 1)[0]), 0, 3))
            if reg.year == 2024 and rng.random() < 0.95:
                a, b = max(later_from, PERIODS["P25a"][0]), PERIODS["P25a"][1]
                if b >= a:
                    own.append((int(_sample_days(rng, cum, a, b, 1)[0]), 0, 3))
            a = max(PERIODS["P26"][0], later_from)
            if a <= END:
                own.append((int(_sample_days(rng, cum, a, END, 1)[0]), 1, 0))
            elif in_data:                                        # registered too late: the first order is the big one
                own[0] = (first_day, 1, 1)
        elif cl == "NC":
            if in_data:
                own.append((first_day, 0, 1))
                if reg.year == 2024:                              # most casual customers of 2024 buy once more in 2025
                    a = max(later_from, PERIODS["P25a"][0])
                    if a <= PERIODS["P25a"][1] and rng.random() < 0.85:
                        own.append((int(_sample_days(rng, cum, a, PERIODS["P25a"][1], 1)[0]), 0, 3))
                elif later_from <= END and rng.random() < 0.20:
                    own.append((int(_sample_days(rng, cum, later_from, min(END, later_from + 300), 1)[0]), 0, 3))
            else:
                for p, pr in (("P24", 0.50), ("P25a", 1.0), ("P26", 0.22)):
                    a, b = PERIODS[p]
                    if rng.random() < pr:
                        own.append((int(_sample_days(rng, cum, a, b, 1)[0]), 0, 3))
        elif cl == "NL":
            a, b = PERIODS["P24"]
            if in_data:
                own.append((first_day, 0, 1))
            elif rng.random() < 0.7:
                own.append((int(_sample_days(rng, cum, a, b, 1)[0]), 0, 3))
            if rng.random() < 0.70:
                a, b = PERIODS["P25a"][0], D(2025, 6, 30)
                a = max(a, eff, later_from)
                if b >= a:
                    own.append((int(_sample_days(rng, cum, a, b, 1)[0]), 0, 3))
        for d, k, f in own:
            ci.append(c["idx"]); di.append(d); ki.append(k); fi.append(f)
    return np.array(ci), np.array(di), np.array(ki, dtype=np.int8), np.array(fi, dtype=np.int8)


if __name__ == "__main__":
    import g_customers as GC
    rng = np.random.default_rng(11)
    custs = GC.build(rng)
    w_in, w_on, cal = day_weights()
    ci, di, ki, fi = plan(rng, custs, w_in, w_on)
    yr = np.array([DAYS[d].year for d in di])
    cls = np.array([custs[i]["cls"] for i in ci])
    print("identified individual orders", len(ci), {y: int((yr == y).sum()) for y in (2024, 2025, 2026)})
    for c in ("PL", "GD", "SE", "SB", "NC", "NL"):
        m = cls == c
        print(c, int(m.sum()), "orders; ttm", int(((di >= TTM0) & m).sum()), "big", int(((ki == 1) & m).sum()))
