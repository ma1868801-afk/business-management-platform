"""Development tool: adjust LINE_PROB so that realised line shares by product line equal LINE_PROB_TARGET."""
import numpy as np, assemble as A, g_baskets as GB
for it in range(4):
    S = A.run(verbose=False); L, O, model = S["L"], S["O"], S["model"]
    nb = ~(O["kind"] == 2)[L["order"]]
    cat = model.cat[L["prod"]][nb]
    share = np.bincount(cat, minlength=8) / nb.sum()
    err = []
    for k, c in enumerate(GB.CATS):
        GB.LINE_PROB[c] *= (GB.LINE_PROB_TARGET[c] / share[k]) ** 0.9
        err.append(share[k] - GB.LINE_PROB_TARGET[c])
    print(it, "max abs share error", round(float(np.abs(err).max()), 4))
tot = sum(GB.LINE_PROB.values())
print("LINE_PROB =", {c: round(v / tot, 4) for c, v in GB.LINE_PROB.items()})
