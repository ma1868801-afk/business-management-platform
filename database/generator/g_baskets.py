"""Basket engine: product weights by day, line sampling, quantities, promotions and line discounts."""
from datetime import date, timedelta
import numpy as np
import registry as R
from g_reference import DAYS, ND, DAY_INDEX, LINE_IDS

CATS = [l[1] for l in R.LINES]                       # ELEC APPL FASH GROC BEAU SPRT KIDS HOME
LINE_PROB_TARGET = dict(ELEC=0.055, APPL=0.040, FASH=0.115, GROC=0.385, BEAU=0.130, SPRT=0.075, KIDS=0.110, HOME=0.090)
LINE_PROB = dict(ELEC=0.0535, APPL=0.0409, FASH=0.1107, GROC=0.4064, BEAU=0.1187, SPRT=0.0741, KIDS=0.1024, HOME=0.0933)   # tuned by tune_lineprob.py
QTY_MU = dict(ELEC=0.08, APPL=0.06, FASH=0.22, GROC=0.70, BEAU=0.22, SPRT=0.10, KIDS=0.35, HOME=0.10)
CH_OFFSET = {  # extra logit for online and app orders by line
    "ELEC": 0.25, "APPL": 0.10, "FASH": 0.15, "GROC": -0.50, "BEAU": 0.20, "SPRT": 0.05, "KIDS": -0.05, "HOME": 0.05}
PROMO_UPTAKE_STORE, PROMO_UPTAKE_LINE = 0.60, 0.78
PROMO_QTY_MULT, PROMO_QTY_ADD = 1.3, 0.50
BIG_SKUS = ["ELEC-0001", "ELEC-0003", "APPL-0002", "APPL-0010"]
DEAD_LAST_SALE = DAY_INDEX[date(2026, 7, 20)]


def _month_factor(months, table):
    return np.array([table.get(m, 1.0) for m in months])


