# Inventory: Regression Input Guidelines

- Document ID: INV-04
- Index: inventory
- Purpose: how to decide whether a forecast is possible, how to extract and prepare weekly history, and how to build the input of the regression tool. The regression model runs only when the user asks for a forecast, a projection or a replenishment recommendation that depends on future demand. It never runs for current quantities, status lists, supplier facts or historical sales.

## When the Regression Model Runs

| Question | Model runs? |
|---|---|
| "How many units of ELEC-0001 are in stock?" | No. Current quantity (SQL only). |
| "Which SKUs are out of stock?" | No. Status list. |
| "How many units did we sell last quarter?" | No. Historical sales (Data Analysis). |
| "Forecast demand for AirWhirl Tower Fan for 8 weeks." | Yes. |
| "How many units of Qassim Gold Khalas Dates should we order for the next Ramadan?" | Yes. Ordering depends on future demand; the horizon is clamped to 13 weeks, and the answer explains when Ramadan 2027 falls compared with the horizon. |
| "When will GROC-0001 run out?" | Yes if the answer must reflect future demand; otherwise the weeks of cover from INV-SQL-06 is enough. |

## Horizon and Calendar

- The history ends on Saturday 2026-10-31. The last complete week starts on Sunday 2026-10-25.
- The first forecast week starts on Sunday 2026-11-01. Weeks start on Sunday and end on Saturday.
- The horizon is 1 to 13 weeks. If the user gives no horizon, use 8 weeks. A month is 4 weeks and a quarter is 13 weeks. A longer horizon is clamped to 13 weeks and the answer says so.
- The first data week begins on Sunday 2024-01-07, because the week containing 2024-01-01 is incomplete.
- Calendar flags (Ramadan week, Eid week, White Friday week) are derived by the tool from the week start date: from the `calendar` table for history, and from the planning event table for future weeks. Only White Friday 2026 (20 to 29 November, a planning estimate) falls inside a 13-week horizon from 2026-11-01.

## Series Level

| Level | Use when | Entity |
|---|---|---|
| `sku_total` | Default for a SKU question without a location. | `{"sku": "APPL-0004"}` |
| `sku_location` | The user names a location and the series has enough history (see below). | `{"sku": "APPL-0004", "branch_code": "RYD-OLY"}` |
| `line_total` | The question is about a product line. | `{"category_name": "Beauty and Fragrance"}` |
| `location_total` | The question is about the total demand of one location. | `{"branch_code": "RYD-OLY"}` |

If a location-level series fails the minimum history rules, forecast at `sku_total` and split the result by the location's share of units over the last 13 weeks. Say that the split is an allocation.

## Minimum History Rules

Weeks are counted from the first week with a sale to the last complete week. Missing weeks before the first sale are not history.

| History class | Rule | Model used | Confidence label |
|---|---|---|---|
| `full` | 52 weeks or more and fewer than 40 percent zero weeks | Candidates: seasonal naive, Ridge on log1p units, gradient boosting; best holdout WAPE wins | High, Medium or Low from the holdout error (INV-05) |
| `reduced` | 26 to 51 weeks, or 52 weeks or more with 40 percent or more zero weeks | Recent mean baseline and Ridge without yearly seasonality | Medium at best, usually Low |
| `cold_start` | 8 to 25 weeks | Mean of the last 8 weeks, adjusted by the product line seasonal index when available | Low |
| `insufficient` | 1 to 7 weeks | Mean of the weeks available; no intervals beyond a wide range | Low |
| `no_sales` | No sale at all | No forecast. The answer says that no sales history exists. | Not applicable |

New SKUs (launched in 2026) usually fall in `cold_start` or `reduced`. Discontinued SKUs are not forecast; the answer says the SKU is discontinued and shows its remaining stock.

## Data Preparation Steps

