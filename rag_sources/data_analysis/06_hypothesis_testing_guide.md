# Data Analysis: Hypothesis Testing Guide

- Document ID: DA-06
- Index: data_analysis
- Purpose: when and how to run statistical tests, how to extract the data they need and how to report the result. Tests run only when the user asks for significance; the router sets `hypothesis_test=true` in that case.

## When to Run a Test

Run a test only when the question contains an explicit request such as "significant", "statistically", "p-value", "is the difference real", "is there an association", "confidence" or "test whether". For a plain comparison ("which is higher") give the descriptive numbers and offer a test in one sentence; do not run it unasked.

## Choosing the Test

| Question | Test | Input shape | SQL input | Example |
|---|---|---|---|---|
| Is the mean of a numeric value different between two groups (large samples) | Welch t-test | one value per row, group label | DA-SQL-11 | DA-PY-10 |
| Same, but the value is very skewed or groups are small | Mann-Whitney U | same | DA-SQL-11 | DA-PY-11 |
| Does the mean differ across three or more groups | One-way ANOVA with Kruskal-Wallis as a check | same | DA-SQL-11 | DA-PY-12 |
| Are two categorical variables associated (for example payment method and channel) | Chi-square test of independence | counts by two categories | DA-SQL-14 | DA-PY-13 |
| Do two rates (proportions) differ | Two-proportion z-test | successes and trials per group | DA-SQL-18 | DA-PY-14 |
| Do two numeric variables move together | Spearman rank correlation | paired values | DA-SQL-19 | DA-PY-15 |
| Do weekend days differ from weekdays in daily revenue | Welch t-test or Mann-Whitney on daily values | one value per day, flag | DA-SQL-21 | DA-PY-10 pattern |

## Defaults

- Significance level 5 percent (alpha = 0.05), two-sided, unless the user states another level.
- Welch's version of the t-test is always used, because it does not assume equal variances.
- Each group needs at least 30 observations for the t-test and ANOVA; with fewer, use Mann-Whitney or Kruskal-Wallis. With fewer than 5 observations in a group, do not test; report that the sample is too small.
- Chi-square needs expected counts of at least 5 in most cells. If many cells are smaller, merge rare categories before testing.
- Always report an effect size next to the p-value. With tens of thousands of orders, tiny differences become "significant", so the effect size tells whether the difference matters: Cohen's d (0.2 small, 0.5 medium, 0.8 large), rank-biserial correlation, eta squared (0.01 small, 0.06 medium, 0.14 large), Cramer's V (0.1 small, 0.3 medium, 0.5 large) or the Spearman rho (0.1 weak, 0.3 moderate, 0.5 strong).
- Report a p-value below 0.001 as "p < 0.001".
- Do not apply a test to the whole population when the user asks about "all customers" in a descriptive sense; tests describe samples. State that the 2025 orders are treated as a sample of the ongoing process.

## Reporting Template

The answer states, in this order:

1. The null hypothesis in plain words (for example, "average order value is the same for Online and In-Store orders").
2. The test and why it was chosen.
3. The group sizes and group statistics (mean and median).
4. The test statistic and the p-value.
5. The decision at the 5 percent level and the effect size.
6. One caution when relevant: orders from the same customer are not fully independent; a non-significant result does not prove that two groups are equal, it shows no evidence of a difference.

Example wording with placeholders (the numbers always come from `facts`): "Average order value was SAR {mean_a} for Online and Mobile App orders and SAR {mean_b} for In-Store orders in 2025 (Welch t-test, t = {t}, p {p}). The difference of SAR {diff} is statistically significant at the 5 percent level, with a {small, medium or large} effect (Cohen's d = {d})."

## Data Extraction for Tests

- Use DA-SQL-11 for any comparison of order values. It returns one row per Completed order with channel, branch, loyalty tier and the promotion flag, so the same extraction supports comparisons by channel, branch, tier and promotion.
- Filter the groups in Pandas. Customers with loyalty tier `None` are members of no tier; anonymous in-store orders have a NULL tier and are left out of tier comparisons.
- The extraction is limited to 50,000 rows. If exactly 50,000 rows return, the period was cut. Narrow the period or the scope and say so.
- Compare like with like: the same period, the same status (`Completed`) and the same measure (order net revenue, excluding VAT).

### DA-SQL-18: Returned lines and sold lines by product line

Use as the input of a two-proportion z-test of return rates. A line counts as returned when at least one return exists for it, so the rate is the share of sold lines that came back. The subquery removes duplicates when a line has several return records. This rate by lines differs from the return rate by value in DA-SQL-13; state which one is used.

```sql
SELECT pc.category_name,
       COUNT(*) AS lines_sold,
       COUNT(r.order_item_id) AS lines_returned
FROM sales_order_items i
JOIN sales_orders o ON o.order_id = i.order_id
JOIN products p ON p.product_id = i.product_id
JOIN product_categories pc ON pc.category_id = p.category_id
LEFT JOIN (SELECT DISTINCT order_item_id FROM sales_returns) r ON r.order_item_id = i.order_item_id
WHERE o.status = 'Completed'
  AND o.order_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
GROUP BY pc.category_name
ORDER BY pc.category_name;
```

