"""Customers: 12 contract business accounts + 5,988 individuals with an activity plan.

Activity classes (individuals) are the device that makes G-20 (tiers from trailing 12-month spend), G-21, G-22 (repeat
rate, cohort re-order) and G-09 (volumes) hold together. The class is a planning attribute only; it is not stored.
  PL  frequent, targets Platinum      GD  frequent, targets Gold       SE  regular, targets Silver
  SB  annual buyer, one big-ticket order in the last 12 months (Silver)
  NC  casual, small spend (None)      NL  lapsed, no orders in the last 12 months (None)
"""
from datetime import date, timedelta
import numpy as np
import registry as R
from g_reference import DAY_INDEX, DAYS

TTM_START = date(2025, 11, 1)

# registrations by calendar year (individuals). 2026 covers January to October.
REG_COUNTS = {2019: 250, 2020: 330, 2021: 400, 2022: 500, 2023: 600, 2024: 800, 2025: 2000, 2026: 1108}
# class mix per registration group (fractions; remainder is NC)
CLASS_MIX = {
    "old":  dict(PL=0.125, GD=0.315, SE=0.015, SB=0.200, NL=0.070),     # registered 2019-2023
    "y24":  dict(PL=0.140, GD=0.350, SE=0.030, SB=0.200, NL=0.040),
    "y25":  dict(PL=0.028, GD=0.085, SE=0.160, SB=0.210, NL=0.0),
    "y26":  dict(PL=0.010, GD=0.055, SE=0.215, SB=0.235, NL=0.0),
}
# target spend in the trailing 12 months (SAR): (low, high, shape) -> drawn log-uniformly inside the range
SPEND = {"PL": (25500, 36000), "GD": (10300, 17500), "SE": (3200, 6800)}
KAPPA = {"PL": -0.01, "GD": -0.03, "SE": -0.06, "SB": -0.11, "NC": -0.19, "NL": -0.04}   # price-affinity exponent
FIRST = ["Abdullah", "Mohammed", "Fahad", "Saud", "Khalid", "Sultan", "Turki", "Nawaf", "Majed", "Bader", "Hamad", "Salman",
         "Yazeed", "Rayan", "Talal", "Ziyad", "Mishal", "Anas", "Ibrahim", "Omar", "Ali", "Hassan", "Faisal", "Nasser",
         "Noura", "Sara", "Lama", "Reem", "Hessa", "Maha", "Dalal", "Amal", "Haya", "Jawaher", "Abeer", "Rana", "Shahad",
         "Lina", "Ghada", "Mona", "Nada", "Rawan", "Joud", "Maryam", "Fatimah", "Aisha", "Layan", "Dana", "Razan", "Hanan"]
LAST = ["Al-Otaibi", "Al-Qahtani", "Al-Ghamdi", "Al-Harbi", "Al-Zahrani", "Al-Shehri", "Al-Dossary", "Al-Mutairi",
        "Al-Anazi", "Al-Subaie", "Al-Juhani", "Al-Malki", "Al-Shammari", "Al-Rashid", "Al-Tamimi", "Al-Yami", "Al-Balawi",
        "Al-Enezi", "Al-Khaldi", "Al-Harthi", "Al-Asmari", "Al-Najjar", "Al-Fahad", "Al-Mansour", "Al-Sheikh", "Al-Bishi",
        "Al-Hamdan", "Al-Rowaili", "Al-Thaqafi", "Al-Dakheel", "Bakr", "Haddad", "Khoury", "Al-Zamil", "Al-Rajhi", "Al-Sulami"]
REGIONS = ["Central", "Western", "Eastern", "Southern"]
REGION_P = [0.40, 0.30, 0.20, 0.10]
CITIES = {
    "Central": (["Riyadh", "Buraydah", "Hail"], [0.90, 0.06, 0.04]),
    "Western": (["Jeddah", "Madinah", "Makkah", "Taif"], [0.62, 0.24, 0.10, 0.04]),
    "Eastern": (["Dammam", "Al Khobar", "Al Ahsa", "Jubail"], [0.45, 0.40, 0.10, 0.05]),
    "Southern": (["Abha", "Khamis Mushait", "Jazan", "Najran"], [0.60, 0.25, 0.10, 0.05]),
}
# preferred store by city: list of (store code, probability)
HOME_STORE = {
    "Riyadh": [("RYD-OLY", 0.62), ("RYD-MLQ", 0.38)], "Buraydah": [("RYD-OLY", 1.0)], "Hail": [("RYD-OLY", 1.0)],
    "Jeddah": [("JED-THL", 0.77), ("JED-OBH", 0.23)], "Madinah": [("MED-QBA", 1.0)], "Makkah": [("JED-THL", 1.0)],
    "Taif": [("JED-THL", 1.0)], "Dammam": [("DMM-FSL", 1.0)], "Al Khobar": [("KHB-COR", 1.0)],
    "Al Ahsa": [("DMM-FSL", 0.5), ("KHB-COR", 0.5)], "Jubail": [("DMM-FSL", 0.5), ("KHB-COR", 0.5)],
    "Abha": [("ABH-CTY", 1.0)], "Khamis Mushait": [("ABH-CTY", 1.0)], "Jazan": [("ABH-CTY", 1.0)], "Najran": [("ABH-CTY", 1.0)],
}
ACQ = ["Walk-in", "Website", "Mobile App", "Social Media", "Referral"]


def _reg_dates(rng):
    """Registration dates with fixed quotas per calendar month (2025 and 2026 never below 100 per month)."""
    out = []
    for y, n in REG_COUNTS.items():
        months = list(range(1, 13)) if y < 2026 else list(range(1, 11))
        base, extra = divmod(n, len(months))
        counts = [base + (1 if i < extra else 0) for i in range(len(months))]
        for m, c in zip(months, counts):
            last = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)).day
            days = rng.integers(1, last + 1, size=c)
            out += [date(y, m, int(d)) for d in days]
    return out