1. Extract the weekly series with the calendar so that every week is present (INV-SQL-14 for a SKU, INV-SQL-16 for a line).
2. Fill any missing week with zero units and trim the weeks before the first sale (INV-PY-01).
3. Extract the stockout days for the same series (INV-SQL-15) and adjust the censored weeks (INV-PY-02).
4. Build the tool input (INV-PY-03) and call the regression tool.
5. Read the result, the holdout metrics and the notes, and write the node response. Carry the notes into `warnings`.

### Stockout Adjustment Rule

Sales in a week with stockout days understate demand, because customers could not buy. For each week, the stockout fraction is the weighted stockout days divided by 7. The weights are the location shares of the SKU's units over the last 52 weeks, so a stockout at a small location moves an all-locations series only a little.

| Stockout fraction | Treatment |
|---|---|
| 0 | No change. |
| Above 0 and up to 0.4 | Scale up: units divided by (1 minus the fraction). |
| Above 0.4 | The week is censored. Replace its value with the median of the non-censored weeks within four weeks on each side. |

The notes of the tool state how many weeks were adjusted. If more than 25 percent of the weeks are censored, lower the confidence label by one level.

### Promotion and Price

- `promo_units` counts units sold on orders that carried a promotion. The model uses a promotion flag (units above zero).
- The default assumption for future weeks is `promo: none` and `price: current`. If the user asks "with a promotion", set `promo: planned`; the model then sets the flag in the future weeks and the answer shows both forecasts if possible.
- Do not forecast prices. Price changes are at most two small changes in the period.

## Inputs the Tool Accepts

```json
{
  "history": [{"week_start_date": "2025-01-05", "units_sold": 41, "promo_units": 0, "stockout_days": 0}],
  "series_level": "sku_total",
  "entity": {"sku": "APPL-0004"},
  "horizon_weeks": 8,
  "interval": 0.8,
  "assumptions": {"promo": "none", "price": "current"},
  "with_reorder_advice": true
}
```

| Field | Rule |
|---|---|
| `history` | Weekly rows in date order, no gaps, ending 2026-10-25. `units_sold` is the stockout-adjusted value. |
| `series_level`, `entity` | As in the table above. |
| `horizon_weeks` | 1 to 13. |
| `interval` | Width of the prediction interval, 0.8 by default. |
| `assumptions` | `promo` is `none` or `planned`; `price` is `current`. |
| `with_reorder_advice` | True when the user asks what or how much to order. The advice follows INV-09. |

The tool returns forecast rows (`week_start_date`, `forecast`, `lower`, `upper`), the model name, holdout metrics (WAPE and bias), a confidence label, notes and optional reorder advice.

## Examples

### INV-SQL-14: Weekly demand history of one SKU

Use as the first step of a SKU forecast. Starts from the calendar weeks so that every week from 2024-01-07 to 2026-10-25 appears, with zero units where nothing was sold. Units are summed over all locations.

```sql
WITH weeks AS (
  SELECT DISTINCT week_start_date
  FROM calendar
  WHERE week_start_date BETWEEN DATE '2024-01-07' AND DATE '2026-10-25'
), demand AS (
  SELECT week_start_date,
         SUM(units_sold) AS units_sold,
         SUM(promo_units) AS promo_units
  FROM v_weekly_product_demand
  WHERE sku = 'APPL-0004'
  GROUP BY week_start_date
)
SELECT w.week_start_date,
       COALESCE(d.units_sold, 0) AS units_sold,
       COALESCE(d.promo_units, 0) AS promo_units
FROM weeks w
LEFT JOIN demand d ON d.week_start_date = w.week_start_date
ORDER BY w.week_start_date
LIMIT 500;
```

### INV-SQL-15: Weighted weekly stockout days of one SKU

Use with INV-SQL-14 to detect weeks where sales were limited by stock. Weights each location's stockout days by its share of the SKU's units over the last 52 weeks (from 2025-11-02), so the result describes the all-locations series. The snapshot is taken on Saturday; subtract 6 days to get the week start.

