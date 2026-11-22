# Data Analysis: SQL Extraction Guidelines

- Document ID: DA-01
- Index: data_analysis
- Purpose: the rules every SQL query written by the Data Analysis subgraph must follow. The SQL tool is strictly read-only (requirement R-05).

## Hard Rules (Validator Enforced)

1. One statement per call, starting with `SELECT` or `WITH`. No `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`, `COPY`, `CALL` or `SET`.
2. Use only the allowed tables and views listed in the schema reference. The `rag` schema is not accessible.
3. Never use `SELECT *`. List the columns you need. On `customers`, `SELECT *` fails because `email` and `phone` are blocked.
4. Never select `customers.email` or `customers.phone`, and never try to work around the block.
5. Add `LIMIT` to every query that returns rows rather than an aggregate: default 100 and maximum 500 for lists shown to the user; up to 50,000 rows when the rows are input for the Pandas tool (the tool call then raises `max_rows`). Prefer aggregating in SQL so far fewer rows are needed.
6. No functions with side effects or system access (`pg_sleep`, `dblink`, `lo_import`, `pg_read_file`). No SQL comments that contain instructions.
7. The query must finish within 8 seconds. Aggregate in SQL instead of pulling raw rows.

## Business Rules for Correct Numbers

- Revenue means net revenue: `SUM(line_total)` from `v_sales_detail` with `status = 'Completed'`. It excludes VAT and is net of line discounts.
- Gross sales before discount is `SUM(quantity * unit_price)`.
- Gross margin is `SUM(line_total - line_cost)`; margin percent is margin divided by net revenue.
- Count orders with `COUNT(DISTINCT order_id)`; the view has one row per order line.
- Average order value is net revenue divided by distinct Completed orders.
- Store rankings exclude branch `RYD-DC`, which carries Online, Mobile App and B2B sales.
- Cancelled, Returned (fully returned) and Processing orders are excluded from revenue unless the user asks about them.
- Returns are measured from `sales_returns` (`refund_amount` excludes VAT) and compared with net revenue of the same scope.

## Dates

- Never use `CURRENT_DATE`, `NOW()` or `CURRENT_TIMESTAMP`. The data ends on 2026-10-31, and relative dates are resolved from that reference date.
- Write dates as `DATE 'YYYY-MM-DD'` literals. Use half-open ranges for months: `>= DATE '2026-10-01' AND < DATE '2026-11-01'`.
- Weeks start on Sunday. Use `calendar.week_start_date` for weekly grouping.
- Timestamps are local Riyadh time; do not convert time zones.
- If the requested period lies entirely after 2026-10-31, do not run a query; report that data ends on 2026-10-31.

## Style

- Name output columns in snake_case with the unit when useful (`net_revenue_sar`, `share_pct`).
- Round money to 2 decimals and percentages to 2 decimals in the final SELECT only.
- Use CTEs for multi-step logic; keep each query readable.
- Order ranked results explicitly (`ORDER BY ... DESC`) and add a tie-breaker when needed.
- Use exact codes for filters (`branch_code = 'RYD-OLY'`) and `ILIKE` only for free-text product names.

## Rejected Patterns

```text
SELECT * FROM customers;
SELECT email, phone FROM customers;
UPDATE sales_orders SET status = 'Completed';
SELECT SUM(line_total) FROM v_sales_detail;            -- missing status filter
SELECT COUNT(*) FROM v_sales_detail;                    -- counts lines, not orders
SELECT ... WHERE order_date >= CURRENT_DATE - 30;       -- system clock not allowed
```

## Examples

### DA-SQL-01: Net revenue for a calendar year

Use when the user asks for total sales or revenue of a full year. Returns one row with the net revenue in SAR.

```sql
SELECT ROUND(SUM(line_total), 2) AS net_revenue_sar
FROM v_sales_detail
WHERE status = 'Completed'
  AND order_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31';
```

### DA-SQL-02: Last month orders, revenue and average order value

Use for "last month", which means October 2026 because the reference date is 2026-10-31. Counts distinct orders and divides revenue by orders.

```sql
SELECT COUNT(DISTINCT order_id) AS orders,
       ROUND(SUM(line_total), 2) AS net_revenue_sar,
       ROUND(SUM(line_total) / COUNT(DISTINCT order_id), 2) AS avg_order_value_sar
FROM v_sales_detail
WHERE status = 'Completed'
  AND order_date >= DATE '2026-10-01' AND order_date < DATE '2026-11-01';
```

### DA-SQL-03: Raw extraction with explicit customer columns

Use when the user asks to list customers. Selects only non-PII columns, orders the rows and applies a limit. This is a raw extraction, so the Pandas tool is bypassed.

```sql
SELECT customer_code, customer_type, city, region, customer_segment, loyalty_tier, registration_date
FROM customers
WHERE customer_type = 'Business'
ORDER BY customer_code
LIMIT 100;
```
