# Data Analysis: Retail KPI Definitions

- Document ID: DA-07
- Index: data_analysis
- Purpose: the exact definition of each retail measure used by Nakhla Retail Group. When a user asks for a measure by name, use the definition here and name the definition in the answer. All money is in SAR and excludes VAT unless stated.

## Revenue and Margin

| KPI | Definition | Source |
|---|---|---|
| Net revenue (sales, revenue, turnover) | Sum of `line_total` of order lines on orders with status `Completed`. It is net of line discounts and excludes VAT and shipping fees. | `v_sales_detail.line_total` |
| Gross sales | Net revenue plus line discounts: `SUM(quantity * unit_price)` on the same lines. | `v_sales_detail` |
| Discount amount | Gross sales minus net revenue. At order level, `sales_orders.discount_amount`. | `v_sales_detail`, `sales_orders` |
| Discount rate | Discount amount divided by gross sales, in percent. | derived |
| Cost of goods sold | Sum of `line_cost` (quantity times unit cost at the time of sale) on the same lines. | `v_sales_detail.line_cost` |
| Gross margin | Net revenue minus cost of goods sold (`line_margin`). | `v_sales_detail.line_margin` |
| Gross margin percent | Gross margin divided by net revenue, in percent. | derived |
| Customer payment (basket total) | `sales_orders.total_amount`: subtotal plus 15 percent VAT plus shipping fee. It is what the customer pays and is never reported as revenue. | `sales_orders` |

## Volume and Basket

| KPI | Definition | Source |
|---|---|---|
| Orders (transactions) | `COUNT(DISTINCT order_id)` of Completed orders. In the line-level view, `COUNT(*)` counts lines, not orders. | `v_sales_detail` or `sales_orders` |
| Units | Sum of `quantity` on Completed lines. | `v_sales_detail.quantity` |
| Average order value (AOV, basket size) | Net revenue divided by Completed orders. | derived |
| Units per transaction | Units divided by Completed orders. | derived |
| Average selling price | Net revenue divided by units. | derived |

## Location Productivity

| KPI | Definition | Source |
|---|---|---|
| Revenue per square metre | Net revenue of a store divided by `branches.area_sqm`. Stores only; the Distribution Center is excluded. | `branches`, `v_sales_detail` |
| Revenue per employee | Net revenue of a store divided by `branches.staff_count`. Stores only. | `branches`, `v_sales_detail` |
| Store ranking | Stores ordered by net revenue for the same period, excluding the Distribution Center (`RYD-DC`), because it carries Online, Mobile App and B2B sales. | `v_sales_detail` |
| Target attainment | Net revenue of a location in a month divided by its `monthly_sales_targets.target_revenue`, in percent. A location at or above 100 percent met target. | `monthly_sales_targets` |

Revenue per square metre and per employee are annual figures when the period is a year. Divide by months for a monthly figure, and say so.

## Channel and Mix

| KPI | Definition | Source |
|---|---|---|
| Channel share | Net revenue of a channel divided by total net revenue of the same period. | `v_sales_detail.channel` |
| Digital share | Share of Online plus Mobile App net revenue. B2B and In-Store are not digital. | derived |
| Category share | Net revenue of a product line divided by total net revenue. | `v_sales_detail.category_name` |
| Payment mix | Share of orders by `payment_method` within a channel. | `sales_orders` |

## Returns

| KPI | Definition | Source |
|---|---|---|
| Return rate by value | `SUM(refund_amount)` of returns on Completed orders divided by net revenue of the same orders. Fully returned orders (status `Returned`) are excluded from both sides. | `sales_returns`, `v_sales_detail` |
| Return rate by lines | Order lines with at least one return divided by lines sold. | `sales_returns`, `sales_order_items` |
| Return reason mix | Share of returns by `return_reason`. | `sales_returns` |

State which return rate is used. The by-value rate is the default for management questions, and the by-lines rate is used for proportion tests.

## Customers

| KPI | Definition | Source |
|---|---|---|
| New customers | Customers with `registration_date` inside the period. | `customers` |
| Active customers | Distinct customers with at least one Completed order in the period. Anonymous in-store orders have no customer and are not counted. | `sales_orders` |
| Repeat purchase rate | Individual customers with two or more Completed orders divided by individual customers with at least one Completed order, over the stated period. | `sales_orders` |
| Retention (cohort) | Share of a registration cohort that places an order in month N after registration. | DA-SQL-24 |
| Tier share | Share of individual customers in each `loyalty_tier` (None, Silver, Gold, Platinum). | `customers` |
| Customer value | Net revenue per active customer in the period. | derived |

Loyalty tier is assigned on trailing 12-month net spend: Silver from SAR 3,000, Gold from SAR 10,000 and Platinum from SAR 25,000. Corporate (Business) customers have tier `None`.

## Time and Season Measures

| KPI | Definition | Source |
|---|---|---|
| Average daily net revenue | Net revenue divided by the number of calendar days in the group (days with no orders count as zero). | `calendar` joined to sales |
| Seasonal uplift | Average daily net revenue in a season divided by average daily net revenue on `Regular` days of the same year. A value of 1.40 means 40 percent higher. | DA-SQL-20 |
| Weekend uplift | Average daily store net revenue on Friday and Saturday divided by the Sunday to Thursday average. | DA-SQL-21 |
| Payday uplift | Average daily net revenue on days 25 to 28 divided by the average on other days of the same months. | DA-SQL-21 |
| Seasonal index | Average of a month divided by the average of all months, using complete years. | DA-PY-06 |
| Year over year growth | Value in a period divided by the value in the same period a year earlier, minus one. | DA-PY-01, DA-PY-04 |
| Year to date | 2026-01-01 to 2026-10-31. Compare with 2025-01-01 to 2025-10-31. | derived |

The week starts on Sunday. The weekend is Friday and Saturday. Season labels are in `calendar.season` and `sales_orders.season`; one day belongs to one season only, using the precedence White Friday, Eid al-Fitr, Hajj and Eid al-Adha, Ramadan, National Day, Founding Day, Back to School, Summer, Winter, Regular.

## Stock Measures

Stock quantities, stock value, status, cover and replenishment belong to the Inventory subgraph. Revenue-side questions about a product are answered here; questions about units on hand are routed to Inventory.

## Naming in Answers

- Say "net revenue" instead of "sales" when the exact number matters, and mention "excluding VAT" once.
- Write percentages with two decimals in tables and with at most one decimal in sentences.
- Write money as "SAR 1,234,567.89" or in millions as "SAR 12.35 million" and keep the same style within one answer.