```sql
WITH share AS (
  SELECT branch_id,
         SUM(units_sold)::numeric / SUM(SUM(units_sold)) OVER () AS weight
  FROM v_weekly_product_demand
  WHERE sku = 'APPL-0004'
    AND week_start_date >= DATE '2025-11-02'
  GROUP BY branch_id
)
SELECT sn.snapshot_date,
       ROUND(SUM(sn.stockout_days * sh.weight), 2) AS weighted_stockout_days
FROM inventory_snapshots sn
JOIN share sh ON sh.branch_id = sn.branch_id
JOIN products p ON p.product_id = sn.product_id
WHERE p.sku = 'APPL-0004'
GROUP BY sn.snapshot_date
ORDER BY sn.snapshot_date;
```

### INV-SQL-16: Weekly demand history of a product line

Use for a line-level forecast. Sums units over all SKUs of the line and all locations for each calendar week. Lines have a long history, so the line series is always in the `full` class.

```sql
WITH weeks AS (
  SELECT DISTINCT week_start_date
  FROM calendar
  WHERE week_start_date BETWEEN DATE '2024-01-07' AND DATE '2026-10-25'
), demand AS (
  SELECT d.week_start_date,
         SUM(d.units_sold) AS units_sold,
         SUM(d.promo_units) AS promo_units
  FROM v_weekly_product_demand d
  JOIN product_categories pc ON pc.category_id = d.category_id
  WHERE pc.category_name = 'Beauty and Fragrance'
  GROUP BY d.week_start_date
)
SELECT w.week_start_date,
       COALESCE(d.units_sold, 0) AS units_sold,
       COALESCE(d.promo_units, 0) AS promo_units
FROM weeks w
LEFT JOIN demand d ON d.week_start_date = w.week_start_date
ORDER BY w.week_start_date
LIMIT 500;
```

### INV-SQL-17: Forecastability screen for all SKUs

Use for "which SKUs can be forecast reliably". For each SKU, returns the first week with a sale, the weeks since then, the share of zero-sales weeks and the total units. Newest SKUs come first. A SKU with 52 or more weeks and under 40 percent zero weeks is in the `full` class.

```sql
WITH weekly AS (
  SELECT sku,
         week_start_date,
         SUM(units_sold) AS units
  FROM v_weekly_product_demand
  WHERE week_start_date BETWEEN DATE '2024-01-07' AND DATE '2026-10-25'
  GROUP BY sku, week_start_date
), span AS (
  SELECT sku,
         MIN(week_start_date) AS first_sale_week,
         COUNT(*) AS weeks_with_sales,
         SUM(units) AS total_units
  FROM weekly
  GROUP BY sku
)
SELECT sku,
       first_sale_week,
       ((DATE '2026-10-25' - first_sale_week) / 7 + 1) AS weeks_since_first_sale,
       weeks_with_sales,
       ROUND(100.0 * (1 - weeks_with_sales::numeric / ((DATE '2026-10-25' - first_sale_week) / 7 + 1)), 1) AS zero_week_pct,
       total_units
FROM span
ORDER BY weeks_since_first_sale, sku
LIMIT 200;
```

### INV-PY-01: Prepare the weekly history

Use right after INV-SQL-14 or INV-SQL-16. Fills missing weeks with zero, trims the weeks before the first sale, counts the weeks and zero weeks, and assigns the history class. The cleaned history goes to `result` so that the next step can use it as `df`.

