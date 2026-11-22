# Data Analysis: Edge Cases and Data Quality

- Document ID: DA-10
- Index: data_analysis
- Purpose: what to do when a question is ambiguous, the period is partial, the result is empty or small, or the data cannot answer the question.

## Period Edge Cases

| Situation | Handling |
|---|---|
| Period entirely after 2026-10-31 (for example March 2027) | Run no query. Report that the data ends on 2026-10-31 and offer a forecast through the Inventory subgraph for unit demand. |
| Period partly after 2026-10-31 | Use the available part and state the actual range, for example "1 January to 31 October 2026". |
| "This year", "year to date" | 2026-01-01 to 2026-10-31. Compare with 2025-01-01 to 2025-10-31, never with full-year 2025. |
| "Last year" | Calendar year 2025. |
| "This week" | No data exists for the week starting 2026-11-01. Use the last complete week (25 to 31 October 2026) and say so. |
| "Today" and "yesterday" | The last three days of the data contain orders with status `Processing`, which are not revenue yet. Today's and yesterday's net revenue may look lower than usual; say so. |
| Hijri dates ("1 Ramadan") | Map to the Gregorian window in `calendar` and name the window. |
| Fiscal year | The company reports on the calendar year. There is no separate fiscal calendar. |

## Entity Edge Cases

- Ambiguous city ("Jeddah" has two stores, "Riyadh" has two stores and the Distribution Center): sum the matching stores for city-level revenue and list them; ask only if the answer would differ materially by store.
- Ambiguous product name: find the SKU first with DA-SQL-29. If several SKUs match, answer for all and name them.
- Product line synonyms ("electronics", "grocery") map to the exact category names in RT-07.
- New and discontinued SKUs have short sales histories. Compare only the months in which both items were sold, and mention the launch or discontinuation date.
- The Distribution Center `RYD-DC` carries Online, Mobile App and B2B sales. It is excluded from store rankings and store productivity measures, and included in total, channel and online questions.

## Empty and Small Results

- An empty result is a valid answer ("no orders matched"). Check the filter for a typing mistake or a status mismatch before saying so, using DA-SQL-29 for names and DA-SQL-30 for statuses.
- If fewer than 5 customers match a customer filter, report only the count.
- A group with fewer than 30 observations is described, not tested. Say that the sample is too small for a reliable test.
- A growth rate from a very small base (under SAR 1,000 or fewer than 10 orders) is reported as "not meaningful".
- A zero denominator gives "not defined" (for example growth from zero, margin on zero revenue).

## Status and Data Quality Rules

- Revenue uses `Completed` orders only. `Cancelled` orders are never counted. `Returned` (fully returned) orders are excluded from revenue, and their value is not deducted twice. Partial returns remain in `Completed` revenue and appear in `sales_returns`.
- `Processing` orders exist only in the last three days of the data and are excluded.
- Order status counts and values can be shown on request (DA-SQL-30).
- `customer_id` is NULL for anonymous in-store orders; customer measures exclude them, revenue measures include them.
- `discount_amount` on an order is informational; net revenue already reflects the discount.
- Shipping fees and VAT are never part of revenue.
- Timestamps are Riyadh local time; hours of day refer to local time.
- Currency is always SAR.

## Questions the Data Cannot Answer

| Request | Answer |
|---|---|
| Operating profit, rent, salaries as costs, net profit | Only gross margin (net revenue minus cost of goods) exists. State this and offer gross margin. |
| Foot traffic, conversion rate, website visits | Not stored. Offer orders and average order value instead. |
| Customer satisfaction, reviews | Not stored. |
| Competitor prices and market share | Not stored. |
| Lost sales caused by stock-outs | Not measured. Inventory can show out-of-stock periods. |
| Sales for dates after 2026-10-31 | Not available; offer a forecast of units. |
| Sales before 2024-01-01 | Not available; the data begins on 2024-01-01. |
| Individual customers' names, emails and phone numbers | Not provided. Customer codes and aggregates only. |
| Why something happened | The data shows what happened, not why. Give the pattern and, if relevant, calendar or promotion context, and label any explanation as a hypothesis. |

## Conflicts Between Sources

- Measured numbers (revenue, orders, supplier on-time delivery) come from the database. If a document gives a different number for the same measure, report the database figure and mention the document figure only if the user asked about the document.
- Contract and policy wording comes from the Knowledge Base. Do not infer policy from data.
- If two SQL results disagree, check that both use the same status filter, period and unit (orders versus lines), and report the corrected comparison.

## Failure Handling

- If a query fails validation, regenerate it using the validator message (at most twice).
- If a query times out (8 seconds), aggregate in SQL at a coarser level (month instead of day, line instead of SKU) or narrow the period.
- If the Pandas tool fails, correct the code using the error (at most twice). After the second failure return `status = "failed"` with a plain explanation, or `partial` with the SQL figures that are reliable. Never invent a number.
- State in `warnings` any limitation that changes how the number should be read.

## SQL Patterns

### DA-SQL-29: Find a product by name or brand

Use to resolve a product name from the user to its SKU, line and lifecycle status before querying sales. `ILIKE` is used here because product names are free text.

```sql
SELECT p.sku,
       p.product_name,
       p.brand,
       p.subcategory,
       pc.category_name,
       p.lifecycle_status,
       p.launch_date,
       p.discontinued_date
FROM products p
JOIN product_categories pc ON pc.category_id = p.category_id
WHERE p.product_name ILIKE '%tower fan%'
   OR p.brand ILIKE '%AirWhirl%'
ORDER BY p.sku
LIMIT 20;
```

### DA-SQL-30: Order status mix for a period

Use to explain differences between order counts and revenue, or when a result is unexpectedly empty. Counts orders and sums the order subtotal by status for 2025.

```sql
SELECT status,
       COUNT(*) AS orders,
       ROUND(SUM(subtotal_amount), 2) AS subtotal_sar
FROM sales_orders
WHERE order_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
GROUP BY status
ORDER BY orders DESC;
```