### DA-SQL-19: Sampled order lines with discount and quantity

Use as the input of a correlation between discount percentage and quantity. A deterministic sample (every third line by identifier) keeps the result within the 50,000 row limit and does not depend on chance. The answer states that a one-third sample of the 2025 lines was used.

```sql
SELECT i.order_item_id,
       i.discount_pct,
       i.quantity
FROM sales_order_items i
JOIN sales_orders o ON o.order_id = i.order_id
WHERE o.status = 'Completed'
  AND o.order_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
  AND MOD(i.order_item_id, 3) = 0
ORDER BY i.order_item_id
LIMIT 50000;
```

## Examples

### DA-PY-10: Welch t-test of order values by channel

Use for "is the average order value of online orders significantly higher than in-store orders". Online and Mobile App orders form the digital group. To compare two stores, filter on `branch_code` instead (for example `DMM-FSL` and `KHB-COR`); a non-significant result is reported as no evidence of a difference.

```python
# fixture: order_values
d = df.copy()
d["order_net_revenue"] = pd.to_numeric(d["order_net_revenue"])
a = d.loc[d["channel"].isin(["Online", "Mobile App"]), "order_net_revenue"]
b = d.loc[d["channel"] == "In-Store", "order_net_revenue"]
t = stats.ttest_ind(a, b, equal_var=False)
va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
dof = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
diff = float(a.mean() - b.mean())
margin = float(stats.t.ppf(0.975, dof)) * math.sqrt(va + vb)
pooled_sd = math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
result = pd.DataFrame({
    "group": ["Online and Mobile App", "In-Store"],
    "orders": [len(a), len(b)],
    "mean_order_value_sar": [a.mean(), b.mean()],
    "median_order_value_sar": [a.median(), b.median()],
}).round(2)
facts = {
    "test": "Welch t-test",
    "t_statistic": round(float(t.statistic), 3),
    "p_value": round(float(t.pvalue), 6),
    "mean_difference_sar": round(diff, 2),
    "ci95_low_sar": round(diff - margin, 2),
    "ci95_high_sar": round(diff + margin, 2),
    "difference_pct": round(diff / float(b.mean()) * 100, 2),
    "cohens_d": round(diff / pooled_sd, 3),
}
```

### DA-PY-11: Mann-Whitney test of order values with and without promotion

Use when the values are strongly right-skewed or the question asks for a rank-based comparison. The effect size is the rank-biserial correlation (from -1 to 1), and the common-language statistic is the chance that a randomly chosen promotion order is larger than a randomly chosen order without promotion.

```python
# fixture: order_values
d = df.copy()
d["order_net_revenue"] = pd.to_numeric(d["order_net_revenue"])
flag = d["has_promotion"].astype(bool)
a = d.loc[flag, "order_net_revenue"]
b = d.loc[~flag, "order_net_revenue"]
u = stats.mannwhitneyu(a, b, alternative="two-sided")
cl = float(u.statistic) / (len(a) * len(b))
result = pd.DataFrame({
    "group": ["With promotion", "Without promotion"],
    "orders": [len(a), len(b)],
    "mean_order_value_sar": [a.mean(), b.mean()],
    "median_order_value_sar": [a.median(), b.median()],
}).round(2)
facts = {
    "test": "Mann-Whitney U",
    "u_statistic": round(float(u.statistic), 1),
    "p_value": round(float(u.pvalue), 6),
    "rank_biserial": round(2 * cl - 1, 3),
    "prob_promotion_order_larger_pct": round(cl * 100, 1),
}
```

### DA-PY-12: One-way ANOVA across loyalty tiers

Use for "does order value differ across loyalty tiers". Kruskal-Wallis is run as a check that does not assume normality. Pairwise Welch tests with a Bonferroni correction (the p-value multiplied by the number of pairs, 6 for four tiers) show which tiers differ.

```python
# fixture: order_values
d = df.copy()
d["order_net_revenue"] = pd.to_numeric(d["order_net_revenue"])
tiers = ["None", "Silver", "Gold", "Platinum"]
d = d[d["loyalty_tier"].isin(tiers)]
groups = [d.loc[d["loyalty_tier"] == name, "order_net_revenue"] for name in tiers]
f = stats.f_oneway(*groups)
h = stats.kruskal(*groups)
grand = d["order_net_revenue"].mean()
ss_between = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
ss_total = ((d["order_net_revenue"] - grand) ** 2).sum()
pairwise = {}
for i in range(len(tiers)):
    for j in range(i + 1, len(tiers)):
        p = stats.ttest_ind(groups[i], groups[j], equal_var=False).pvalue
        pairwise[tiers[i] + " vs " + tiers[j]] = round(min(float(p) * 6, 1.0), 6)
result = pd.DataFrame({
    "loyalty_tier": tiers,
    "orders": [len(g) for g in groups],
    "mean_order_value_sar": [g.mean() for g in groups],
    "median_order_value_sar": [g.median() for g in groups],
}).round(2)
facts = {
    "anova_f": round(float(f.statistic), 2),
    "anova_p_value": round(float(f.pvalue), 6),
    "kruskal_h": round(float(h.statistic), 2),
    "kruskal_p_value": round(float(h.pvalue), 6),
    "eta_squared": round(float(ss_between / ss_total), 4),
    "pairwise_p_values_bonferroni": pairwise,
}
```