def _class_for(group, k, rng):
    """Exact class quotas for a group of size k."""
    mix = CLASS_MIX[group]
    labels, left = [], k
    for c in ("PL", "GD", "SE", "SB", "NL"):
        n = int(round(mix.get(c, 0) * k))
        labels += [c] * n
        left -= n
    labels += ["NC"] * max(left, 0)
    labels = labels[:k]
    rng.shuffle(labels)
    return labels


def build(rng):
    """Return (customers list of dict incl. planning fields)."""
    regs = _reg_dates(rng)
    assert len(regs) == 5988
    regs.sort()
    n = len(regs)
    group = np.array(["old" if d.year <= 2023 else f"y{d.year % 100}" for d in regs])
    cls = np.empty(n, dtype="U2")
    # class quotas are applied per registration month for 2025 and 2026 so that every monthly cohort has the same mix
    ym = np.array([d.year * 100 + d.month for d in regs])
    for g in ("old", "y24"):
        idx = np.where(group == g)[0]
        cls[idx] = _class_for(g, len(idx), rng)
    for g in ("y25", "y26"):
        for key in np.unique(ym[group == g]):
            idx = np.where((group == g) & (ym == key))[0]
            cls[idx] = _class_for(g, len(idx), rng)
    # late 2026 registrants cannot reach the spend of the higher classes within the window: move them one class down
    for i, d in enumerate(regs):
        if d.year == 2026:
            c = str(cls[i])
            c = "GD" if (c == "PL" and d > date(2026, 2, 28)) else c
            c = "SE" if (c == "GD" and d > date(2026, 7, 31)) else c
            c = "NC" if (c == "SE" and d > date(2026, 9, 15)) else c
            cls[i] = c
    rows = []
    for i in range(n):
        reg = regs[i]
        region = REGIONS[int(rng.choice(4, p=REGION_P))]
        cities, cp = CITIES[region]
        city = cities[int(rng.choice(len(cities), p=cp))]
        stores = HOME_STORE[city]
        store = stores[int(rng.choice(len(stores), p=[p for _, p in stores]))][0]
        online_aff = float(np.clip(rng.beta(1.6, 3.2) + (0.20 if region == "Southern" else 0.0) + 0.04 * (reg.year - 2019) / 7, 0.02, 0.97))
        c = str(cls[i])
        rows.append(dict(idx=i, reg=reg, cls=c, region=region, city=city, store=store, online_aff=online_aff,
                         kappa=KAPPA[c] + float(rng.normal(0, 0.05))))
    # demographics and attributes
    for i, r in enumerate(rows):
        r["customer_id"] = i + 1
        r["customer_code"] = f"CUST-{i + 1:06d}"
        r["customer_type"] = "Individual"
        r["full_name"] = f"{FIRST[int(rng.integers(0, len(FIRST)))]} {LAST[int(rng.integers(0, len(LAST)))]}"
        g = rng.random()
        r["gender"] = "Female" if g < 0.52 else "Male" if g < 0.99 else None
        r["age_group"] = ["18-24", "25-34", "35-44", "45-54", "55+"][int(rng.choice(5, p=[0.14, 0.32, 0.28, 0.16, 0.10]))]
        w = np.array([0.30 - 0.10 * (r["reg"].year - 2019) / 7, 0.20 + 0.06 * (r["reg"].year - 2019) / 7,
                      0.14 + 0.07 * (r["reg"].year - 2019) / 7, 0.19, 0.17])
        w = w / w.sum()
        r["acquisition_channel"] = ACQ[int(rng.choice(5, p=w))]
        seg = rng.random()
        pm = {"PL": 0.55, "GD": 0.35, "SE": 0.12, "SB": 0.10, "NC": 0.03, "NL": 0.02}[r["cls"]]
        r["customer_segment"] = "Premium" if seg < pm else ("Core" if rng.random() < 0.62 else "Occasional")
        r["marketing_opt_in"] = bool(rng.random() < 0.65)
        r["contract_number"] = None
        r["credit_limit"] = None
        r["payment_terms_days"] = None
        r["email"] = f"customer{i + 1:06d}@mail.example"
        r["phone"] = f"+9665500{int(rng.integers(0, 10**5)):05d}"
        r["is_active"] = True
    # business customers
    base_id = len(rows)
    for j, b in enumerate(R.BUS_CUSTOMERS):
        stores = HOME_STORE[b["city"]]
        slug = "".join(ch for ch in b["name"].lower() if ch.isalnum())[:24]
        rows.append(dict(idx=base_id + j, customer_id=base_id + j + 1, customer_code=b["code"], customer_type="Business",
                         full_name=b["name"], gender=None, age_group=None, city=b["city"], region=b["region"],
                         customer_segment="Premium", reg=b["start"], acquisition_channel="B2B Sales",
                         store=stores[0][0], marketing_opt_in=bool(j % 2 == 0), contract_number=b["contract"],
                         credit_limit=float(b["credit"]), payment_terms_days=b["days"], email=f"procurement@{slug}.example",
                         phone=f"+9661100{j:05d}", is_active=True, cls="BZ", online_aff=0.0, kappa=0.0, biz=b))
    return rows


if __name__ == "__main__":
    from collections import Counter
    rng = np.random.default_rng(7)
    cs = build(rng)
    print(len(cs), Counter(c["cls"] for c in cs))
    print(Counter(c["region"] for c in cs if c["customer_type"] == "Individual"))
