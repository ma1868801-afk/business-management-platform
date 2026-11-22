# Router: Data Analysis Subgraph Description

- Document ID: RT-02
- Index: router
- Subgraph name: `data_analysis`

## Purpose

The Data Analysis subgraph answers questions that need numbers computed from the sales, customer, promotion, return and target tables in PostgreSQL. It writes read-only SQL, optionally computes statistics with Pandas and optionally runs a hypothesis test when the user asks for one.

## Choose Data Analysis When the Question Is About

- Revenue, net sales, gross sales, margin, units sold, number of orders, average order value, basket size.
- Comparisons and trends: month over month, year over year, growth, share of total, ranking of stores, product lines, SKUs, channels or payment methods.
- Seasonality: Ramadan, Eid, Hajj, White Friday, National Day, summer, weekends, paydays, hours of day.
- Customers: loyalty tiers, customer segments, repeat purchase, new registrations, cohorts, acquisition channels, business accounts and their orders.
- Returns and refunds, return rates and return reasons.
- Promotions and discounts: promotion performance, discount depth, orders with a promotion.
- Targets: monthly sales targets and attainment by location.
- Statistical questions: "is the difference significant", "test whether", "correlation between".

## Tools and Behavior

| Step | Tool | Rule |
|---|---|---|
| 1 | Data Analysis RAG | Retrieves SQL guidelines, Pandas instructions and domain knowledge. |
| 2 | PostgreSQL tool | Read-only SELECT or WITH queries on the allowed tables and views. |
| 3 | Pandas tool | Used only when computation is needed after extraction (growth rates, shares, rankings, tests). |
| 4 | Hypothesis test | Only when the user explicitly asks for significance, a test, a p-value or a confidence statement. |

If the question only asks to list or extract data (for example "show orders of customer X" or "list the promotions in 2025"), the Pandas tool is bypassed.

## Routing Hints

- `needs_computation`: true when the answer needs growth, share, ranking, correlation or any calculation beyond a single SQL aggregate; false for plain extraction or a single aggregate.
- `hypothesis_test`: true only when the user asks for a statistical test or significance.

## Typical Questions

- What was net revenue by product line in 2025?
- Which store had the highest revenue last month?
- How did online share of revenue change from 2024 to 2026?
- Which payment method is most used in stores?
- Is the average order value of Gold customers significantly different from Silver customers?
- What is the return rate of Fashion and Apparel?
- Which locations missed their sales target in October 2026?
- How many new customers registered each month in 2025?

## Do Not Choose Data Analysis For

- Current stock, reorder points or forecasts (Inventory).
- Policy, contract or procedure questions (Knowledge Base).
- Requests to change data or to export personal contact details (reject).
