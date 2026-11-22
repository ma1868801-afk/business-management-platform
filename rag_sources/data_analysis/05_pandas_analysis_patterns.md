# Data Analysis: Pandas Analysis Patterns

- Document ID: DA-05
- Index: data_analysis
- Purpose: tested Pandas patterns for calculations that follow a SQL extraction. Each pattern names the SQL pattern that produces its input. Basic result shaping and growth between years are in DA-04.

## Pattern Index

| Question type | SQL input | Pandas pattern |
|---|---|---|
| Year over year growth by month | DA-SQL-10 | DA-PY-04 |
| Digital channel share and change in points | DA-SQL-07 | DA-PY-05 |
| Seasonal index of months | DA-SQL-04 | DA-PY-06 |
| Pareto (ABC) classification of products | DA-SQL-08 without the top ten limit | DA-PY-07 |
| Cohort retention | DA-SQL-24 | DA-PY-08 |
| Target attainment bands | DA-SQL-12 | DA-PY-09 |

## Comparing a Partial Year

The data for 2026 ends on 2026-10-31, so 2026 holds ten months. Never compare the 2026 total with a full 2025 total. Compare January to October of both years, or compare shares and averages. The SQL side does this by adding `AND month <= 10` to the filter, or by choosing explicit date ranges. State the compared period in the answer, for example "January to October 2026 versus January to October 2025".

## Growth, Share and Rank Rules

- Growth percent is `(new / old - 1) * 100`. A zero or missing old value gives NaN, and the answer says growth is undefined.
- Share is the part divided by the total of the same scope. When a filter removes rows (for example `RYD-DC`), the share is of the filtered total, and the answer says so.
- Percentage point change is the difference of two percentages, written "points". Do not call it a percent.
- Ties in a ranking keep the SQL order, which already has a tie-breaker.

### DA-PY-04: Year over year growth by month

Use for "which month grew most compared with last year". The input has one row per calendar month with a column per year, from DA-SQL-10. Months with a zero base give NaN growth.

```python
# fixture: yoy_month
d = df.copy()
for c in ["net_revenue_2024_sar", "net_revenue_2025_sar"]:
    d[c] = pd.to_numeric(d[c])
d["growth_pct"] = ((d["net_revenue_2025_sar"] / d["net_revenue_2024_sar"].replace(0, np.nan) - 1) * 100).round(2)
result = d.sort_values("growth_pct", ascending=False).reset_index(drop=True)
total_growth = (d["net_revenue_2025_sar"].sum() / d["net_revenue_2024_sar"].sum() - 1) * 100
facts = {
    "best_month": int(result.loc[0, "month"]),
    "best_growth_pct": float(result.loc[0, "growth_pct"]),
    "full_year_growth_pct": round(float(total_growth), 2),
}
```

### DA-PY-05: Digital channel share and change in points

Use for online growth questions. Online and Mobile App are combined as digital. The input is DA-SQL-07 (year, channel, revenue, share). The result has the digital share per year and its change from the previous year in percentage points. Compare shares, because 2026 is a partial year.

```python
# fixture: channel_revenue
d = df.copy()
d["net_revenue_sar"] = pd.to_numeric(d["net_revenue_sar"])
d["is_digital"] = d["channel"].isin(["Online", "Mobile App"])
yearly = d.groupby(["year", "is_digital"])["net_revenue_sar"].sum().unstack(fill_value=0)
share = (yearly[True] / (yearly[True] + yearly[False]) * 100).round(2)
result = pd.DataFrame({"digital_share_pct": share, "change_points": share.diff().round(2)}).reset_index()
facts = {"latest_digital_share_pct": float(share.iloc[-1]), "latest_change_points": float(share.diff().iloc[-1])}
```

### DA-PY-06: Seasonal index of calendar months

Use for "which months are strongest". The index of a month is its average revenue divided by the average of all months, so 1.00 is average and 1.30 is 30 percent above average. Use only complete years (2024 and 2025) so that no month is over-represented. The input is DA-SQL-04.

