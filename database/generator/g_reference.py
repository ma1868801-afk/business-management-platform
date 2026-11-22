"""Reference tables: branches, categories, suppliers, products (with price history), promotions, calendar."""
from datetime import date, timedelta
import numpy as np
import registry as R

DAYS = [R.DATA_START + timedelta(days=i) for i in range((R.REF_DATE - R.DATA_START).days + 1)]
ND = len(DAYS)
assert ND == 1035
DAY_INDEX = {d: i for i, d in enumerate(DAYS)}
LINE_IDS = {l[1]: l[0] for l in R.LINES}


def branches():
    rows = []
    for i, b in enumerate(R.BRANCHES, start=1):
        code, name, city, region, btype, opened, area, staff, mgr, hours, w = b
        rows.append(dict(branch_id=i, branch_code=code, branch_name=name, city=city, region=region, branch_type=btype,
                         opening_date=opened, area_sqm=area, staff_count=staff, manager_name=mgr,
                         fulfills_online=(code == "RYD-DC"), opening_hours=hours, is_active=True, weight=w))
    return rows


def categories():
    return [dict(category_id=l[0], category_code=l[1], category_name=l[2], department=l[3], target_margin_pct=l[4],
                 peak_season=l[5], description=l[9]) for l in R.LINES]


def suppliers():
    rows = []
    for s in R.SUPPLIERS:
        rows.append(dict(supplier_id=s["idx"], supplier_code=s["code"], supplier_name=s["name"], country=s["country"],
                         city=s["city"], primary_category_id=LINE_IDS[s["line"]], lead_time_days=s["lead"],
                         min_order_qty=s["moq"], payment_terms_days=s["terms"], on_time_delivery_pct=s["otd"],
                         quality_rating=s["quality"], billing_currency=s["currency"], contract_number=s["contract"],
                         contract_start_date=s["start"], contract_end_date=s["end"], is_active=True))
    return rows


WEIGHT_RANGE = {"ELEC": (0.1, 25), "APPL": (2, 70), "FASH": (0.2, 2), "GROC": (0.3, 6), "BEAU": (0.05, 1.5),
                "SPRT": (0.3, 25), "KIDS": (0.1, 8), "HOME": (0.5, 40)}
HEAVY = {"Smartphones": (0.2, 0.3), "Laptops and Tablets": (0.5, 2.5), "TV and Display": (9, 22), "Large Appliances": (45, 80),
         "Cooling and Fans": (4, 60), "Furniture": (8, 40), "Rugs": (12, 20), "Fitness Equipment": (0.2, 90),
         "Cycling": (0.4, 14)}
ORIGIN = {"ELEC": "China", "APPL": "China", "FASH": None, "GROC": None, "BEAU": None, "SPRT": None, "KIDS": "China", "HOME": None}


def products(rng):
    """Return product rows (without unit_cost) plus price schedule arrays."""
    rows, sched = [], []
    sup_id = {s["code"]: s["idx"] for s in R.SUPPLIERS}
    for i, s in enumerate(R.SKUS, start=1):
        lo, hi = HEAVY.get(s["sub"], WEIGHT_RANGE[s["line"]])
        w = round(float(rng.uniform(lo, hi)), 2) if hi > 1 else round(float(rng.uniform(lo, hi)), 2)
        sup = R.SUP[s["supplier"]]
        origin = ORIGIN[s["line"]] or sup["country"]
        rows.append(dict(product_id=i, sku=s["sku"], product_name=s["name"], category_id=LINE_IDS[s["line"]],
                         subcategory=s["sub"], brand=s["brand"], supplier_id=sup_id[s["supplier"]], unit_cost=None,
                         unit_price=float(s["price"]), unit_of_measure=s["uom"], shelf_life_days=s["shelf"],
                         is_seasonal=s["seasonal"], peak_season=s["peak"], lifecycle_status=s["status"],
                         launch_date=s["launch"], discontinued_date=s["discontinued"], weight_kg=w, origin_country=origin))
    return rows


