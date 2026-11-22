import numpy as np, assemble as A, g_baskets as GB
S = A.run(); O, L, model = S["O"], S["L"], S["model"]
val = L["qty"] * L["price"] * (1 - L["disc"] / 100)
cat = model.cat[L["prod"]]
tot = val.sum(); lines = len(cat); units = L["qty"].sum()
biz = (O["kind"] == 2)[L["order"]]
print("share of B2B units", round(L["qty"][biz].sum() / units, 3), "rev", round(val[biz].sum() / tot, 3))
nb = ~biz
print("non-B2B units/line", round(L["qty"][nb].mean(), 2))
for k, c in enumerate(GB.CATS):
    m = cat == k
    print(c, "lines", round(m.mean(), 3), "units", round(L["qty"][m].sum() / units, 3), "rev", round(val[m].sum() / tot, 3),
          "avg price", round(float((L["price"][m]).mean())), "avg net unit", round(val[m].sum() / L["qty"][m].sum()), "disc>0", round(float((L["disc"][m] > 0).mean()), 2))
print("disc lines share", round(float((L["disc"] > 0).mean()), 3), "qty promo lines", round(float(L["qty"][L["disc"] > 0].mean()), 2), "non-promo", round(float(L["qty"][L["disc"] == 0].mean()), 2))
