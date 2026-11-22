"""Monthly sales targets (guarantee G-29): target(year) = 1.10 x target(year - 1); 2024 is the planning baseline."""
import numpy as np
import pandas as pd


def make_targets(rng, orders):
    c = orders[orders.status == "Completed"].copy()
    c["ym"] = pd.to_datetime(c.order_date).dt.to_period("M")
    rev = c.groupby(["branch_id", "ym"]).subtotal_amount.sum()
    rows, info = [], []
    lo, hi = 0.806, 1.194
    for b in range(1, 10):
        for m in range(1, 11 if True else 13):
            pass
    cells = []
    for b in range(1, 10):
        for m in range(1, 13):
            r24 = rev.get((b, pd.Period(f"2024-{m:02d}")), np.nan)
            r25 = rev.get((b, pd.Period(f"2025-{m:02d}")), np.nan)
            r26 = rev.get((b, pd.Period(f"2026-{m:02d}")), np.nan) if m <= 10 else np.nan
            q25 = r25 / r24 / 1.10
            q26 = (r26 / r25 / 1.10) * q25 if m <= 10 else np.nan
            ivs = [(lo, hi), (lo / q25, hi / q25)] + ([(lo / q26, hi / q26)] if m <= 10 else [])
            a, z = max(i[0] for i in ivs), min(i[1] for i in ivs)
            cells.append(dict(b=b, m=m, r24=r24, r25=r25, r26=r26, q25=q25, q26=q26, a=a, z=z))
    df = pd.DataFrame(cells)
    feasible = df.a < df.z
    # choose attainment of 2024 inside the feasible interval; make the spread wide enough for the guarantee
    u = rng.random(len(df))
    pick = np.where(feasible, df.a + u * (df.z - df.a), (df.a + df.z) / 2)
    df["a24"] = pick
    # Oct 2026: four locations miss, four meet (the ninth is free)
    oct_ = df[df.m == 10].index.tolist()
    order = rng.permutation(len(oct_))
    for rank, j in enumerate(order):
        i = oct_[j]
        if not feasible[i]:
            continue
        a26_lo, a26_hi = df.a[i] * df.q26[i], df.z[i] * df.q26[i]
        want_miss = rank < 4
        want_meet = 4 <= rank < 8
        if want_miss and a26_lo < 0.985:
            df.loc[i, "a24"] = (df.a[i] + min(df.z[i], 0.985 / df.q26[i])) / 2
        if want_meet and a26_hi > 1.02:
            df.loc[i, "a24"] = (max(df.a[i], 1.02 / df.q26[i]) + df.z[i]) / 2
    df["t24"] = df.r24 / df.a24
    out = []
    tid = 0
    for b in range(1, 10):
        t = {}
        for y in (2024, 2025, 2026):
            for m in range(1, 13):
                if y == 2026 and m > 10:
                    continue
                i = df[(df.b == b) & (df.m == m)].index[0]
                base = round(float(df.t24[i]), 2) if y == 2024 else round(t[(y - 1, m)] * 1.10, 2)
                t[(y, m)] = base
                tid += 1
                out.append(dict(target_id=tid, branch_id=b, target_month=pd.Timestamp(y, m, 1).date(), target_revenue=base))
    tg = pd.DataFrame(out)
    tg = tg.sort_values(["target_month", "branch_id"]).assign(target_id=lambda d: np.arange(1, len(d) + 1)).reset_index(drop=True)
    return tg, df
