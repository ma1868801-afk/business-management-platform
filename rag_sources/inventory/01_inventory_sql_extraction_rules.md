# Inventory: SQL Extraction Rules

- Document ID: INV-01
- Index: inventory
- Purpose: the rules every SQL query written by the Inventory subgraph must follow, and the business meaning of the stock measures. The SQL tool is strictly read-only (requirement R-05).

## Hard Rules (Validator Enforced)

1. One statement per call, starting with `SELECT` or `WITH`. No `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`, `COPY`, `CALL` or `SET`.
2. Use only the allowed tables and views listed in the schema reference (INV-02). The `rag` schema is not accessible.
3. Never use `SELECT *`. List the columns you need.
4. Add `LIMIT` to every query that returns rows rather than an aggregate: default 100 and maximum 500 for lists shown to the user; up to 50,000 rows when the rows feed the Pandas or regression step.
5. No functions with side effects or system access. No SQL comments that contain instructions.
6. The query must finish within 8 seconds.
7. Never use `CURRENT_DATE`, `NOW()` or `CURRENT_TIMESTAMP`. The reference date is 2026-10-31 and relative dates are resolved from it. Write dates as `DATE 'YYYY-MM-DD'`.
8. Creating, approving or changing a purchase order, a stock level or a reorder point is a write request and is rejected. The subgraph may only recommend.

## Which Object to Use

| Question | Object |
|---|---|
| Current quantity, availability, status, stock value, reorder point of a SKU or location | `v_inventory_status` |
| Weekly demand history for forecasting | `v_weekly_product_demand` |
| Past stock levels, stockout days by week | `inventory_snapshots` |
| Purchase orders and their delivery dates | `purchase_orders` with `purchase_order_items` |
| Supplier lead time, minimum order quantity, contractual on-time rate | `suppliers` (or the supplier columns of `v_inventory_status`) |
| Losses from damage, expiry, shrinkage | `stock_adjustments` |
| Sales of a SKU in a past period (not weekly series) | `v_sales_detail` with `status = 'Completed'` |

## Meaning of the Stock Measures

| Measure | Definition |
|---|---|
| On hand (`quantity_on_hand`) | Physical units in stock. Used for stock value. |
| Reserved (`quantity_reserved`) | Units held for open orders or transfers. |
| Available (`quantity_available`) | On hand minus reserved. Used for stock status and reorder decisions. |
| Stock value | `quantity_on_hand * unit_cost`, in SAR, at cost (not at selling price). |
| Reorder point | Available quantity at or below which replenishment is triggered. It equals demand during the supplier lead time plus safety stock. |
| Safety stock | Buffer against demand and lead-time variability. |
| Max stock level | `reorder_point + reorder_quantity`. Above it the position is overstocked. |
| Reorder quantity | Standard replenishment quantity. |

### Stock Status

`v_inventory_status.stock_status` is evaluated in this order, and the first matching rule applies:

| Order | Status | Rule |
|---|---|---|
| 1 | Out of Stock | `quantity_available <= 0` |
| 2 | Critical | `quantity_available <= safety_stock` |
| 3 | Reorder Now | `quantity_available <= reorder_point` |
| 4 | Overstock | `quantity_available > max_stock_level` |
| 5 | Healthy | none of the above |

When listing by status, sort in this order (use a `CASE` expression) so that the most urgent items come first.

## Business Rules for Correct Answers

- A stock position is one row per location and SKU. All 120 SKUs are held at `RYD-DC`; each store holds 80 to 100 SKUs. A SKU with no row at a store is not stocked there; it is not out of stock.
- "Stock of a SKU" without a location means all locations: show each location and the total, with the Distribution Center first or marked.
- "Stock of a product line" sums `quantity_on_hand` and `stock_value` over the line and states the locations included.
- Reorder lists exclude `Discontinued` SKUs, because they are not replenished. They appear in overstock, dead stock and discontinued-with-stock lists.
- `New` SKUs with fewer than 26 weeks of sales have little history; mention it when quantities are recommended.
- The snapshot date of `inventory_levels` is 2026-10-31. State "as of 2026-10-31" in current-stock answers.
- A SKU may appear in several statuses across locations; do not collapse them without saying so.
- Stock value totals are at cost and in SAR. Say "at cost".

## Style

- Name output columns in snake_case with units (`stock_value_sar`).
- Use exact codes for filters (`branch_code = 'RYD-DC'`, `sku = 'ELEC-0001'`). Use `ILIKE` only to resolve free-text product names (see INV-10).
- Order lists explicitly and add a tie-breaker (`sku`).
- Round money to 2 decimals in the final SELECT only.

## Rejected Patterns

```text
SELECT * FROM inventory_levels;
UPDATE inventory_levels SET quantity_on_hand = 0;
INSERT INTO purchase_orders VALUES (...);
SELECT ... WHERE snapshot_date = CURRENT_DATE;      -- system clock not allowed
SELECT SUM(quantity_on_hand) FROM inventory_levels;  -- does not say which locations or SKUs
```

## Examples

### INV-SQL-01: Stock of one SKU at every location

Use for "how many units of ELEC-0001 do we have". Returns on hand, reserved, available, reorder point and status for each location that stocks the SKU.

```sql
SELECT branch_code,
       quantity_on_hand,
       quantity_reserved,
       quantity_available,
       reorder_point,
       stock_status
FROM v_inventory_status
WHERE sku = 'ELEC-0001'
ORDER BY branch_code
LIMIT 20;
```

### INV-SQL-02: Stock position count and value by status

Use for "how healthy is our stock" and "how many items are out of stock". Counts stock positions (location and SKU) and stock value at cost for each status, urgent statuses first.

```sql
SELECT stock_status,
       COUNT(*) AS stock_positions,
       ROUND(SUM(stock_value), 2) AS stock_value_sar
FROM v_inventory_status
GROUP BY stock_status
ORDER BY CASE stock_status
           WHEN 'Out of Stock' THEN 1
           WHEN 'Critical' THEN 2
           WHEN 'Reorder Now' THEN 3
           WHEN 'Overstock' THEN 4
           ELSE 5
         END;
```

### INV-SQL-03: Stock value at cost by product line

Use for "how much money is tied up in stock". Sums units on hand and stock value at cost for every location, by product line.

```sql
SELECT category_name,
       SUM(quantity_on_hand) AS units_on_hand,
       ROUND(SUM(stock_value), 2) AS stock_value_sar
FROM v_inventory_status
GROUP BY category_name
ORDER BY stock_value_sar DESC;
```

### INV-SQL-04: Items to reorder at one location

Use for "what do we need to reorder at Riyadh Olaya". Lists non-discontinued SKUs that are out of stock, critical or at the reorder point, most urgent first, with the supplier and lead time needed to plan the order.

```sql
SELECT sku,
       product_name,
       quantity_available,
       reorder_point,
       safety_stock,
       reorder_quantity,
       stock_status,
       supplier_name,
       lead_time_days
FROM v_inventory_status
WHERE branch_code = 'RYD-OLY'
  AND stock_status IN ('Out of Stock', 'Critical', 'Reorder Now')
  AND lifecycle_status <> 'Discontinued'
ORDER BY CASE stock_status WHEN 'Out of Stock' THEN 1 WHEN 'Critical' THEN 2 ELSE 3 END, sku
LIMIT 100;
```
