# Inventory: Forecasting Models and Evaluation

- Document ID: INV-05
- Index: inventory
- Purpose: which models the regression tool fits, how it evaluates and chooses between them, how it builds intervals and confidence labels, and how to explain a forecast. The code below is the reference implementation of those steps; the tool runs it, and the language model supplies only the input described in INV-04 and reads the output.

## Models

| Model | What it is | Used when |
|---|---|---|
| Seasonal naive | The forecast for a week is the units of the same week one year earlier (52 weeks back). Without 52 weeks of history, the mean of the last 8 weeks. | Always, as the benchmark that any other model has to beat. |
| Ridge on log1p units | Linear regression with an L2 penalty, fitted to log(1 + units). Features: trend, two yearly harmonics (sine and cosine), promotion flag, Ramadan week, Eid week, White Friday week. | Default for the `full` and `reduced` classes. Handles seasonality and the calendar events with few parameters, and it is easy to explain. |
| Gradient boosting | Small boosted trees (depth 2, 150 trees) on the same features and target. | Candidate for the `full` class when interactions matter, for example event weeks that differ by year. |

Why log1p: demand is non-negative and its noise grows with its level. Modelling log(1 + units) turns multiplicative seasonality into an additive effect, keeps forecasts non-negative after the inverse transform and stabilizes the variance. Forecasts are transformed back with `expm1` and clipped at zero.

Why Ridge: with about 150 weeks of history and 9 features, an unpenalized fit can chase noise. The penalty (alpha 1.0) shrinks the coefficients and keeps the yearly shape smooth.

## Features

| Feature | Definition |
|---|---|
| `trend` | Days since 2024-01-07 divided by 364 (years elapsed). |
| `s1`, `c1`, `s2`, `c2` | Sine and cosine of the day of the year (first and second harmonic). They capture the yearly cycle such as cooling in summer or camping in winter. |
| `promo` | 1 when `promo_units` is above zero in the week. For future weeks, 1 only if the assumption is `promo: planned`. |
| `ramadan`, `eid` | 1 when any day of the week is in Ramadan or in an Eid season (from the `calendar` for history and from the planning event table for future weeks). |
| `white_friday` | 1 when any day of the week is in the White Friday window. |

Hijri events move about 11 days earlier every year, so the yearly harmonics cannot represent Ramadan, Eid or Hajj. The event flags do that. This is why the calendar flags are needed for any SKU with a Ramadan or Eid peak (dates, baskets, gift sets).

## Evaluation

- Holdout: the last 8 complete weeks of history (or the horizon, if shorter). The models are fitted on the earlier weeks and scored on the holdout. The chosen model is then refitted on all weeks.
- WAPE (weighted absolute percentage error): sum of absolute errors divided by the sum of actual units. 0.20 means that forecasts are off by 20 percent of volume on average. WAPE is used instead of MAPE because weekly units can be zero.
- Bias: sum of (forecast minus actual) divided by the sum of actual. Positive means over-forecasting. A bias beyond 0.15 in either direction lowers the confidence label by one level.
- The model with the lowest holdout WAPE is chosen. If the best model is not better than the seasonal naive benchmark, the benchmark is used and the notes say so.

### Confidence Label

| Label | Rule |
|---|---|
| High | History class `full`, holdout WAPE 0.30 or lower |
| Medium | History class `full` with WAPE above 0.30 and up to 0.50 |
| Low | WAPE above 0.50, or any history class other than `full` |

After the rule, a bias beyond 0.15, or more than 25 percent of censored (stockout) weeks in the history, lowers the label by one level (High to Medium, Medium to Low).

### Prediction Interval

The interval (default 80 percent) is built on the log scale from the spread of the model's recent residuals, widened by 25 percent because in-sample residuals understate the error on new weeks, and widened a further 5 percent for each week ahead. It is a range of plausible weekly demand, not a guarantee. Totals over several weeks are the sum of the weekly forecasts; the interval of a total is narrower in relative terms than the weekly intervals, and the tool reports only the weekly intervals.

## Examples