class Model:
    def __init__(self, rng, prods, price, cal):
        self.rng = rng
        self.P = len(prods)
        self.prods = prods
        self.price = price
        self.cat = np.array([CATS.index(p["sku"][:4]) for p in prods])
        self.sku = [p["sku"] for p in prods]
        self.cal = cal
        self.month = np.array([c["month"] for c in cal])
        self.season = np.array([c["season"] for c in cal])
        self.week = (np.arange(ND) + 1) // 7
        self.nweeks = int(self.week.max()) + 1
        self.pop = self._popularity(rng)
        self.log_base = self._log_base(rng)

    # --------------------------------------------------------------- popularity and availability
    def _popularity(self, rng):
        pop = np.exp(rng.normal(0, 0.45, self.P)) * (np.array([p["unit_price"] for p in self.prods]) / 300.0) ** -0.28
        for i, p in enumerate(self.prods):
            if p["lifecycle_status"] == "Declining":
                pop[i] *= 0.55
            if p["sku"] in ("ELEC-0012", "SPRT-0013", "BEAU-0014", "KIDS-0014", "GROC-0014", "APPL-0014"):
                pop[i] *= 1.0
        return pop

    def _avail(self):
        a = np.ones((self.P, ND))
        for i, p in enumerate(self.prods):
            li = max(DAY_INDEX.get(p["launch_date"], 0), 0) if p["launch_date"] >= DAYS[0] else 0
            if li > 0:
                ramp = np.clip((np.arange(ND) - li) / 42.0, 0, 1) * 0.6 + 0.4
                a[i] = np.where(np.arange(ND) >= li, ramp, 0.0)
            if p["discontinued_date"]:
                di = DAY_INDEX[p["discontinued_date"]]
                a[i, di + 1:] = 0.0
                a[i, max(di - 90, 0):di + 1] *= 0.6
            if p["sku"] in R.DEAD_DECLINING:
                a[i, DEAD_LAST_SALE + 1:] = 0.0
                a[i, DEAD_LAST_SALE - 120:DEAD_LAST_SALE + 1] *= 0.5
        return a

    # --------------------------------------------------------------- seasonality
    def _seasonal(self):
        m, s = self.month, self.season
        sm = np.ones((self.P, ND))
        dayidx = np.arange(ND)
        pre_ram = np.zeros(ND, bool)
        for y, (a, b) in R.RAMADAN.items():
            pre_ram[DAY_INDEX[a] - 28:DAY_INDEX[a]] = True
        bts = s == "Back to School"
        win = {
            "ram": s == "Ramadan", "eid": s == "Eid al-Fitr", "hajj": s == "Hajj and Eid al-Adha", "wf": s == "White Friday",
            "nd": s == "National Day", "bts": bts, "ram_all": np.array([c["is_ramadan"] for c in self.cal]),
        }
        cool = _month_factor(m, {6: 4.0, 7: 4.0, 8: 4.0, 5: 2.0, 9: 2.0, 3: 1.0, 4: 1.2, 10: 1.0, 11: 0.4, 12: 0.35, 1: 0.35, 2: 0.35})
        camp = _month_factor(m, {11: 3.2, 12: 3.2, 1: 3.2, 2: 3.2, 3: 1.2, 10: 1.4, 4: 0.4, 5: 0.35, 6: 0.3, 7: 0.3, 8: 0.3, 9: 0.35})
        heat = _month_factor(m, {12: 3.0, 1: 3.0, 2: 3.0, 11: 1.6, 3: 1.0})
        school = np.where(bts, 5.0, np.where((m == 9) & ~bts, 1.5, 0.7))
        winter_fashion = _month_factor(m, {11: 2.2, 12: 2.2, 1: 2.2, 2: 2.2})
        for i, p in enumerate(self.prods):
            c, sku = CATS[self.cat[i]], p["sku"]
            f = np.ones(ND)
            if c == "ELEC":
                f *= np.where(win["wf"], 2.3, 1.0)
            elif c == "APPL":
                f *= np.where(win["wf"], 1.5, 1.0)
            elif c == "FASH":
                f *= np.where(win["eid"], 1.7, 1.0) * np.where(win["wf"], 1.4, 1.0)
            elif c == "GROC":
                f *= np.where(win["ram_all"], 1.9, 1.0) * np.where(win["wf"], 0.8, 1.0)
            elif c == "BEAU":
                f *= np.where(win["eid"], 2.1, np.where(win["nd"], 1.6, 1.0))
            elif c == "HOME":
                f *= np.where(pre_ram | win["wf"], 1.9, 1.0)
            if sku in ("APPL-0001", "APPL-0002", "APPL-0003", "APPL-0004", "APPL-0005", "APPL-0006"):
                f *= cool
            if sku == "APPL-0014":
                f *= heat
            if sku in ("SPRT-0001", "SPRT-0002", "SPRT-0003", "SPRT-0004"):
                f *= camp
            if sku in ("KIDS-0001", "KIDS-0002", "KIDS-0003", "KIDS-0004", "KIDS-0005", "KIDS-0014"):
                f *= school
            if sku in ("FASH-0002", "FASH-0007"):
                f *= winter_fashion
            if sku in ("FASH-0001", "FASH-0003", "GROC-0010", "BEAU-0001", "BEAU-0002"):
                f *= np.where(win["eid"], 2.2, 1.0)
            if sku == "BEAU-0003":
                f *= np.where(win["nd"], 3.0, 1.0)
            if sku in ("GROC-0001", "GROC-0002", "GROC-0003", "GROC-0012", "GROC-0014", "HOME-0001", "HOME-0002"):
                f *= np.where(win["ram_all"], 3.0, np.where(pre_ram, 1.6, 0.45))
            sm[i] = f
        return sm

    def _log_base(self, rng):
        av = self._avail()
        sm = self._seasonal()
        live = (av > 0).astype(float)
        sm = sm / np.maximum((sm * live).sum(axis=1) / np.maximum(live.sum(axis=1), 1), 1e-9)[:, None]   # annual mean 1
        wk = rng.normal(0, 0.22, (self.P, self.nweeks))
        noise = np.exp(wk[:, self.week])
        w = self.pop[:, None] * av * sm * noise
        # normalise popularity within each line so that LINE_PROB holds on a day without seasonal effects
        lb = np.full((self.P, ND), -np.inf)
        for k, c in enumerate(CATS):
            idx = np.where(self.cat == k)[0]
            ref = (self.pop[idx][:, None] * np.where(av[idx] > 0, 1.0, 0.0)).sum(axis=0)       # available popularity
            ref = np.maximum(ref, 1e-9)
            lb[idx] = np.log(LINE_PROB[c]) + np.log(np.maximum(w[idx], 1e-30)) - np.log(ref)[None, :]
            lb[idx] = np.where(w[idx] > 0, lb[idx], -np.inf)
        return lb

    # --------------------------------------------------------------- sampling
    def sample_products(self, rng, day, online, aff_rows, kappa, price_cap=None, exclude=None, chunk=20000):
        n = len(day)
        out = np.empty(n, dtype=np.int32)
        lp = np.log(self.price + 1e-9)
        co = np.array([CH_OFFSET[CATS[k]] for k in range(8)])
        for s in range(0, n, chunk):
            e = min(n, s + chunk)
            d = day[s:e]
            z = self.log_base[:, d].T.copy()                                        # (m, P)
            z += (online[s:e, None] * co[self.cat][None, :])
            if aff_rows is not None:
                z += aff_rows[s:e][:, self.cat]
            z += kappa[s:e, None] * (lp[:, d].T - np.log(300.0))
            if price_cap is not None:
                z = np.where(self.price[:, d].T > price_cap[s:e, None], -np.inf, z)
            if exclude is not None:
                z[:, exclude] = -np.inf
            g = -np.log(-np.log(rng.random(z.shape)))
            out[s:e] = np.argmax(z + g, axis=1)
        return out
