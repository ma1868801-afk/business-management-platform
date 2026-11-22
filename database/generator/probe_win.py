import numpy as np, assemble as A, g_inventory as I
from datetime import date
S = A.run(); L, O, prods, sups = S["L"], S["O"], S["prods"], S["sups"]
dc = O["store"][L["order"]] == I.DC
day = O["day"][L["order"]]
y0, y1 = I.DAY_INDEX[date(2025,1,1)], I.DAY_INDEX[date(2025,12,31)]
rows = []
for p, pr in enumerate(prods):
    if pr["lifecycle_status"] != "Active" or pr["launch_date"] > date(2024,3,1) or pr["sku"] in I.DEAD or pr["is_seasonal"]: continue
    if pr["sku"] in sum(I.MUST.values(), []): continue
    m = (L["prod"] == p) & dc
    d25 = m & (day >= y0) & (day <= y1)
    u25 = int(L["qty"][d25].sum()); dd = len(np.unique(day[d25]))
    moq = sups[pr["supplier_id"]-1]["min_order_qty"]
    rows.append((pr["sku"], u25, dd, moq, round(u25/moq,1)))
rows.sort(key=lambda r: -r[4])
print(len(rows))
for r in rows[:60]: print(r)