### INV-PY-04: Seasonal naive benchmark and holdout metrics

Use to see how a naive forecast performs on the last 8 weeks. Uses the same week one year earlier when there are at least 60 weeks of history, otherwise the mean of the 8 weeks before the holdout. Returns the holdout table and the WAPE and bias.

```python
# fixture: weekly_history_clean
d = df.copy()
d["week_start_date"] = pd.to_datetime(d["week_start_date"])
d = d.sort_values("week_start_date").reset_index(drop=True)
y = d["units_sold"].to_numpy(dtype=float)
h = 8
n = len(y)
actual = y[-h:]
if n >= h + 52:
    pred = y[n - h - 52 : n - 52]
    baseline = "seasonal_naive"
else:
    pred = np.repeat(y[n - h - 8 : n - h].mean(), h)
    baseline = "recent_mean"
denom = max(float(actual.sum()), 1.0)
result = pd.DataFrame({
    "week_start_date": d["week_start_date"].iloc[-h:].dt.strftime("%Y-%m-%d").to_numpy(),
    "actual_units": actual,
    "baseline_forecast": pred.round(1),
})
facts = {
    "baseline": baseline,
    "holdout_weeks": h,
    "wape": round(float(np.abs(actual - pred).sum() / denom), 3),
    "bias": round(float((pred - actual).sum() / denom), 3),
}
```

### INV-PY-05: Compare models and assign the confidence label

Use to choose between the seasonal naive benchmark, Ridge and gradient boosting on the same holdout. The history is `df` with the calendar flags; the models see only the weeks before the holdout. The result lists the models by WAPE, and the facts carry the chosen model and its label.

```python
# fixture: weekly_history_model
def make_x(f):
    start = pd.to_datetime(f["week_start_date"])
    ang = 2 * math.pi * (start.dt.dayofyear.to_numpy(dtype=float) + 3.0) / 365.25
    return pd.DataFrame({
        "trend": (start - pd.Timestamp("2024-01-07")).dt.days.to_numpy(dtype=float) / 364.0,
        "s1": np.sin(ang),
        "c1": np.cos(ang),
        "s2": np.sin(2 * ang),
        "c2": np.cos(2 * ang),
        "promo": (f["promo_units"].to_numpy(dtype=float) > 0).astype(float),
        "ramadan": f["is_ramadan_week"].to_numpy(dtype=float),
        "eid": f["is_eid_week"].to_numpy(dtype=float),
        "white_friday": f["is_white_friday_week"].to_numpy(dtype=float),
    })

d = df.copy()
d["week_start_date"] = pd.to_datetime(d["week_start_date"])
d = d.sort_values("week_start_date").reset_index(drop=True)
h = 8
n = len(d)
train, test = d.iloc[:-h], d.iloc[-h:]
y_all = d["units_sold"].to_numpy(dtype=float)
actual = y_all[-h:]
log_train = np.log1p(train["units_sold"].to_numpy(dtype=float))
preds = {}
preds["seasonal_naive"] = y_all[n - h - 52 : n - 52] if n >= h + 52 else np.repeat(y_all[n - h - 8 : n - h].mean(), h)
ridge = Ridge(alpha=1.0).fit(make_x(train), log_train)
preds["ridge_log1p"] = np.clip(np.expm1(ridge.predict(make_x(test))), 0, None)
gbr = GradientBoostingRegressor(n_estimators=150, max_depth=2, learning_rate=0.05, random_state=0).fit(make_x(train), log_train)
preds["gradient_boosting"] = np.clip(np.expm1(gbr.predict(make_x(test))), 0, None)
denom = max(float(actual.sum()), 1.0)
rows = [
    {"model": name, "wape": round(float(np.abs(actual - p).sum() / denom), 3), "bias": round(float((p - actual).sum() / denom), 3)}
    for name, p in preds.items()
]
result = pd.DataFrame(rows).sort_values("wape").reset_index(drop=True)
best_wape = float(result.loc[0, "wape"])
levels = ["High", "Medium", "Low"]
idx = 2 if (n < 52 or best_wape > 0.50) else (0 if best_wape <= 0.30 else 1)
if abs(float(result.loc[0, "bias"])) > 0.15:
    idx = min(idx + 1, 2)
facts = {"best_model": str(result.loc[0, "model"]), "best_wape": best_wape, "confidence": levels[idx], "holdout_weeks": h}
```

