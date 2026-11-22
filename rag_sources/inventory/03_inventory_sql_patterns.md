# Inventory: SQL Patterns

- Document ID: INV-03
- Index: inventory
- Purpose: tested SQL patterns for the most common stock and purchasing questions. Adapt the SKU, location and dates; keep the structure. Basic patterns are in INV-01.

## Pattern Index

| Question type | Pattern |
|---|---|
| Overstock excess by product line | INV-SQL-05 |
| Weeks of cover per SKU | INV-SQL-06 |
| Dead stock | INV-SQL-07 |
| Discontinued SKUs that still hold stock | INV-SQL-08 |
| Stockout history | INV-SQL-09 |
| Weekly stock trend of one SKU | INV-SQL-10 |
| Overdue purchase orders | INV-SQL-11 |
| Stock adjustments (losses) | INV-SQL-12 |
| Stock by location for a product line | INV-SQL-13 |

## Definitions Used by the Patterns

| Term | Definition |
|---|---|
| Weeks of cover | Available units divided by average weekly units sold over the last 8 complete weeks (6 September to 31 October 2026). A SKU without sales has no cover figure. |
| Slow mover | A SKU with more than 26 weeks of cover. State the window used. |
| Dead stock | A SKU with units on hand and no Completed sale in the last 13 weeks (3 August to 31 October 2026). |
| Excess units | Available units above `max_stock_level` for an overstock position. |
| Overdue purchase order | Status `Open` or `In Transit` with `expected_delivery_date` before 2026-10-31. |
| Late delivery | A Received or Partially Received purchase order whose `actual_delivery_date` is after `expected_delivery_date`. |
| Stockout week | A weekly snapshot with `stockout_days > 0`. |

## Patterns

### INV-SQL-05: Overstock excess by product line

Use for "how much money is tied up in overstock". Counts overstock positions and values the units above the maximum stock level at cost.

```sql
SELECT category_name,
       COUNT(*) AS overstock_positions,
       SUM(quantity_available - max_stock_level) AS excess_units,
       ROUND(SUM((quantity_available - max_stock_level) * unit_cost), 2) AS excess_value_sar
FROM v_inventory_status
WHERE stock_status = 'Overstock'
GROUP BY category_name
ORDER BY excess_value_sar DESC;
```

### INV-SQL-06: Weeks of cover per SKU across all locations

Use for "which products will run out first" and "how long will stock last". Divides available units over all locations by the average weekly units over the last 8 complete weeks. The average divides by 8 so that weeks without sales count as zero. Discontinued SKUs are left out.

```sql
WITH demand AS (
  SELECT product_id,
         SUM(units_sold) / 8.0 AS avg_weekly_units
  FROM v_weekly_product_demand
  WHERE week_start_date BETWEEN DATE '2026-09-06' AND DATE '2026-10-25'
  GROUP BY product_id
), stock AS (
  SELECT product_id,
         sku,
         product_name,
         SUM(quantity_available) AS units_available
  FROM v_inventory_status
  WHERE lifecycle_status <> 'Discontinued'
  GROUP BY product_id, sku, product_name
)
SELECT s.sku,
       s.product_name,
       s.units_available,
       ROUND(d.avg_weekly_units, 1) AS avg_weekly_units,
       ROUND(s.units_available / NULLIF(d.avg_weekly_units, 0), 1) AS weeks_of_cover
FROM stock s
LEFT JOIN demand d ON d.product_id = s.product_id
ORDER BY weeks_of_cover ASC NULLS LAST, s.sku
LIMIT 20;
```

### INV-SQL-07: Dead stock

Use for "which products are not selling". Lists SKUs with units on hand and no Completed sale between 3 August and 31 October 2026, with the value at cost. Discontinued SKUs appear too; the lifecycle column tells them apart.

```sql
SELECT s.sku,
       s.product_name,
       s.lifecycle_status,
       SUM(s.quantity_on_hand) AS units_on_hand,
       ROUND(SUM(s.stock_value), 2) AS stock_value_sar
FROM v_inventory_status s
WHERE NOT EXISTS (
        SELECT 1
        FROM v_sales_detail v
        WHERE v.product_id = s.product_id
          AND v.status = 'Completed'
          AND v.order_date BETWEEN DATE '2026-08-03' AND DATE '2026-10-31')
GROUP BY s.sku, s.product_name, s.lifecycle_status
HAVING SUM(s.quantity_on_hand) > 0
ORDER BY stock_value_sar DESC, s.sku
LIMIT 50;
```

### INV-SQL-08: Discontinued SKUs that still hold stock

Use for "what stock do we hold for discontinued products". Returns each location position with the discontinuation date and the value at cost.

