import sys, numpy as np, assemble as A, g_steer as GS, g_balance as GB2, g_orders as GO
from g_reference import DAYS
YR = np.array([d.year for d in DAYS]); MO = np.array([d.month for d in DAYS])
def yr_rev(tag, O, L):
    n = len(O["day"])
    val = GS.order_values(L, n)
    d = O["day"]
    r24 = val[YR[d] == 2024].sum(); r25 = val[YR[d] == 2025].sum()
    r25y = val[(YR[d] == 2025) & (MO[d] <= 10)].sum(); r26 = val[YR[d] == 2026].sum()
    print(f"{tag:14s} n={n:7d} 24={r24/1e6:6.2f} 25={r25/1e6:6.2f} 25ytd={r25y/1e6:6.2f} 26={r26/1e6:6.2f}  g25={100*(r25/r24-1):5.1f}  g26={100*(r26/r25y-1):5.1f}")
o_steer, o_fit, o_bal = GS.steer, GS.fit_anon, GB2.balance
def steer(rng, custs, O, L):
    yr_rev("pre-steer", O, L)
    out = o_steer(rng, custs, O, L); yr_rev("post-steer", *out[0]); return out
def fit(rng, O, L):
    out = o_fit(rng, O, L); yr_rev("post-fit_anon", *out); return out
def bal(*a, **k):
    out = o_bal(*a, **k); yr_rev("post-balance", out[0], out[1]); print("   balance stats", out[2]); return out
A.GS.steer, A.GS.fit_anon, A.GB2.balance = steer, fit, bal
knot = float(sys.argv[1])
GO.G_KNOTS[2] = (GO.G_KNOTS[2][0], knot)
S = A.run()
yr_rev("final", S["O"], S["L"])
