# Data Analysis: SQL Patterns for Sales

- Document ID: DA-03
- Index: data_analysis
- Purpose: tested SQL patterns for the most common sales questions. Adapt the dates and filters; keep the structure. All patterns use `status = 'Completed'` and the reference date 2026-10-31.

## Pattern Index

| Question type | Pattern |
|---|---|
| Revenue trend by month | DA-SQL-04 |
| Revenue, units and share by product line | DA-SQL-05 |
| Store ranking | DA-SQL-06 |
| Channel mix by year | DA-SQL-07 |
| Top products | DA-SQL-08 |
| Gross margin by product line | DA-SQL-09 |
| Year over year by month | DA-SQL-10 |
| Order-level extraction for statistical tests | DA-SQL-11 |
| Target attainment | DA-SQL-12 |
| Return rate by product line | DA-SQL-13 |
| Payment method mix by channel | DA-SQL-14 |
| Promotion versus no promotion | DA-SQL-15 |
| Weekday profile | DA-SQL-16 |
| Hour-of-day profile | DA-SQL-17 |

### DA-SQL-04: Monthly net revenue trend

Use for trend, seasonality over time and growth questions. Returns one row per month from January 2024 to October 2026. The 2026 data stops at 2026-10-31, so the last month is complete.

```sql
SELECT date_trunc('month', order_date)::date AS order_month,
       ROUND(SUM(line_total), 2) AS net_revenue_sar
FROM v_sales_detail
WHERE status = 'Completed'
  AND order_date BETWEEN DATE '2024-01-01' AND DATE '2026-10-31'
GROUP BY 1
ORDER BY 1;
```

### DA-SQL-05: Revenue, units and share by product line

Use for "which product line sells most". Returns revenue, units and the percentage share of the total for one year using a window function.

```sql
SELECT category_name,
       ROUND(SUM(line_total), 2) AS net_revenue_sar,
       SUM(quantity) AS units,
       ROUND(100 * SUM(line_total) / SUM(SUM(line_total)) OVER (), 2) AS share_pct
FROM v_sales_detail
WHERE status = 'Completed'
  AND year = 2025
GROUP BY category_name
ORDER BY net_revenue_sar DESC;
```

### DA-SQL-06: Store ranking by net revenue

Use for "best store" or "rank the stores". Excludes the Distribution Center `RYD-DC` because it carries Online, Mobile App and B2B sales.

```sql
SELECT branch_code,
       branch_name,
       ROUND(SUM(line_total), 2) AS net_revenue_sar,
       RANK() OVER (ORDER BY SUM(line_total) DESC) AS revenue_rank
FROM v_sales_detail
WHERE status = 'Completed'
  AND year = 2025
  AND branch_code <> 'RYD-DC'
GROUP BY branch_code, branch_name
ORDER BY revenue_rank;
```

### DA-SQL-07: Channel mix by year

Use for online growth and channel share questions. Returns revenue and share within each year. The year 2026 covers January to October only, so compare shares, not totals.

```sql
SELECT year,
       channel,
       ROUND(SUM(line_total), 2) AS net_revenue_sar,
       ROUND(100 * SUM(line_total) / SUM(SUM(line_total)) OVER (PARTITION BY year), 2) AS share_pct
FROM v_sales_detail
WHERE status = 'Completed'
  AND order_date BETWEEN DATE '2024-01-01' AND DATE '2026-10-31'
GROUP BY year, channel
ORDER BY year, net_revenue_sar DESC;
```

### DA-SQL-08: Top ten SKUs by revenue

Use for best-selling product questions. Add a tie-breaker on `sku` so the order is deterministic.

```sql
SELECT sku,
       product_name,
       ROUND(SUM(line_total), 2) AS net_revenue_sar,
       SUM(quantity) AS units
FROM v_sales_detail
WHERE status = 'Completed'
  AND year = 2025
GROUP BY sku, product_name
ORDER BY net_revenue_sar DESC, sku
LIMIT 10;
```

### DA-SQL-09: Gross margin by product line

Use for profitability. Margin percent is margin divided by net revenue. `line_margin` is `line_total - line_cost` and already exists in the view.

```sql
SELECT category_name,
       ROUND(SUM(line_total), 2) AS net_revenue_sar,
       ROUND(SUM(line_margin), 2) AS gross_margin_sar,
       ROUND(100 * SUM(line_margin) / NULLIF(SUM(line_total), 0), 2) AS margin_pct
FROM v_sales_detail
WHERE status = 'Completed'
  AND year = 2025
GROUP BY category_name
ORDER BY margin_pct DESC;
```

### DA-SQL-10: Year over year by month

Use to compare the same month across two years. Conditional aggregation with `FILTER` puts each year in its own column; growth is then computed in Pandas.

```sql
SELECT month,
       ROUND(SUM(line_total) FILTER (WHERE year = 2024), 2) AS net_revenue_2024_sar,
       ROUND(SUM(line_total) FILTER (WHERE year = 2025), 2) AS net_revenue_2025_sar
FROM v_sales_detail
WHERE status = 'Completed'
  AND year IN (2024, 2025)
GROUP BY month
ORDER BY month;
```

### DA-SQL-11: Order-level extraction for statistical tests

Use as the input of a hypothesis test on order values. Returns one row per Completed order with the grouping columns that tests use: channel, branch, loyalty tier and whether a promotion was applied. `loyalty_tier` is NULL for anonymous in-store orders, and the text value `None` means a customer who is not a member of any tier. Filter the groups in Pandas, not in SQL, so the same extraction serves several tests. The row limit is raised to 50,000 because the rows feed Pandas; about 45,000 orders fall in 2025, so if exactly 50,000 rows come back the result was truncated and the period must be narrowed.