```python
# fixture: weekly_history
d = df.copy()
d["week_start_date"] = pd.to_datetime(d["week_start_date"])
for c in ["units_sold", "promo_units"]:
    d[c] = pd.to_numeric(d[c])
d = d.sort_values("week_start_date").set_index("week_start_date")
d = d.reindex(pd.date_range(d.index.min(), d.index.max(), freq="7D")).fillna(0)
sales_weeks = d.index[d["units_sold"] > 0]
d = d.loc[sales_weeks.min():] if len(sales_weeks) else d.iloc[0:0]
weeks = int(len(d))
zero_pct = round(float((d["units_sold"] == 0).mean() * 100), 1) if weeks else 100.0
if weeks == 0:
    history_class = "no_sales"
elif weeks >= 52 and zero_pct < 40:
    history_class = "full"
elif weeks >= 26:
    history_class = "reduced"
elif weeks >= 8:
    history_class = "cold_start"
else:
    history_class = "insufficient"
result = d.reset_index().rename(columns={"index": "week_start_date"})
result["week_start_date"] = result["week_start_date"].dt.strftime("%Y-%m-%d")
facts = {"weeks_of_history": weeks, "zero_week_pct": zero_pct, "history_class": history_class}
```

### INV-PY-02: Adjust weeks limited by stockouts

Use after INV-PY-01 and INV-SQL-15. The history is `df` and the stockout table is `dfs["stockout"]`. Applies the stockout adjustment rule: weeks with a stockout fraction up to 0.4 are scaled up, and weeks above 0.4 are replaced by the local median of the non-censored weeks. The adjusted history goes to `result`.

```python
# fixture: history_with_stockout
d = df.copy()
d["week_start_date"] = pd.to_datetime(d["week_start_date"])
s = dfs["stockout"].copy()
s["week_start_date"] = pd.to_datetime(s["snapshot_date"]) - pd.Timedelta(days=6)
s["weighted_stockout_days"] = pd.to_numeric(s["weighted_stockout_days"])
d = d.merge(s[["week_start_date", "weighted_stockout_days"]], on="week_start_date", how="left")
d["weighted_stockout_days"] = d["weighted_stockout_days"].fillna(0.0)
frac = d["weighted_stockout_days"] / 7
clean = d["units_sold"].where(frac <= 0.4)
local = clean.rolling(9, center=True, min_periods=2).median().fillna(clean.median())
d["units_adjusted"] = np.where(frac == 0, d["units_sold"], np.where(frac <= 0.4, d["units_sold"] / (1 - frac), local)).round(1)
d["adjustment"] = np.where(frac == 0, "none", np.where(frac <= 0.4, "scaled", "imputed"))
result = d[["week_start_date", "units_sold", "promo_units", "weighted_stockout_days", "units_adjusted", "adjustment"]].copy()
result["week_start_date"] = result["week_start_date"].dt.strftime("%Y-%m-%d")
facts = {
    "weeks_scaled": int((d["adjustment"] == "scaled").sum()),
    "weeks_imputed": int((d["adjustment"] == "imputed").sum()),
    "censored_share_pct": round(float((frac > 0.4).mean() * 100), 1),
}
```

### INV-PY-03: Build the regression tool input

Use as the last preparation step. Converts the adjusted history into the tool input structure. The adjusted units replace the raw units. The entity, level, horizon and assumptions come from the routing hints and the question.

```python
# fixture: history_adjusted
d = df.copy()
history = [
    {
        "week_start_date": str(r.week_start_date),
        "units_sold": float(r.units_adjusted),
        "promo_units": float(r.promo_units),
        "stockout_days": float(r.weighted_stockout_days),
    }
    for r in d.itertuples()
]
result = {
    "history": history,
    "series_level": "sku_total",
    "entity": {"sku": "APPL-0004"},
    "horizon_weeks": 8,
    "interval": 0.8,
    "assumptions": {"promo": "none", "price": "current"},
    "with_reorder_advice": True,
}
facts = {"history_weeks": len(history), "last_week_start": history[-1]["week_start_date"], "horizon_weeks": 8}
```

## Refusals and Cold Starts

- No sales history: do not forecast; say that the SKU has no sales (for example a SKU not yet launched).
- Cold start: say "this estimate is based on fewer than 26 weeks of sales and has low confidence". Give a range, not a single number.
- A request longer than 13 weeks: forecast 13 weeks and say the horizon was limited.
- A request for a date before 2026-11-01: that is history; answer from the sales data.
