# Data Analysis: Customer Analytics Knowledge

- Document ID: DA-09
- Index: data_analysis
- Purpose: how customers are described in the data, what may and may not be returned about them, and tested SQL patterns for cohorts, tiers, repeat purchase, registrations and business accounts.

## Customer Types

| Type | Code style | Description |
|---|---|---|
| Individual | `CUST-000001` | Retail consumers who buy in stores, online or through the app. They may belong to the Nakhla Rewards loyalty programme. |
| Business | `CUST-B001` to `CUST-B012` | Twelve contract business accounts that buy through the B2B channel, with a contract number, credit limit, payment terms and a contract discount. Business customers have loyalty tier `None`. |

Anonymous in-store transactions (about 8 percent of in-store orders) have no customer: `customer_id` is NULL. They count in revenue but not in any customer measure.

A note on naming: the database stores Business accounts as customer type `Business`, while contract and policy documents call them corporate or business customers. They are the same accounts.

## Customer Columns Available

`customer_id`, `customer_code`, `customer_type`, `full_name`, `gender`, `age_group`, `city`, `region`, `customer_segment`, `loyalty_tier`, `loyalty_points`, `registration_date`, `acquisition_channel`, `preferred_branch_id`, `marketing_opt_in`, `contract_number`, `credit_limit`, `payment_terms_days`, `is_active`.

Not available: `email` and `phone` (blocked by column-level grants).

| Column | Values |
|---|---|
| `customer_segment` | Premium, Core, Occasional (a marketing value segment assigned at registration review; it is not computed from spend) |
| `loyalty_tier` | None, Silver, Gold, Platinum |
| `age_group` | 18-24, 25-34, 35-44, 45-54, 55+ (NULL for businesses) |
| `gender` | Male, Female (NULL for businesses) |
| `acquisition_channel` | Walk-in, Website, Mobile App, Social Media, Referral, B2B Sales |

## Loyalty Programme (Nakhla Rewards)

Tiers follow trailing 12-month net spend as of the reference date: Silver from SAR 3,000, Gold from SAR 10,000 and Platinum from SAR 25,000; below SAR 3,000 the tier is `None`. About 45 percent of individuals are `None`, 30 percent Silver, 18 percent Gold and 7 percent Platinum. Average order value rises with the tier: Platinum above Gold above Silver above None. Delivery fees are waived for Gold and Platinum members. Programme rules (points earning, redemption, tier benefits) are policy documents in the Knowledge Base; measured tier counts and spend are answered here.

## Privacy Rules for Customer Questions

- Never select or return `email` or `phone`. The database blocks them, and the router rejects such requests.
- Do not return `full_name` of Individual customers. Identify individuals by `customer_code`. The `full_name` of a Business customer is a company name and may be returned.
- List queries return at most 100 rows and only the columns the question needs. Prefer aggregates (counts, shares, averages) to lists of people.
- A request for a ranked list of named individual spenders is answered with customer codes, tier and spend, not names.
- Do not combine columns to identify a single person (city, age group, gender, registration date and spend together for a narrow filter). If a filter returns fewer than 5 customers, report the count only.

## Reading Customer Measures

- Active customers need at least one Completed order in the period and exclude anonymous orders.
- Repeat purchase rate is measured over a stated period; the all-history rate is higher than the one-year rate.
- Retention is measured by cohort (the month of registration). A cohort younger than the requested month has no value for it.
- Tier is a current snapshot as of 2026-10-31. Do not describe the tier a customer had in 2024 or 2025; say that history of tier changes is not stored.
- Spend by tier uses the customer's current tier, which can differ from the tier at the time of the order. Say so when comparing tiers over a past period.

## SQL Patterns

### DA-SQL-24: Cohort activity for 2025 registrations

Use as the input of the cohort retention table (DA-PY-08). Cohorts are individual customers by registration month. For each cohort and order month, returns the cohort size and the number of cohort customers with a Completed order that month.