```python
# fixture: monthly_revenue
d = df.copy()
d["order_month"] = pd.to_datetime(d["order_month"])
d["net_revenue_sar"] = pd.to_numeric(d["net_revenue_sar"])
d = d[d["order_month"] < pd.Timestamp("2026-01-01")]
d["calendar_month"] = d["order_month"].dt.month
by_month = d.groupby("calendar_month")["net_revenue_sar"].mean()
result = (by_month / by_month.mean()).round(3).rename("seasonal_index").reset_index()
peak = result.loc[result["seasonal_index"].idxmax()]
facts = {"peak_month": int(peak["calendar_month"]), "peak_index": float(peak["seasonal_index"])}
```

### DA-PY-07: Pareto (ABC) classification of products

Use for "how concentrated is revenue" or "which products make 80 percent of sales". Run DA-SQL-08 without `LIMIT 10` and with `LIMIT 500` so that all SKUs are returned (there are 120). Class A holds the SKUs up to a cumulative 80 percent of revenue, class B up to 95 percent and class C the rest.

```python
# fixture: sku_revenue
d = df.copy()
d["net_revenue_sar"] = pd.to_numeric(d["net_revenue_sar"])
d = d.sort_values("net_revenue_sar", ascending=False).reset_index(drop=True)
d["cum_share_pct"] = d["net_revenue_sar"].cumsum() / d["net_revenue_sar"].sum() * 100
d["abc_class"] = np.where(d["cum_share_pct"] <= 80, "A", np.where(d["cum_share_pct"] <= 95, "B", "C"))
result = d.groupby("abc_class").agg(skus=("sku", "count"), net_revenue_sar=("net_revenue_sar", "sum")).round(2).reset_index()
facts = {"total_skus": int(len(d)), "class_a_skus": int((d["abc_class"] == "A").sum())}
```

### DA-PY-08: Cohort retention table

Use for "how many customers come back". The input is DA-SQL-24: one row per registration cohort month and order month with the cohort size and the number of cohort customers who ordered in that month. Retention is the active customers divided by the cohort size, in percent, for months 0, 1, 3 and 6 after the registration month. Month 0 is the registration month itself, so it is below 100 percent. Cohorts younger than the requested month show no value (empty) for it.

```python
# fixture: cohort
d = df.copy()
d["cohort_month"] = pd.to_datetime(d["cohort_month"])
d["order_month"] = pd.to_datetime(d["order_month"])
d["months_since"] = (d["order_month"].dt.year - d["cohort_month"].dt.year) * 12 + (d["order_month"].dt.month - d["cohort_month"].dt.month)
d["retention_pct"] = d["active_customers"] / d["cohort_size"] * 100
table = d.pivot_table(index="cohort_month", columns="months_since", values="retention_pct", aggfunc="mean").round(1)
keep = [m for m in [0, 1, 3, 6] if m in table.columns]
result = table[keep].copy()
result.columns = ["month_" + str(m) for m in keep]
result["cohort_size"] = d.groupby("cohort_month")["cohort_size"].first()
result = result.reset_index()
result["cohort_month"] = result["cohort_month"].dt.strftime("%Y-%m")
facts = {
    "cohorts": int(len(result)),
    "avg_month_3_retention_pct": round(float(table[3].mean()), 1) if 3 in table.columns else None,
}
```

### DA-PY-09: Target attainment bands

Use for "which locations missed target". The input is DA-SQL-12. Attainment is revenue divided by target. Locations are grouped into bands: below 90 percent, 90 to under 100 percent, and 100 percent or more. A location without revenue in the month has NaN attainment and appears in the band "No data".

```python
# fixture: attainment
d = df.copy()
for c in ["net_revenue_sar", "target_revenue_sar"]:
    d[c] = pd.to_numeric(d[c])
d["attainment_pct"] = (d["net_revenue_sar"] / d["target_revenue_sar"].replace(0, np.nan) * 100).round(2)
bands = pd.cut(d["attainment_pct"], [-np.inf, 90, 100, np.inf], labels=["Below 90%", "90% to under 100%", "100% or more"], right=False)
d["band"] = bands.astype(str).replace("nan", "No data")
result = d[["branch_code", "attainment_pct", "band"]].sort_values("attainment_pct").reset_index(drop=True)
facts = {"locations": int(len(d)), "missed_target": int((d["attainment_pct"] < 100).sum())}
```

## Method Notes for the Answer

- Name the SQL pattern and the Pandas step in `method`, so the user can see how the number was produced.
- Quote only numbers present in `result` or `facts`.
- When a series has fewer than 24 months, do not compute a seasonal index; say that at least two full years are needed.
