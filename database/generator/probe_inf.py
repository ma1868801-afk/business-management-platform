import sys, numpy as np, pandas as pd, assemble as A, g_finalize as F, g_targets as T
for sd in [int(x) for x in sys.argv[1:]]:
    S = A.run(seed=sd); rng = S["rng"]
    orders, items = F.finalize(S, rng)
    tg, df = T.make_targets(rng, orders)
    bad = df[~(df.a < df.z)]
    print("seed", sd, "infeasible", len(bad))
    print(bad[["b", "m", "q25", "q26", "a", "z"]].round(3).to_string())