### INV-PY-06: Ridge forecast with prediction interval

Use to produce the forecast rows. Fits Ridge on all weeks, predicts the future weeks given in `dfs["future"]` (week start and calendar flags, with `promo_units` of 0 unless a promotion is planned) and builds an 80 percent interval that widens with the horizon.

```python
# fixture: weekly_history_model
def make_x(f):
    start = pd.to_datetime(f["week_start_date"])
    ang = 2 * math.pi * (start.dt.dayofyear.to_numpy(dtype=float) + 3.0) / 365.25
    return pd.DataFrame({
        "trend": (start - pd.Timestamp("2024-01-07")).dt.days.to_numpy(dtype=float) / 364.0,
        "s1": np.sin(ang),
        "c1": np.cos(ang),
        "s2": np.sin(2 * ang),
        "c2": np.cos(2 * ang),
        "promo": (f["promo_units"].to_numpy(dtype=float) > 0).astype(float),
        "ramadan": f["is_ramadan_week"].to_numpy(dtype=float),
        "eid": f["is_eid_week"].to_numpy(dtype=float),
        "white_friday": f["is_white_friday_week"].to_numpy(dtype=float),
    })

d = df.copy()
d["week_start_date"] = pd.to_datetime(d["week_start_date"])
future = dfs["future"].copy()
future["week_start_date"] = pd.to_datetime(future["week_start_date"])
log_y = np.log1p(d["units_sold"].to_numpy(dtype=float))
model = Ridge(alpha=1.0).fit(make_x(d), log_y)
sigma = max(float(np.std(log_y[-52:] - model.predict(make_x(d))[-52:])) * 1.25, 0.05)
interval = 0.8
z = float(stats.norm.ppf(0.5 + interval / 2))
mu = model.predict(make_x(future))
width = z * sigma * (1 + 0.05 * np.arange(len(future)))
result = pd.DataFrame({
    "week_start_date": future["week_start_date"].dt.strftime("%Y-%m-%d").to_numpy(),
    "forecast": np.round(np.clip(np.expm1(mu), 0, None)).astype(int),
    "lower": np.round(np.clip(np.expm1(mu - width), 0, None)).astype(int),
    "upper": np.round(np.expm1(mu + width)).astype(int),
})
facts = {
    "model": "ridge_log1p",
    "interval": interval,
    "horizon_weeks": int(len(future)),
    "total_forecast_units": int(result["forecast"].sum()),
    "peak_week": str(result.loc[result["forecast"].idxmax(), "week_start_date"]),
}
```

## Sanity Checks Before Reporting

1. Forecasts are non-negative integers; the lower bound is never above the forecast and the upper bound never below it.
2. No weekly forecast exceeds three times the highest week in the history. If it does, report the model as unreliable and use the benchmark.
3. Compare the total forecast with the same weeks one year earlier. A difference beyond 50 percent needs an explanation (trend, event shift, promotion); otherwise add a warning.
4. For White Friday 2026 (planning estimate 20 to 29 November), say that the event dates are estimates.
5. The forecast is demand, not sales. If the SKU is out of stock or the stock is below the forecast, the sales can be lower than the forecast.

## Explaining a Forecast

- Say "expected demand", not "will sell". Give the horizon, the total, the peak week and the range of the weekly interval.
- Name the main drivers in plain words: the yearly pattern (for example summer peak for cooling products), the event weeks inside the horizon, the recent trend.
- State the model, the confidence label and the holdout WAPE as a percentage ("the model's weekly forecasts were off by about 22 percent on the last 8 weeks").
- State what the model does not know: unplanned promotions, price changes, supply limits and competitor actions.
- For a new SKU or a short history, use the cold-start wording from INV-04 and give a range.
- Never present a forecast of a Discontinued SKU.