```sql
SELECT s.branch_code,
       s.sku,
       s.product_name,
       p.discontinued_date,
       s.quantity_on_hand,
       s.stock_value AS stock_value_sar
FROM v_inventory_status s
JOIN products p ON p.product_id = s.product_id
WHERE s.lifecycle_status = 'Discontinued'
  AND s.quantity_on_hand > 0
ORDER BY s.stock_value DESC, s.branch_code, s.sku
LIMIT 100;
```

### INV-SQL-09: Stockout history at the Distribution Center

Use for "which products ran out most often in 2025". Counts the weekly snapshots with at least one stockout day (`stockout_days` is 0 to 7) and the total stockout days, for SKUs with three or more stockout weeks.

```sql
SELECT p.sku,
       p.product_name,
       COUNT(*) FILTER (WHERE sn.stockout_days > 0) AS weeks_with_stockout,
       SUM(sn.stockout_days) AS stockout_days_total
FROM inventory_snapshots sn
JOIN branches b ON b.branch_id = sn.branch_id
JOIN products p ON p.product_id = sn.product_id
WHERE b.branch_code = 'RYD-DC'
  AND sn.snapshot_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
GROUP BY p.sku, p.product_name
HAVING COUNT(*) FILTER (WHERE sn.stockout_days > 0) >= 3
ORDER BY weeks_with_stockout DESC, p.sku
LIMIT 50;
```

### INV-SQL-10: Weekly stock trend of one SKU

Use for "how has the stock of GROC-0001 developed". Returns the last 26 Saturday snapshots (9 May to 31 October 2026) of on-hand units and stockout days at the Distribution Center.

```sql
SELECT sn.snapshot_date,
       sn.quantity_on_hand,
       sn.stockout_days
FROM inventory_snapshots sn
JOIN branches b ON b.branch_id = sn.branch_id
JOIN products p ON p.product_id = sn.product_id
WHERE p.sku = 'GROC-0001'
  AND b.branch_code = 'RYD-DC'
  AND sn.snapshot_date >= DATE '2026-05-09'
ORDER BY sn.snapshot_date
LIMIT 100;
```

### INV-SQL-11: Overdue purchase orders

Use for "which purchase orders are late". Lists Open and In Transit orders whose expected delivery date has passed on 2026-10-31, with the days overdue and the supplier.

```sql
SELECT po.po_number,
       s.supplier_code,
       s.supplier_name,
       b.branch_code AS destination,
       po.status,
       po.order_date,
       po.expected_delivery_date,
       (DATE '2026-10-31' - po.expected_delivery_date) AS days_overdue,
       po.total_amount AS total_amount_sar
FROM purchase_orders po
JOIN suppliers s ON s.supplier_id = po.supplier_id
JOIN branches b ON b.branch_id = po.destination_branch_id
WHERE po.status IN ('Open', 'In Transit')
  AND po.expected_delivery_date < DATE '2026-10-31'
ORDER BY days_overdue DESC, po.po_number
LIMIT 100;
```

### INV-SQL-12: Stock adjustments by reason

Use for "how much stock did we lose to damage, expiry and shrinkage". Sums the cost impact of adjustments in the last 12 months (1 November 2025 to 31 October 2026). Losses are negative, so the largest loss comes first.

```sql
SELECT reason,
       COUNT(*) AS adjustments,
       SUM(quantity_change) AS units_change,
       ROUND(SUM(cost_impact), 2) AS cost_impact_sar
FROM stock_adjustments
WHERE adjustment_date BETWEEN DATE '2025-11-01' AND DATE '2026-10-31'
GROUP BY reason
ORDER BY cost_impact_sar;
```

### INV-SQL-13: Stock by location for a product line

Use for "how much Home Appliances stock does each location hold". Counts the SKUs stocked, units on hand and value at cost per location.

```sql
SELECT branch_code,
       COUNT(*) AS skus_stocked,
       SUM(quantity_on_hand) AS units_on_hand,
       ROUND(SUM(stock_value), 2) AS stock_value_sar
FROM v_inventory_status
WHERE category_name = 'Home Appliances'
GROUP BY branch_code
ORDER BY stock_value_sar DESC;
```

## Reading the Results

- Adjustments with a negative `cost_impact` are losses; a Count Correction can be positive.
- A purchase order is overdue only while it is Open or In Transit. A Received order that arrived late is a late delivery, not an overdue order.
- Cover is a snapshot of the last 8 weeks. For a seasonal SKU, say that cover changes with the season and refer to the forecast when the user needs a forward view.
- Quote the date "as of 2026-10-31" for current stock and cover.