```sql
SELECT order_id,
       channel,
       branch_code,
       loyalty_tier,
       (promotion_id IS NOT NULL) AS has_promotion,
       ROUND(SUM(line_total), 2) AS order_net_revenue
FROM v_sales_detail
WHERE status = 'Completed'
  AND year = 2025
GROUP BY order_id, channel, branch_code, loyalty_tier, promotion_id
ORDER BY order_id
LIMIT 50000;
```

### DA-SQL-12: Target attainment by location

Use for "which locations missed target". Joins monthly revenue to `monthly_sales_targets`. Attainment is revenue divided by target. Change the month in both places for another month.

```sql
WITH rev AS (
  SELECT branch_id,
         date_trunc('month', order_date)::date AS target_month,
         SUM(line_total) AS net_revenue
  FROM v_sales_detail
  WHERE status = 'Completed'
    AND order_date >= DATE '2026-10-01' AND order_date < DATE '2026-11-01'
  GROUP BY branch_id, date_trunc('month', order_date)::date
)
SELECT b.branch_code,
       t.target_month,
       ROUND(r.net_revenue, 2) AS net_revenue_sar,
       t.target_revenue AS target_revenue_sar,
       ROUND(100 * r.net_revenue / t.target_revenue, 2) AS attainment_pct
FROM monthly_sales_targets t
JOIN branches b ON b.branch_id = t.branch_id
LEFT JOIN rev r ON r.branch_id = t.branch_id AND r.target_month = t.target_month
WHERE t.target_month = DATE '2026-10-01'
ORDER BY attainment_pct
LIMIT 20;
```

### DA-SQL-13: Return rate by product line

Use for return rate questions. Refunds on Completed orders of the year are divided by net revenue of the same orders. Fully returned orders (status Returned) are excluded from both sides, and the answer states that scope.

```sql
WITH sales AS (
  SELECT category_id, SUM(line_total) AS net_revenue
  FROM v_sales_detail
  WHERE status = 'Completed' AND year = 2025
  GROUP BY category_id
), refunds AS (
  SELECT p.category_id, SUM(r.refund_amount) AS refund_amount
  FROM sales_returns r
  JOIN sales_orders o ON o.order_id = r.order_id
  JOIN products p ON p.product_id = r.product_id
  WHERE o.status = 'Completed'
    AND EXTRACT(YEAR FROM o.order_date) = 2025
  GROUP BY p.category_id
)
SELECT pc.category_name,
       ROUND(s.net_revenue, 2) AS net_revenue_sar,
       ROUND(COALESCE(f.refund_amount, 0), 2) AS refund_sar,
       ROUND(100 * COALESCE(f.refund_amount, 0) / s.net_revenue, 2) AS return_rate_pct
FROM sales s
JOIN product_categories pc ON pc.category_id = s.category_id
LEFT JOIN refunds f ON f.category_id = s.category_id
ORDER BY return_rate_pct DESC
LIMIT 20;
```

### DA-SQL-14: Payment method mix by channel

Use for payment questions and as the contingency table for a chi-square test. The header table `sales_orders` has one row per order, so `COUNT(*)` counts orders.

```sql
SELECT channel,
       payment_method,
       COUNT(*) AS orders,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY channel), 2) AS share_pct
FROM sales_orders
WHERE status = 'Completed'
  AND order_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
GROUP BY channel, payment_method
ORDER BY channel, orders DESC;
```

### DA-SQL-15: Orders with a promotion versus without

Use for promotion effect questions. `subtotal_amount` is the order net revenue. Groups the header table by whether a promotion was applied.

```sql
SELECT CASE WHEN promotion_id IS NULL THEN 'No promotion' ELSE 'Promotion' END AS order_group,
       COUNT(*) AS orders,
       ROUND(AVG(subtotal_amount), 2) AS avg_order_value_sar,
       ROUND(SUM(subtotal_amount), 2) AS net_revenue_sar,
       ROUND(AVG(discount_amount), 2) AS avg_discount_sar
FROM sales_orders
WHERE status = 'Completed'
  AND order_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
GROUP BY 1
ORDER BY 1;
```

### DA-SQL-16: Weekday profile of store revenue

Use for weekend and day-of-week questions. First builds daily in-store revenue (all stores together), then averages by weekday using `calendar.day_of_week` (0 Sunday to 6 Saturday).

```sql
WITH daily AS (
  SELECT o.order_date, SUM(i.line_total) AS store_revenue
  FROM sales_orders o
  JOIN sales_order_items i ON i.order_id = o.order_id
  WHERE o.status = 'Completed'
    AND o.channel = 'In-Store'
    AND o.order_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
  GROUP BY o.order_date
)
SELECT c.day_name,
       c.day_of_week,
       COUNT(*) AS days,
       ROUND(AVG(d.store_revenue), 2) AS avg_daily_store_revenue_sar
FROM daily d
JOIN calendar c ON c.date_key = d.order_date
GROUP BY c.day_name, c.day_of_week
ORDER BY c.day_of_week;
```

### DA-SQL-17: Hour-of-day profile by channel

Use for peak hour questions. Counts Completed orders by `order_hour` for in-store and for digital (Online plus Mobile App) orders.

```sql
SELECT order_hour,
       COUNT(*) FILTER (WHERE channel = 'In-Store') AS in_store_orders,
       COUNT(*) FILTER (WHERE channel IN ('Online', 'Mobile App')) AS digital_orders
FROM sales_orders
WHERE status = 'Completed'
  AND order_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
GROUP BY order_hour
ORDER BY order_hour;
```
