# Data Analysis: Pandas Execution Instructions

- Document ID: DA-04
- Index: data_analysis
- Purpose: how the Pandas tool runs code, what the code may use and how to shape the result. Computation is done by code, not by language model reasoning.

## When to Use the Pandas Tool

Use Pandas when the answer needs a calculation after SQL extraction: growth rates, shares of total, rankings, moving averages, seasonal indexes, cohort tables, correlations and hypothesis tests. Bypass Pandas (and say so in `method.bypassed`) when the question only needs a list, a single SQL aggregate or a lookup.

## Sandbox Contract

| Item | Rule |
|---|---|
| Names available | `df` (first SQL result), `dfs` (dictionary of named results), `pd`, `np`, `stats` (scipy.stats), `math` |
| Imports | Not allowed. A static check rejects `import`, `open`, `eval`, `exec`, `__` attributes, network and file access |
| Limits | 50,000 input rows, 5 seconds, 200 output rows |
| Output | Assign the answer to `result` (DataFrame, Series, dict or scalar). Optionally assign `facts`, a dictionary of named numbers used in the answer |

## Coding Rules

- Do not modify `df` in place; create a copy first (`d = df.copy()`).
- Convert SQL numeric columns with `pd.to_numeric` when they may arrive as text.
- Convert date columns with `pd.to_datetime`.
- Round only at the end. Report percentages with two decimals and money with two decimals.
- Guard divisions: replace a zero denominator with NaN and say so in the answer.
- Put every number used in the answer into `result` or `facts`, so the output guard can verify it.
- Never print; the tool returns `result` and `facts` only.

## Error Handling

When the tool returns an error, regenerate the code once or twice using the error message. After two failed retries, return `status = "failed"` with a plain explanation and do not guess numbers.

## Examples

### DA-PY-01: Growth between the last two years

Use when the question asks how much a value grew from one year to the next. The input is the result of a SQL query with one row per year.

```python
# fixture: yearly_revenue
d = df.copy().sort_values("year")
d["net_revenue_sar"] = pd.to_numeric(d["net_revenue_sar"])
d["growth_pct"] = (d["net_revenue_sar"].pct_change() * 100).round(2)
result = d[["year", "net_revenue_sar", "growth_pct"]]
facts = {"latest_growth_pct": float(d["growth_pct"].iloc[-1])}
```

### DA-PY-02: Shaping result and facts

Use as the standard pattern for a ranked table with a total. The table goes to `result`, and the numbers used in the sentence go to `facts`.

```python
# fixture: line_revenue
d = df.copy()
d["net_revenue_sar"] = pd.to_numeric(d["net_revenue_sar"])
total = d["net_revenue_sar"].sum()
d["share_pct"] = (d["net_revenue_sar"] / total * 100).round(2)
result = d.sort_values("net_revenue_sar", ascending=False).reset_index(drop=True)
facts = {"total_net_revenue_sar": round(float(total), 2), "top_line": str(result.loc[0, "category_name"])}
```

### DA-PY-03: Moving average of a monthly series

Use for trend questions. Sort by month, convert the month to a date and add a 3-month moving average.

```python
# fixture: monthly_revenue
d = df.copy()
d["order_month"] = pd.to_datetime(d["order_month"])
d = d.sort_values("order_month").set_index("order_month")
d["ma3_sar"] = d["net_revenue_sar"].rolling(3).mean().round(2)
result = d.reset_index().tail(12)
facts = {"last_month_net_revenue_sar": round(float(d["net_revenue_sar"].iloc[-1]), 2)}
```
