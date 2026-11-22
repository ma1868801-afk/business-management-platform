import time, numpy as np, assemble as A, g_finalize as F, g_targets as T, quick_checks as Q
t0 = time.time()
S = A.run()
rng = S["rng"]
orders, items = F.finalize(S, rng)
returns = F.make_returns(rng, S, orders, items)
targets, _ = T.make_targets(rng, orders)
print("built in", round(time.time() - t0, 1), "s")
Q.run(S, orders, items, returns, targets)