def price_table(rng, prod_rows):
    """price[p, d] in SAR (excl. VAT) for product index p (0-based) and day index d. Up to two rises of 2-6 percent."""
    price = np.zeros((len(prod_rows), ND))
    events = []
    for p, row in enumerate(prod_rows):
        cur = row["unit_price"]
        n_ev = int(rng.choice([0, 1, 2], p=[0.30, 0.40, 0.30]))
        first = max(row["launch_date"], R.DATA_START)
        dates, facs = [], []
        windows = [(date(2024, 5, 1), date(2025, 2, 28)), (date(2025, 6, 1), date(2026, 6, 30))]
        if n_ev == 1:
            windows = [windows[int(rng.integers(0, 2))]]
        for k in range(n_ev):
            a, b = windows[k]
            a = max(a, first + timedelta(days=60))
            if a >= b:
                continue
            d = a + timedelta(days=int(rng.integers(0, (b - a).days)))
            dates.append(d)
            facs.append(1.0 + float(rng.uniform(0.02, 0.06)))
        series = np.full(ND, cur)
        # walk back from the current price: before each event date the price is lower by that factor
        for d, f in sorted(zip(dates, facs), reverse=True):
            series[: DAY_INDEX[d]] = series[: DAY_INDEX[d]] / f
        step = 0.5 if cur < 50 else 1.0
        series = np.round(series / step) * step
        series[-1] = cur
        price[p] = series
        events.append(list(zip(dates, facs)))
    return price, events


def promotions():
    rows = []
    for p in R.PROMOTIONS:
        rows.append(dict(promotion_id=p["id"], promotion_code=p["code"], promotion_name=p["name"], promotion_type=p["type"],
                         discount_pct=p["pct"], start_date=p["start"], end_date=p["end"], season=p["season"],
                         category_id=LINE_IDS[p["line"]] if p["line"] else None, channel_scope=p["scope"],
                         min_basket_amount=float(p["min_basket"]) if p["min_basket"] else None))
    return rows


def calendar_rows():
    rows = []
    ram = {}
    for y, (a, b) in R.RAMADAN.items():
        d = a
        while d <= b:
            ram[d] = True
            d += timedelta(days=1)
    hol = {}
    for (y, name, a, b) in R.PUBLIC_HOLIDAYS:
        d = a
        while d <= b:
            hol[d] = name
            d += timedelta(days=1)
    for d in DAYS:
        dow = (d.weekday() + 1) % 7          # 0 = Sunday
        wk0 = d - timedelta(days=dow)
        jan1 = date(d.year, 1, 1)
        off = (jan1.weekday() + 1) % 7
        woy = ((d - jan1).days + off) // 7 + 1
        season = R.season_of(d)
        m = d.month
        clim = "Winter" if m in (12, 1, 2) else "Spring" if m in (3, 4, 5) else "Summer" if m in (6, 7, 8, 9) else "Autumn"
        rows.append(dict(date_key=d, year=d.year, quarter=(m - 1) // 3 + 1, month=m, month_name=d.strftime("%B"),
                         week_start_date=wk0, week_of_year=woy, day_of_month=d.day, day_of_week=dow,
                         day_name=d.strftime("%A"), is_weekend=dow in (5, 6), is_holiday=d in hol, holiday_name=hol.get(d),
                         season=season, climate_season=clim, is_ramadan=d in ram,
                         is_eid=season in ("Eid al-Fitr", "Hajj and Eid al-Adha"), is_payday=25 <= d.day <= 28))
    return rows


if __name__ == "__main__":
    rng = np.random.default_rng(1)
    pr = products(rng)
    pt, ev = price_table(rng, pr)
    print(len(branches()), len(categories()), len(suppliers()), len(pr), len(promotions()), len(calendar_rows()))
    print(pt[0, [0, 400, 800, -1]], pt[11, [0, 400, 800, -1]])