```sql
WITH cohort AS (
  SELECT customer_id,
         date_trunc('month', registration_date)::date AS cohort_month
  FROM customers
  WHERE customer_type = 'Individual'
    AND registration_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
), sizes AS (
  SELECT cohort_month, COUNT(*) AS cohort_size
  FROM cohort
  GROUP BY cohort_month
), activity AS (
  SELECT c.cohort_month,
         date_trunc('month', o.order_date)::date AS order_month,
         COUNT(DISTINCT o.customer_id) AS active_customers
  FROM cohort c
  JOIN sales_orders o ON o.customer_id = c.customer_id
  WHERE o.status = 'Completed'
    AND o.order_date >= c.cohort_month
  GROUP BY c.cohort_month, date_trunc('month', o.order_date)::date
)
SELECT a.cohort_month,
       a.order_month,
       s.cohort_size,
       a.active_customers
FROM activity a
JOIN sizes s ON s.cohort_month = a.cohort_month
ORDER BY a.cohort_month, a.order_month
LIMIT 500;
```

### DA-SQL-25: Loyalty tier distribution

Use for "how many customers are in each tier". Counts individual customers per tier with the share and the average points balance. The `CASE` puts the tiers in programme order.

```sql
SELECT loyalty_tier,
       COUNT(*) AS customers,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct,
       ROUND(AVG(loyalty_points), 0) AS avg_points
FROM customers
WHERE customer_type = 'Individual'
GROUP BY loyalty_tier
ORDER BY CASE loyalty_tier WHEN 'None' THEN 0 WHEN 'Silver' THEN 1 WHEN 'Gold' THEN 2 ELSE 3 END;
```

### DA-SQL-26: Repeat purchase rate for one year

Use for "what share of customers buy more than once". Counts individual customers with at least one Completed order in 2025 and those with two or more. Change the date range for another period and name it in the answer.

```sql
WITH per_customer AS (
  SELECT o.customer_id,
         COUNT(*) AS orders
  FROM sales_orders o
  JOIN customers c ON c.customer_id = o.customer_id
  WHERE o.status = 'Completed'
    AND c.customer_type = 'Individual'
    AND o.order_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
  GROUP BY o.customer_id
)
SELECT COUNT(*) AS active_customers,
       COUNT(*) FILTER (WHERE orders >= 2) AS repeat_customers,
       ROUND(100.0 * COUNT(*) FILTER (WHERE orders >= 2) / NULLIF(COUNT(*), 0), 2) AS repeat_rate_pct
FROM per_customer;
```

### DA-SQL-27: New registrations by month and acquisition channel

Use for customer growth and acquisition questions. Returns monthly new individual customers by acquisition channel from January 2025 to October 2026.

```sql
SELECT date_trunc('month', registration_date)::date AS registration_month,
       acquisition_channel,
       COUNT(*) AS new_customers
FROM customers
WHERE customer_type = 'Individual'
  AND registration_date BETWEEN DATE '2025-01-01' AND DATE '2026-10-31'
GROUP BY date_trunc('month', registration_date)::date, acquisition_channel
ORDER BY registration_month, acquisition_channel;
```

### DA-SQL-28: Top business accounts by net revenue

Use for B2B questions. Returns the ten business customers with the highest 2025 net revenue, with their payment terms and credit limit. `full_name` is a company name here, which is allowed; the same query for individuals must use `customer_code` only.

```sql
SELECT c.customer_code,
       c.full_name AS company_name,
       c.payment_terms_days,
       c.credit_limit,
       COUNT(DISTINCT v.order_id) AS orders,
       ROUND(SUM(v.line_total), 2) AS net_revenue_sar
FROM v_sales_detail v
JOIN customers c ON c.customer_id = v.customer_id
WHERE v.status = 'Completed'
  AND c.customer_type = 'Business'
  AND v.year = 2025
GROUP BY c.customer_code, c.full_name, c.payment_terms_days, c.credit_limit
ORDER BY net_revenue_sar DESC, c.customer_code
LIMIT 10;
```

## Where Customer Questions Go

| Question | Subgraph |
|---|---|
| How many Platinum customers, what do they spend | Data Analysis |
| What does a Platinum member get, how do points work | Knowledge Base |
| What discount does Gulf Catering Services have | Knowledge Base (customer agreement) |
| How much did Gulf Catering Services buy in 2025 | Data Analysis |
| Customers' emails or phone numbers | Rejected (restricted data) |