### DA-PY-13: Chi-square test of payment method and channel

Use for "is payment method related to channel". The input is DA-SQL-14 (order counts by channel and payment method). Cramer's V gives the strength of the association. The share of cells with expected counts below 5 is reported so the reader can judge the validity of the test.

```python
# fixture: payment_channel
d = df.copy()
d["orders"] = pd.to_numeric(d["orders"])
table = d.pivot_table(index="channel", columns="payment_method", values="orders", aggfunc="sum", fill_value=0)
chi2, p_value, dof, expected = stats.chi2_contingency(table.values)
n = float(table.values.sum())
cramers_v = math.sqrt(chi2 / (n * (min(table.shape) - 1)))
result = table.reset_index()
result.columns = [str(c) for c in result.columns]
facts = {
    "test": "Chi-square test of independence",
    "chi2": round(float(chi2), 2),
    "degrees_of_freedom": int(dof),
    "p_value": round(float(p_value), 6),
    "cramers_v": round(float(cramers_v), 3),
    "cells_expected_below_5_pct": round(float((expected < 5).mean() * 100), 1),
}
```

### DA-PY-14: Two-proportion z-test of return rates

Use for "do Fashion and Grocery have different return rates". The input is DA-SQL-18. The proportion is the share of sold lines that were returned. The result includes the difference in points and its 95 percent confidence interval.

```python
# fixture: returns_rates
d = df.copy().set_index("category_name")
x1, n1 = int(d.loc["Fashion and Apparel", "lines_returned"]), int(d.loc["Fashion and Apparel", "lines_sold"])
x2, n2 = int(d.loc["Grocery and Gourmet", "lines_returned"]), int(d.loc["Grocery and Gourmet", "lines_sold"])
p1, p2 = x1 / n1, x2 / n2
pooled = (x1 + x2) / (n1 + n2)
z = (p1 - p2) / math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
p_value = 2 * float(stats.norm.sf(abs(z)))
se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
result = pd.DataFrame({
    "category_name": ["Fashion and Apparel", "Grocery and Gourmet"],
    "lines_sold": [n1, n2],
    "lines_returned": [x1, x2],
    "return_rate_pct": [round(p1 * 100, 2), round(p2 * 100, 2)],
})
facts = {
    "test": "Two-proportion z-test",
    "z_statistic": round(float(z), 3),
    "p_value": round(p_value, 6),
    "difference_points": round((p1 - p2) * 100, 2),
    "ci95_low_points": round((p1 - p2 - 1.96 * se) * 100, 2),
    "ci95_high_points": round((p1 - p2 + 1.96 * se) * 100, 2),
}
```

### DA-PY-15: Spearman correlation of discount and quantity

Use for "does a higher discount go with larger quantities". The input is the sampled lines of DA-SQL-19. Spearman is used because most lines have a zero discount, so the data has many ties and is not normal. A correlation shows association, not cause; the answer says so. The result groups lines into discount bands for readability.

```python
# fixture: discount_lines
d = df.copy()
d["discount_pct"] = pd.to_numeric(d["discount_pct"])
d["quantity"] = pd.to_numeric(d["quantity"])
rho = stats.spearmanr(d["discount_pct"], d["quantity"])
band = pd.cut(d["discount_pct"], [-0.01, 0, 10, 20, 100], labels=["No discount", "Up to 10%", "10% to 20%", "Above 20%"])
result = d.groupby(band, observed=True)["quantity"].agg(lines="count", avg_quantity="mean").round(2).reset_index()
result = result.rename(columns={"discount_pct": "discount_band"})
result["discount_band"] = result["discount_band"].astype(str)
facts = {
    "test": "Spearman rank correlation",
    "rho": round(float(rho.statistic), 3),
    "p_value": round(float(rho.pvalue), 6),
    "lines_used": int(len(d)),
}
```

## Common Mistakes

- Running a test without being asked.
- Reporting only the p-value. Add the group sizes, the means and an effect size.
- Saying "proved" or "confirmed". Use "statistically significant at the 5 percent level" or "no statistically significant difference".
- Comparing a partial year with a full year. Use matching periods.
- Mixing order-level and line-level data. Order values come from DA-SQL-11 (one row per order); quantities and discounts come from order lines.
- Running several tests on the same question and reporting only the significant one. Report every test that was run.
